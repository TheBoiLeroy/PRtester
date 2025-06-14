
import streamlit as st
import requests
import os

# Configuration: adjust if backend is running on a different host/port
BACKEND_URL = st.sidebar.text_input("Backend URL", value="http://127.0.0.1:8000")

st.title("AI Resume & Cover Letter Generator")

st.markdown("Upload your resume (PDF or DOCX) and enter the job description to generate a tailored resume and cover letter.")

# File uploader
uploaded_file = st.file_uploader("Choose your resume file", type=["pdf", "docx", "txt"])

# Job description input
job_description = st.text_area("Paste the job description here")

if st.button("Generate"):
    if not uploaded_file:
        st.error("Please upload a resume file.")
    elif not job_description.strip():
        st.error("Please enter a job description.")
    else:
        # Upload resume file to backend
        with st.spinner("Uploading resume..."):
            files = {"files": (uploaded_file.name, uploaded_file.getvalue())}
            try:
                resp = requests.post(f"{BACKEND_URL}/upload-resume", files=files)
                resp.raise_for_status()
                file_ids = resp.json().get("file_ids", [])
                if not file_ids:
                    st.error("No file ID returned from upload.")
                    st.stop()
                resume_file_id = file_ids[0]
            except Exception as e:
                st.error(f"Upload failed: {e}")
                st.stop()

        # Generate tailored resume & cover letter
        with st.spinner("Generating tailored resume and cover letter..."):
            data = {"resume_file_id": resume_file_id, "job_description": job_description}
            try:
                resp2 = requests.post(f"{BACKEND_URL}/generate", data=data)
                resp2.raise_for_status()
                result = resp2.json()
            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()

        # Display results
        resume_url = result.get("resume_download_url")
        cover_url = result.get("cover_letter_download_url")
        if resume_url:
            st.markdown("### Generated Resume")
            # Fetch and display markdown
            try:
                r = requests.get(f"{BACKEND_URL}{resume_url}")
                if r.status_code == 200:
                    st.code(r.text, language="markdown")
                    st.markdown(f"[Download Resume]({BACKEND_URL}{resume_url})")
                else:
                    st.error("Failed to download generated resume.")
            except Exception as e:
                st.error(f"Error fetching resume: {e}")
        if cover_url:
            st.markdown("### Generated Cover Letter")
            try:
                r2 = requests.get(f"{BACKEND_URL}{cover_url}")
                if r2.status_code == 200:
                    st.code(r2.text, language="markdown")
                    st.markdown(f"[Download Cover Letter]({BACKEND_URL}{cover_url})")
                else:
                    st.error("Failed to download generated cover letter.")
            except Exception as e:
                st.error(f"Error fetching cover letter: {e}")
