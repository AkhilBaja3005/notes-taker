import os
import sys
import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from git_sync import sync_notes_to_git

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
LECTURES_DIR = Path(os.environ.get("LECTURES_DIR", "./lectures"))
LECTURES_DIR.mkdir(parents=True, exist_ok=True)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash")

SUPPORTED_AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".flac", ".wma"}
SUPPORTED_DOC_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md", ".pptx", ".ppt"}
SUPPORTED_EXTS = SUPPORTED_AUDIO_EXTS.union(SUPPORTED_DOC_EXTS)

def extract_text_from_docx(file_path: Path) -> str:
    try:
        import docx
        doc = docx.Document(str(file_path))
        return "\n".join([p.text for p in doc.paragraphs if p.text])
    except Exception as e:
        print(f"[!] Warning: docx parsing error: {e}")
        return ""

def process_file(file_path_str: str, course_name: str, topic_name: str, lecture_date: str = None, model: str = None) -> Path:
    if lecture_date is None:
        lecture_date = datetime.date.today().isoformat()
    if model is None:
        model = GEMINI_MODEL

    file_path = Path(file_path_str)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path_str}")

    suffix = file_path.suffix.lower()
    is_audio = suffix in SUPPORTED_AUDIO_EXTS
    content_type_label = "audio recording" if is_audio else "academic document/slides"

    prompt = f"""
    You are an expert academic tutor for a graduate-level STEM curriculum.
    Analyze the provided {content_type_label} for:
    - Course: "{course_name}"
    - Topic: "{topic_name}"

    Generate your response in standard Markdown (compatible with Obsidian math & callouts) using EXACTLY the following structure:
    
    # {course_name}: {topic_name}
    
    ## 1. Executive Summary
    - 3 to 5 concise bullet points capturing the core conceptual thesis.
    
    ## 2. Mathematical Definitions, Derivations & Proofs
    - Render every equation, variable, and proof in clean standard LaTeX ($...$ for inline, $$...$$ for display).
    - Clearly define state variables, objective functions, and boundary conditions.
    
    ## 3. High-Yield Exam Notes & Professor Emphasis
    > [!WARNING] Exam Pitfalls & Professor Warnings
    > - Highlight direct warnings, potential exam questions, and common conceptual traps.
    
    ## 4. Key Concept Q&A Flashcards
    - 5 to 8 rigorous conceptual check questions in Question/Answer format.
    
    ## 5. Chronological / Sectional Breakdown
    - A detailed, readable breakdown with timestamps [HH:MM:SS] (for audio) or Section/Slide references (for documents).
    """

    uploaded_remote_file = None
    contents_payload = []

    if suffix in [".docx", ".doc"]:
        text_content = extract_text_from_docx(file_path)
        if not text_content.strip():
            print(f"[*] Uploading {file_path.name} to Gemini File API...")
            uploaded_remote_file = client.files.upload(file=str(file_path))
            contents_payload = [uploaded_remote_file, prompt]
        else:
            contents_payload = [f"Document Content for {file_path.name}:\n\n{text_content}", prompt]
    elif suffix in [".txt", ".md"]:
        text_content = file_path.read_text(encoding="utf-8", errors="ignore")
        contents_payload = [f"Document Content for {file_path.name}:\n\n{text_content}", prompt]
    else:
        print(f"[*] Uploading {file_path.name} to Gemini File API...")
        uploaded_remote_file = client.files.upload(file=str(file_path))
        contents_payload = [uploaded_remote_file, prompt]

    print(f"[*] Processing material through Gemini ({model})...")
    response = client.models.generate_content(
        model=model,
        contents=contents_payload
    )

    clean_course_tag = course_name.replace(" ", "")
    clean_topic_tag = topic_name.replace(" ", "")

    file_content = f"""---
date: {lecture_date}
course: "[[{course_name}]]"
topic: "[[{topic_name}]]"
source_file: "{file_path.name}"
model_used: "{model}"
tags:
  - course/{clean_course_tag}
  - topic/{clean_topic_tag}
  - graduate-notes
---

{response.text}
"""

    safe_course = course_name.strip().replace(" ", "_")
    safe_topic = topic_name.strip().replace(" ", "_")
    output_filename = LECTURES_DIR / f"{lecture_date}_{safe_course}_{safe_topic}.md"
    
    output_filename.write_text(file_content, encoding="utf-8")
    print(f"[+] Successfully saved structured notes to: {output_filename}")
    
    # Auto-commit & push to Git repository for Obsidian sync
    try:
        commit_msg = f"Auto-sync note: {safe_course} - {safe_topic} ({lecture_date})"
        sync_notes_to_git(commit_msg)
    except Exception as e:
        print(f"[!] Warning: Git auto-sync failed: {e}")

    # Cleanup remote file
    if uploaded_remote_file:
        try:
            client.files.delete(name=uploaded_remote_file.name)
        except Exception as e:
            print(f"[!] Warning: Remote file deletion failed: {e}")

    return output_filename

process_audio_file = process_file

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python ingest_audio.py <file_path> <course_name> <topic_name> [YYYY-MM-DD] [model_name]")
    else:
        arg_file = sys.argv[1]
        arg_course = sys.argv[2]
        arg_topic = sys.argv[3]
        arg_date = sys.argv[4] if len(sys.argv) > 4 else None
        arg_model = sys.argv[5] if len(sys.argv) > 5 else None
        process_file(arg_file, arg_course, arg_topic, arg_date, arg_model)
