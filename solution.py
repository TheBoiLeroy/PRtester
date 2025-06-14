# app.py
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
# For qwen3 via Ollama
from langchain_ollama import ChatOllama

# For LlamaParse
from llama_cloud_services import LlamaParse


load_dotenv()
# Initialize LlamaParse
api_key = os.getenv("LLAMA_CLOUD_API_KEY")

if not api_key:
    raise ValueError("Set LLAMA_CLOUD_API_KEY in environment")

parser = LlamaParse(api_key=api_key)

app = FastAPI()

# Configuration
UPLOAD_DIR = 'uploads'
OUTPUT_DIR = 'outputs'
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Pydantic models
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

# In-memory mapping of file IDs to paths
file_storage: Dict[str, str] = {}

# Initialize local qwen3 LLM via Ollama
def get_llm():
    # Ensure qwen3 is pulled locally: `ollama pull qwen3`
    return ChatOllama(model="qwen3", temperature=0)

# Parse resume via LlamaParse
def parse_resume_with_llama(file_bytes: bytes, filename: str) -> ResumeData:
    """
    Send resume bytes to LlamaParse via load_data + get_json_result(tmp_path),
    then map into ResumeData.
    """
    try:
        # Write bytes to a temp file with same extension
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        print("[DEBUG] Calling parser.load_data on temp file:", tmp_path)
        parser.load_data(tmp_path)

        print("[DEBUG] Calling parser.get_json_result with file_path:", tmp_path)
        parsed_json = parser.get_json_result(file_path=tmp_path)
        print("[DEBUG] Raw parsed_json from LlamaParse:", parsed_json)

        # Cleanup temp file
        try:
            os.remove(tmp_path)
        except Exception:
            pass

        # Map parsed_json keys to ResumeData fields if needed.
        # Inspect parsed_json structure in logs; adjust mapping if keys differ.
        # Example (if parsed_json already matches):
        rd = ResumeData.model_validate(parsed_json)
        return rd

    except Exception as e:
        print("[ERROR] parse_resume_with_llama exception:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"LlamaParse failed: {e}")
    
# Use qwen3 to analyze job description
def analyze_job_description(text: str) -> JobDescription:
    llm = get_llm()
    system_prompt = (
        "You are a job description analysis assistant. "
        "Given raw job description text, extract into JSON with exactly these fields:\n"
        "- required_skills: list of strings\n"
        "- preferred_skills: list of strings\n"
        "- experience_years: integer (minimum years of experience)\n"
        "- responsibilities: list of strings\n"
        "- company_culture: string or null\n"
        "Respond with valid JSON only."
    )
    user_prompt = f"Job description text:\n\"\"\"{text}\"\"\""
    ai_msg = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])
    if hasattr(ai_msg, "content"):
        response_text = ai_msg.content
    else:
        response_text = str(ai_msg)
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("```").strip()
        try:
            parsed = json.loads(cleaned)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse JD JSON: {e}\nResponse: {response_text}")
    try:
        jd = JobDescription.parse_obj(parsed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsed JD JSON invalid: {e}\nJSON: {parsed}")
    return jd

# Use qwen3 to generate tailored resume markdown
def generate_tailored_resume(resume_data: ResumeData, job_description: JobDescription) -> str:
    llm = get_llm()
    system_prompt = (
        "You are a resume generator. Given JSON of user resume data and JSON of job description data, "
        "produce a tailored resume in Markdown format. "
        "Structure with headings: Name & Contact, Summary, Skills, Experience, Education, Projects, Certifications, Other. "
        "Emphasize alignment: reorder or rephrase bullet points to match required_skills and responsibilities, "
        "highlight metrics if present. "
        "Output only the Markdown text."
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
    if hasattr(ai_msg, "content"):
        return ai_msg.content
    return str(ai_msg)

# Use qwen3 to generate cover letter
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
    if hasattr(ai_msg, "content"):
        return ai_msg.content
    return str(ai_msg)

# Endpoint: upload resume file
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

# Endpoint: generate tailored resume & cover letter
@app.post('/generate')
async def generate_resume_and_cover_letter(
    resume_file_id: str = Form(...),
    job_description: str = Form(...)
):
    try:
        if resume_file_id not in file_storage:
            raise HTTPException(status_code=404, detail="Resume file not found")
        # Read file bytes
        resume_path = file_storage[resume_file_id]
        with open(resume_path, 'rb') as f:
            data = f.read()
        # Parse via LlamaParse
        print("[DEBUG] Calling parse_resume_with_llama")
        resume_data = parse_resume_with_llama(data, os.path.basename(resume_path))
        print("[DEBUG] parse_resume_with_llama succeeded:", resume_data)
        # Analyze JD
        print("[DEBUG] Calling analyze_job_description")
        jd_data = analyze_job_description(job_description)
        print("[DEBUG] analyze_job_description succeeded:", jd_data)
        # Generate resume
        print("[DEBUG] Calling generate_tailored_resume")
        tailored_md = generate_tailored_resume(resume_data, jd_data)
        print("[DEBUG] tailored resume preview:\n", tailored_md[:200])
        # Generate cover letter
        print("[DEBUG] Calling generate_cover_letter")
        cover_md = generate_cover_letter(resume_data, jd_data)
        print("[DEBUG] cover letter preview:\n", cover_md[:200])
        # Save outputs
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

# Download endpoints
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