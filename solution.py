from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
import os
from pydantic import BaseModel
from typing import List, Dict, Optional
import uuid
import io
from datetime import datetime
import json
import traceback
import tempfile
import asyncio
import re
# For qwen3 via Ollama
from langchain_ollama import ChatOllama

# For LlamaParse
from llama_cloud_services import LlamaParse

load_dotenv()
api_key = os.getenv("LLAMA_CLOUD_API_KEY")
if not api_key:
    raise ValueError("Set LLAMA_CLOUD_API_KEY in environment")
parser = LlamaParse(api_key=api_key)

app = FastAPI()

UPLOAD_DIR = 'uploads'
OUTPUT_DIR = 'outputs'
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

class ResumeData(BaseModel):
    name: str
    email: str
    phone: str
    summary: Optional[str] = None
    work_experience: List[Dict[str, str]]
    education: List[Dict[str, str]]
    skills: List[str]
    projects: List[Dict[str, str]]
    certifications: List[str]
    other: List[Dict[str, str]]

class JobDescription(BaseModel):
    required_skills: List[str]
    preferred_skills: List[str]
    experience_years: int
    responsibilities: List[str]
    company_culture: Optional[str] = None

file_storage: Dict[str, str] = {}

def get_llm():
    return ChatOllama(model="qwen3", temperature=0)

def extract_resume_data_from_md(md_text: str) -> ResumeData:
    llm = get_llm()
    system_prompt = (
    "You are a resume parsing assistant. Given a Markdown version of a resume, "
    "convert it into a structured JSON object using the **exact** schema below:\n\n"
    "**ResumeData schema:**\n"
    "- name: string\n"
    "- email: string\n"
    "- phone: string\n"
    "- summary: string or null\n"
    "- work_experience: list of {title, company, dates, description}\n"
    "- education: list of {school, degree, dates}\n"
    "- skills: list of strings\n"
    "- projects: list of {name, description}\n"
    "- certifications: list of strings\n"
    "- other: list of {label, content}\n\n"
    "⚠️ Output only a complete and valid JSON object. No extra explanation. No commentary. No Markdown headings.\n"
    "Wrap the output *only* inside triple backticks with a `json` tag, like this:\n"
    "```json\n{\n  ...\n}\n```"
)

    user_prompt = f"Here is the Markdown resume:\n\n{md_text}"

    ai_msg = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    response_text = getattr(ai_msg, "content", str(ai_msg)).strip()

    # Try extracting first JSON block in case LLM adds extra commentary
    match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response_text)
    if not match:
        raise ValueError("No valid JSON block found in LLM response.")
    json_text = match.group(1)

    try:
        parsed_json = json.loads(json_text)
        return ResumeData.model_validate(parsed_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse JSON: {e}\nRaw JSON block:\n{json_text}")

# ✅ ASYNC version of parse_resume_with_llama
async def parse_resume_with_llama(file_bytes: bytes, filename: str) -> ResumeData:
    try:
        suffix = os.path.splitext(filename)[1]
        print("[DEBUG] File suffix for temp file:", suffix)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            tmp_path = tmp.name

        print("[DEBUG] Calling parser.aparse on temp file:", tmp_path)
        parsed_obj = await asyncio.to_thread(parser.parse, tmp_path)

        markdown_resume = parsed_obj.get_markdown_documents(split_by_page=True)
        print("[DEBUG] LlamaParse response:", markdown_resume)
        print("[DEBUG] parsed_obj type:", type(markdown_resume))

        print("[DEBUG] .md preview:", markdown_resume[:200])
        try:
            os.remove(tmp_path)
            print("[DEBUG] Temporary file removed:", tmp_path)
        except Exception:
            pass

        # Now use your LLM to convert markdown to structured ResumeData
        print("[DEBUG] Converting markdown to ResumeData via LLM...")
        dataFromLLM = extract_resume_data_from_md(markdown_resume)
        print("[DEBUG] LLM response:\n", dataFromLLM)
        return dataFromLLM

    except Exception as e:
        print("[ERROR] parse_resume_with_llama exception:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"LlamaParse failed: {e}")


def analyze_job_description(text: str) -> JobDescription:
    print("[DEBUG] Analyzing job description text:", text[:500])
    llm = get_llm()

    system_prompt = (
        "You are a job description analysis assistant. "
        "Given raw job description text, extract into JSON with exactly these fields:\n"
        "- required_skills: list of strings\n"
        "- preferred_skills: list of strings\n"
        "- experience_years: integer (minimum years of experience)\n"
        "- responsibilities: list of strings\n"
        "- company_culture: string or null\n"
        "Respond ONLY with a valid JSON object. Do NOT include any commentary, markdown, or code fences."
    )

    user_prompt = f"Job description text:\n\"\"\"{text}\"\"\""

    ai_msg = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    # Safely extract raw string
    response_text = getattr(ai_msg, "content", str(ai_msg)).strip()
    print("[DEBUG] Raw LLM response:\n", response_text[:300])

    # Strip markdown code block wrappers if present
    cleaned = (
        response_text
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    print("[DEBUG] Cleaned LLM response:\n", cleaned[:300])

    if not cleaned:
        raise HTTPException(status_code=500, detail="LLM returned an empty response.")

    # Parse JSON and validate
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse JSON: {e}\nRaw LLM output:\n{cleaned}")

    try:
        jd = JobDescription.model_validate(parsed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsed JD JSON invalid: {e}\nJSON: {parsed}")

    return jd



def generate_tailored_resume(resume_data: ResumeData, job_description: JobDescription) -> str:
    llm = get_llm()
    system_prompt = (
        "You are a resume generator. Given JSON of user resume data and JSON of job description data, "
        "produce a tailored resume in Markdown format. "
        "Structure with headings: Name & Contact, Summary, Skills, Experience, Education, Projects, Certifications, Other. "
        "Emphasize alignment: reorder or rephrase bullet points to match required_skills and responsibilities, "
        "highlight metrics if present. Output only the Markdown text."
    )
    payload = {
        "resume": resume_data.dict(),
        "job": job_description.dict()
    }
    user_prompt = (
        "User resume JSON:\n" + json.dumps(payload["resume"], indent=2) +
        "\n\nJob description JSON:\n" + json.dumps(payload["job"], indent=2)
    )
    ai_msg = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])
    return getattr(ai_msg, "content", str(ai_msg))

def generate_cover_letter(resume_data: ResumeData, job_description: JobDescription) -> str:
    llm = get_llm()
    system_prompt = (
        "You are a cover letter writer. Given JSON of user resume data and JSON of job description data, "
        "write a personalized cover letter in Markdown or plain text. "
        "Include salutation, intro stating interest, body highlighting 2-3 key matching experiences/skills, and a closing. "
        "Do not include extra commentary; output only the letter."
    )
    payload = {
        "resume": resume_data.model_dump(),
        "job": job_description.model_dump()
    }
    user_prompt = (
        "User resume JSON:\n" + json.dumps(payload["resume"], indent=2) +
        "\n\nJob description JSON:\n" + json.dumps(payload["job"], indent=2)
    )
    ai_msg = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])
    return getattr(ai_msg, "content", str(ai_msg))

