from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
import os
import PyPDF2
import pdfplumber
from docx import Document
import openai
from pydantic import BaseModel
from typing import List, Dict, Optional
import uuid
import io
import base64
from datetime import datetime

app = FastAPI()

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY
UPLOAD_DIR = 'uploads'
OUTPUT_DIR = 'outputs'

# Ensure directories exist
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

# File storage
file_storage = {}

# Helper functions
def extract_text_from_pdf(file: UploadFile) -> str:
    """Extract text from a PDF file."""
    text = ""
    with file.file as f:
        pdf_reader = PyPDF2.PdfReader(f)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def extract_text_from_docx(file: UploadFile) -> str:
    """Extract text from a DOCX file."""
    text = ""
    doc = Document(file.file)
    for para in doc.paragraphs:
        text += para.text + '\n'
    return text

def extract_text_from_file(file: UploadFile) -> str:
    """Extract text from a file based on its type."""
    if file.filename.endswith('.pdf'):
        return extract_text_from_pdf(file)
    elif file.filename.endswith('.docx'):
        return extract_text_from_docx(file)
    else:
        return file.file.read().decode('utf-8')

# AI agents
def parse_resume(text: str) -> ResumeData:
    """Parse resume text into structured data using an AI model."""
    # Simulate AI parsing
    # In a real implementation, this would use an LLM to parse the text
    # For this example, we'll return a dummy structure
    return ResumeData(
        name="John Doe",
        email="john.doe@example.com",
        phone="(123) 456-7890",
        summary="Experienced software developer with a passion for building scalable applications.",
        work_experience=[
            {
                "company": "Tech Corp",
                "title": "Senior Software Engineer",
                "dates": "2018 - Present",
                "responsibilities": [
                    "Developed and maintained scalable web applications",
                    "Led a team of 5 developers",
                    "Implemented CI/CD pipelines"
                ]
            }
        ],
        education=[
            {
                "institution": "University of Tech",
                "degree": "Bachelor of Science in Computer Science",
                "dates": "2014 - 2018"
            }
        ],
        skills=["Python", "JavaScript", "React", "Node.js", "AWS"],
        projects=[
            {
                "title": "E-commerce Platform",
                "description": "Built a scalable e-commerce platform using React and Node.js"
            }
        ],
        certifications=["AWS Certified Developer"],
        other=[
            {
                "title": "Open Source Contributor",
                "description": "Contributed to several open source projects on GitHub"
            }
        ]
    )

def analyze_job_description(text: str) -> JobDescription:
    """Analyze job description text to extract key requirements."""
    # Simulate AI analysis
    # In a real implementation, this would use an LLM to analyze the text
    # For this example, we'll return a dummy structure
    return JobDescription(
        required_skills=["Python", "Django", "REST APIs"],
        preferred_skills=["AWS", "React"],
        experience_years=3,
        responsibilities=[
            "Develop RESTful APIs",
            "Design and implement scalable web services",
            "Collaborate with cross-functional teams"
        ],
        company_culture="Innovative and collaborative environment"
    )

def generate_tailored_resume(resume_data: ResumeData, job_description: JobDescription) -> str:
    """Generate a tailored resume based on the user's data and job description."""
    # Simulate resume generation
    # In a real implementation, this would use an LLM to generate the resume
    # For this example, we'll return a dummy Markdown resume
    return "## John Doe\n\n**Email:** john.doe@example.com | **Phone:** (123) 456-7890\n\n### Summary\nExperienced software developer with a passion for building scalable applications.\n\n### Skills\n- Python\n- JavaScript\n- React\n- Node.js\n- AWS\n\n### Experience\n**Senior Software Engineer** - Tech Corp (2018 - Present)\n- Developed and maintained scalable web applications\n- Led a team of 5 developers\n- Implemented CI/CD pipelines\n\n### Education\n**Bachelor of Science in Computer Science** - University of Tech (2014 - 2018)\n\n### Projects\n**E-commerce Platform**\nBuilt a scalable e-commerce platform using React and Node.js\n\n### Certifications\n- AWS Certified Developer\n\n### Other\n**Open Source Contributor**\nContributed to several open source projects on GitHub"

def generate_cover_letter(resume_data: ResumeData, job_description: JobDescription) -> str:
    """Generate a cover letter based on the user's data and job description."""
    # Simulate cover letter generation
    # In a real implementation, this would use an LLM to generate the cover letter
    # For this example, we'll return a dummy cover letter
    return "Dear Hiring Manager,\n\nI am writing to apply for the Senior Software Engineer position at Tech Corp. With my experience in developing scalable web applications and leading teams, I am confident that I am a strong fit for this role.\n\nMy background in Python, Django, and REST APIs aligns well with the requirements of the position. I am particularly drawn to Tech Corp's innovative and collaborative environment, and I am excited about the opportunity to contribute to your team.\n\nThank you for considering my application. I look forward to the possibility of discussing my qualifications further.\n\nSincerely,\nJohn Doe"

# API endpoints
@app.post('/upload-resume')
async def upload_resume(files: List[UploadFile] = File(...)):
    """Upload resume and other files."""
    file_ids = []
    for file in files:
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, file_id + os.path.splitext(file.filename)[1])
        with open(file_path, 'wb') as f:
            f.write(await file.read())
        file_storage[file_id] = file_path
        file_ids.append(file_id)
    return {'file_ids': file_ids}

@app.post('/generate')
async def generate_resume_and_cover_letter(
    resume_file_id: str = Form(...),
    job_description: str = Form(...)
):
    """Generate tailored resume and cover letter."""
    if resume_file_id not in file_storage:
        raise HTTPException(status_code=404, detail="Resume file not found")

    resume_file_path = file_storage[resume_file_id]
    with open(resume_file_path, 'rb') as f:
        resume_text = f.read().decode('utf-8')

    resume_data = parse_resume(resume_text)
    job_description_data = analyze_job_description(job_description)

    tailored_resume = generate_tailored_resume(resume_data, job_description_data)
    cover_letter = generate_cover_letter(resume_data, job_description_data)

    # Save outputs
    resume_output_path = os.path.join(OUTPUT_DIR, f"resume_{datetime.now().strftime('%Y%m%d%H%M%S')}.md")
    cover_letter_output_path = os.path.join(OUTPUT_DIR, f"cover_letter_{datetime.now().strftime('%Y%m%d%H%M%S')}.md")

    with open(resume_output_path, 'w') as f:
        f.write(tailored_resume)
    with open(cover_letter_output_path, 'w') as f:
        f.write(cover_letter)

    return {
        'resume_download_url': f"/download-resume?file={os.path.basename(resume_output_path)}",
        'cover_letter_download_url': f"/download-cover-letter?file={os.path.basename(cover_letter_output,)}"
    }

@app.get('/download-resume')
async def download_resume(file: str):
    """Download the generated resume."""
    file_path = os.path.join(OUTPUT_DIR, file)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@app.get('/download-cover-letter')
async def download_cover_letter(file: str):
    """Download the generated cover letter."""
    file_path = os.path.join(OUTPUT_DIR, file)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)

# Created by AI