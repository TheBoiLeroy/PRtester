## Overview
- **Goal**: Let a user upload their current resume + any extra files (e.g., portfolio details, personal bio), then upload a job description. The system uses AI “agents” (modular steps) to:
  1. Parse the user’s resume/data.
  2. Analyze the job description.
  3. Generate a tailored resume.
  4. Generate a matching cover letter.
- **Approach**:
  - Frontend for file upload + inputs.
  - Backend to extract text, orchestrate AI calls, and return results (e.g., downloadable PDF/DOCX or plain text).
  - AI “agents” = modular functions or chains that handle parsing, matching, generation.

## Architecture & Components

### Frontend UI
- File upload widget (resume file(s), extra docs).
- Text area or file upload for job description.
- “Generate” button.
- Display area / download links for generated resume & cover letter.

### Backend API
- Endpoints:
  - `POST /upload-resume` → accept files, store temporarily.
  - `POST /generate` → take references to uploaded files and job description text; run pipeline; return outputs.

### File Handling & Text Extraction
- Accept common resume formats: PDF, DOCX, maybe plain text.
- Use libraries:
  - PDF: PyPDF2 or pdfplumber.
  - DOCX: python-docx.
- Extract full text from each uploaded file.

### Data Parsing Agent
- Input: raw text from resume + any extra user files.
- Task: extract structured info:
  - Contact info (name, email, phone).
  - Professional summary / objective (if present).
  - Work experience entries: company, title, dates, bullet points.
  - Education.
  - Skills (hard/soft).
  - Projects, certifications, etc.
  - Extra: volunteer, publications, etc.
- Implementation:
  - Use LLM to parse into a predefined JSON schema via prompt instructing “output JSON only”.

### Job Description Analyzer Agent
- Input: job description text.
- Task: extract key requirements & preferences:
  - Required skills, preferred skills, years of experience.
  - Responsibilities.
  - Company values / mission hints.
- Implementation:
  - LLM prompt: “Extract from this JD: a list of required skills, preferred skills, years of experience expectations, main responsibilities, any company culture hints.”

### Matching & Prioritization Logic
- Input: parsed resume JSON + parsed JD JSON.
- Task: determine which experiences/skills to emphasize, reorder bullet points, rephrase achievements to align with JD keywords.
- Implementation:
  - Often folded into the resume-generation prompt: feed both JSONs into LLM with instructions to highlight overlaps and rewrite bullets accordingly.

### Resume Generator Agent
- Input: structured user data + JD insights + matching guidance.
- Task: produce a formatted resume draft:
  - Preserve or apply a template.
  - Rephrase bullet points, reorder sections.
- Implementation:
  - Prompt: “Using this JSON of user background and this JSON of JD insights, generate a resume in Markdown. Sections: Name & Contact, Summary, Skills, Experience, Education, Projects, Certifications, Other.”

### Cover Letter Generator Agent
- Input: user’s background summary, JD insights (role, company, key responsibilities), optional personal motivations.
- Task: produce personalized cover letter:
  - Address hiring manager (or generic).
  - Explain why user is interested, highlight matching experiences/skills, closing.
- Implementation:
  - Prompt: “Write a cover letter for [Role] at [Company] based on user’s background JSON and JD JSON. Tone: professional but conversational.”

### Formatting & Export
- Generated Markdown can be rendered or converted:
  - To DOCX via python-docx (e.g., parse Markdown headings/bullets).
  - To PDF via converting DOCX or using HTML+WeasyPrint.
- Alternatively, return raw Markdown for user editing.

### Security & Privacy
- Handle resume/cover letter data securely: delete files after generation or store encrypted.
- Don’t log sensitive info in plain-text logs.
- Use HTTPS for uploads.
- Secure API endpoints if deployed publicly (auth, rate limits).

### Orchestration / Agent Framework
- Simple: chain function calls sequentially.
- Advanced: use LangChain or similar:
  - Define tools: parse_resume, analyze_jd, generate_resume, generate_cover_letter.
  - Chain them or let an agent orchestrate.

## Tech Stack & Dependencies
- **Backend**: Python (FastAPI or Flask).
- **Frontend**:
  - React/Next.js with file upload component; calls backend API.
  - Or Streamlit prototype for quick testing.
- **AI API**: OpenAI or other LLM provider.
- **File parsing**:
  - `python-docx`, `PyPDF2` or `pdfplumber`.
- **Document generation**:
  - `python-docx` for .docx.
  - PDF conversion via WeasyPrint or other.
- **Prompt templates**: stored in files or code.
- **Environment variables**: API keys, storage paths.
- **Storage**: Temporary local storage or cloud (S3) if deployed.
- **Optional**: LangChain for chaining, pydantic for schemas.

## Step-by-Step Implementation

### 1. Setup Environment
```bash
pip install fastapi uvicorn python-docx PyPDF2 pdfplumber openai pydantic
# If using LangChain:
pip install langchain
# If using Streamlit prototype:
pip install streamlit