@app.post('/upload-resume')
async def upload_resume(files: List[UploadFile] = File(...)):
    file_ids = []
    for file in files:
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1]
        path = os.path.join(UPLOAD_DIR, file_id + ext)
        contents = await file.read()
        with open(path, 'wb') as f:
            f.write(contents)
        file_storage[file_id] = path
        file_ids.append(file_id)
    return {'file_ids': file_ids}

@app.post('/generate')
async def generate_resume_and_cover_letter(
    resume_file_id: str = Form(...),
    job_description: str = Form(...)
):
    try:
        if resume_file_id not in file_storage:
            raise HTTPException(status_code=404, detail="Resume file not found")

        resume_path = file_storage[resume_file_id]
        print("[DEBUG] Resume file path:", resume_path)
        with open(resume_path, 'rb') as f:
            data = f.read()
            print("[DEBUG] Read resume file bytes, size:", len(data))

        print("[DEBUG] Calling parse_resume_with_llama")
        resume_data = await parse_resume_with_llama(data, os.path.basename(resume_path))
        print("[DEBUG] parse_resume_with_llama succeeded:", resume_data)

        print("[DEBUG] Calling analyze_job_description")
        jd_data = analyze_job_description(job_description)
        print("[DEBUG] analyze_job_description succeeded:", jd_data)

        print("[DEBUG] Calling generate_tailored_resume")
        tailored_md = generate_tailored_resume(resume_data, jd_data)
        print("[DEBUG] tailored resume preview:\n", tailored_md[:200])

        print("[DEBUG] Calling generate_cover_letter")
        cover_md = generate_cover_letter(resume_data, jd_data)
        print("[DEBUG] cover letter preview:\n", cover_md[:200])

        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        resume_fn = f"resume_{ts}.md"
        cover_fn = f"cover_letter_{ts}.md"
        resume_path_out = os.path.join(OUTPUT_DIR, resume_fn)
        cover_path_out = os.path.join(OUTPUT_DIR, cover_fn)
        with open(resume_path_out, 'w') as f:
            f.write(tailored_md)
        with open(cover_path_out, 'w') as f:
            f.write(cover_md)

        return {
            'resume_download_url': f"/download-resume?file={resume_fn}",
            'cover_letter_download_url': f"/download-cover-letter?file={cover_fn}"
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

@app.get('/download-resume')
async def download_resume(file: str):
    path = os.path.join(OUTPUT_DIR, file)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type='text/markdown', filename=file)

@app.get('/download-cover-letter')
async def download_cover_letter(file: str):
    path = os.path.join(OUTPUT_DIR, file)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type='text/markdown', filename=file)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
