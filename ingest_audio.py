import os
import sys
import io
import contextlib
import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from git_sync import sync_notes_to_git
from anki_exporter import generate_anki_deck_from_file
from obsidian_moc import update_all_course_mocs
from metadata_db import index_lecture_file
from vector_store import index_file_in_vector_db
from audio_optimizer import optimize_audio_file
from core_engine import clean_and_repair_latex

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
LECTURES_DIR = Path(os.environ.get("LECTURES_DIR", "./lectures"))
LECTURES_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_AUDIO_MODEL = os.environ.get("AUDIO_MODEL", "gemini-3.6-flash")
DEFAULT_DOC_MODEL = os.environ.get("DOC_MODEL", "gemini-3.1-flash-lite")
DEFAULT_DENSE_MODEL = os.environ.get("DENSE_MATH_MODEL", "gemini-3.6-flash")

AUDIO_FALLBACKS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest"
]
DOC_FALLBACKS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.6-flash",
    "gemini-3.5-flash"
]

SUPPORTED_AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".flac", ".wma"}
SUPPORTED_DOC_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md", ".pptx", ".ppt"}
SUPPORTED_EXTS = SUPPORTED_AUDIO_EXTS.union(SUPPORTED_DOC_EXTS)

MIME_TYPE_MAP = {
    ".m4a": "audio/mp4",
    ".mp3": "audio/mp3",
    ".wav": "audio/wav",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".wma": "audio/x-ms-wma",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

def get_optimal_model_for_file(file_path: Path, is_dense_math: bool = False) -> tuple[str, list[str]]:
    suffix = file_path.suffix.lower()
    if suffix in SUPPORTED_AUDIO_EXTS:
        return DEFAULT_AUDIO_MODEL, AUDIO_FALLBACKS
    elif is_dense_math:
        return DEFAULT_DENSE_MODEL, AUDIO_FALLBACKS
    else:
        return DEFAULT_DOC_MODEL, DOC_FALLBACKS

def extract_text_from_docx(file_path: Path) -> str:
    try:
        import docx
        doc = docx.Document(str(file_path))
        return "\n".join([p.text for p in doc.paragraphs if p.text])
    except Exception as e:
        print(f"[!] Warning: docx parsing error: {e}")
        return ""

def process_file(file_path_str: str, course_name: str, topic_name: str, lecture_date: str = None, model: str = None, is_dense_math: bool = False) -> Path:
    if lecture_date is None:
        lecture_date = datetime.date.today().isoformat()

    file_path = Path(file_path_str)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path_str}")

    # Sanitize unicode characters in filename (e.g. iOS narrow no-break space \u202f in timestamped recordings)
    clean_stem = "".join([c if ord(c) < 128 and (c.isalnum() or c in ("-", "_", ".", " ")) else "_" for c in file_path.stem]).strip()
    if clean_stem != file_path.stem:
        new_path = file_path.parent / f"{clean_stem}{file_path.suffix}"
        try:
            file_path.rename(new_path)
            file_path = new_path
        except Exception:
            pass

    suffix = file_path.suffix.lower()
    is_audio = suffix in SUPPORTED_AUDIO_EXTS

    # 1. Automatic Audio Pre-Optimization
    actual_upload_path = file_path
    if is_audio:
        try:
            opt_parts = optimize_audio_file(file_path)
            if opt_parts:
                actual_upload_path = opt_parts[0]
        except Exception as e:
            print(f"[!] Audio optimizer notice: {e}")

    content_type_label = "audio recording" if is_audio else ("dense mathematical document" if is_dense_math else "academic slides/document")

    if model is None:
        selected_model, fallback_pool = get_optimal_model_for_file(file_path, is_dense_math)
    else:
        selected_model = model
        fallback_pool = AUDIO_FALLBACKS if is_audio else DOC_FALLBACKS

    prompt = f"""
    You are an expert academic tutor for a graduate-level STEM curriculum.
    Analyze the provided {content_type_label} for:
    - Course: "{course_name}"
    - Topic: "{topic_name}"

    [ACOUSTIC ADAPTATION & ACCENT PRIMING INSTRUCTIONS]:
    - Normalize diverse international accents and room reverberation.
    - Accurately identify technical domain terminology, Greek notations, and vector calculus proofs without phonetic hallucination.

    Generate your response in standard Markdown (compatible with Obsidian math, Mermaid diagrams & callouts) using EXACTLY the following structure:
    
    # {course_name}: {topic_name}
    
    ## 1. Executive Summary & Conceptual Mind Map
    - 3 to 5 concise bullet points capturing the core conceptual thesis.
    
    ```mermaid
    graph TD
        A[{topic_name}] --> B[Core Concept 1]
        A --> C[Core Concept 2]
        B --> D[Theorem / Result]
        C --> E[Application / Metric]
    ```
    
    ## 2. Mathematical Definitions, Derivations & Proofs
    - Render every equation, variable, and proof in clean standard LaTeX ($...$ for inline, $$...$$ for display).
    - If writing multi-line aligned equations with '&' and '\\\\', always wrap inside '$$\\begin{{aligned}} ... \\end{{aligned}}$$'.
    - Clearly define state variables, objective functions, and boundary conditions.
    
    ## 3. High-Yield Exam Notes & Professor Emphasis
    > [!WARNING] Exam Pitfalls & Professor Warnings
    > - Highlight direct warnings, potential exam questions, and common conceptual traps.
    
    ## 4. Key Concept Q&A Flashcards
    - 5 to 8 rigorous conceptual check questions in Question/Answer format (e.g. **Q1: Question?** and **A1:** Answer).
    
    ## 5. Chronological / Sectional Breakdown
    - A detailed, readable breakdown with timestamps [HH:MM:SS] (for audio) or Section/Slide references (for documents).
    """

    uploaded_remote_file = None
    upload_mime = MIME_TYPE_MAP.get(actual_upload_path.suffix.lower())
    upload_config = {"mime_type": upload_mime} if upload_mime else None

    if suffix in [".docx", ".doc"]:
        text_content = extract_text_from_docx(file_path)
        if not text_content.strip():
            print(f"[*] Uploading {file_path.name} to Gemini File API (mime: {upload_mime})...")
            with contextlib.redirect_stderr(io.StringIO()):
                if upload_config:
                    uploaded_remote_file = client.files.upload(file=str(actual_upload_path), config=upload_config)
                else:
                    uploaded_remote_file = client.files.upload(file=str(actual_upload_path))
            contents_payload = [uploaded_remote_file, prompt]
        else:
            contents_payload = [f"Document Content for {file_path.name}:\n\n{text_content}", prompt]
    elif suffix in [".txt", ".md"]:
        text_content = file_path.read_text(encoding="utf-8", errors="ignore")
        contents_payload = [f"Document Content for {file_path.name}:\n\n{text_content}", prompt]
    else:
        print(f"[*] Uploading {actual_upload_path.name} to Gemini File API (mime: {upload_mime})...")
        with contextlib.redirect_stderr(io.StringIO()):
            if upload_config:
                uploaded_remote_file = client.files.upload(file=str(actual_upload_path), config=upload_config)
            else:
                uploaded_remote_file = client.files.upload(file=str(actual_upload_path))
        contents_payload = [uploaded_remote_file, prompt]

    candidate_models = [selected_model] + [m for m in fallback_pool if m != selected_model]
    response = None
    last_err = None

    for candidate in candidate_models:
        try:
            print(f"[*] Processing material through Gemini ({candidate})...")
            with contextlib.redirect_stderr(io.StringIO()):
                response = client.models.generate_content(
                    model=candidate,
                    contents=contents_payload
                )
            selected_model = candidate
            break
        except Exception as err:
            print(f"[!] Warning: {candidate} error: {err}. Retrying with next model...")
            last_err = err

    if response is None:
        raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")

    raw_text = clean_and_repair_latex(response.text)
    clean_course_tag = course_name.replace(" ", "")
    clean_topic_tag = topic_name.replace(" ", "")

    file_content = f"""---
date: {lecture_date}
course: "[[{course_name}]]"
topic: "[[{topic_name}]]"
source_file: "{file_path.name}"
model_used: "{selected_model}"
tags:
  - course/{clean_course_tag}
  - topic/{clean_topic_tag}
  - graduate-notes
---

{raw_text}
"""

    safe_course = course_name.strip().replace(" ", "_")
    safe_topic = topic_name.strip().replace(" ", "_")
    output_filename = LECTURES_DIR / f"{lecture_date}_{safe_course}_{safe_topic}.md"
    
    output_filename.write_text(file_content, encoding="utf-8")
    print(f"[+] Successfully saved structured notes to: {output_filename}")
    
    # 2. Automated Pipeline Extensions
    try:
        generate_anki_deck_from_file(output_filename)
        update_all_course_mocs(LECTURES_DIR)
        index_lecture_file(output_filename)
        index_file_in_vector_db(output_filename)
    except Exception as e:
        print(f"[!] Warning: Pipeline extension index notice: {e}")

    # 3. Git Auto-sync to my-obsidian-notes repo
    try:
        commit_msg = f"Auto-sync note: {safe_course} - {safe_topic} ({lecture_date})"
        sync_notes_to_git(commit_msg)
    except Exception as e:
        print(f"[!] Warning: Git auto-sync failed: {e}")

    if uploaded_remote_file:
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                client.files.delete(name=uploaded_remote_file.name)
        except Exception as e:
            print(f"[!] Warning: Remote file deletion failed: {e}")

    return output_filename

process_audio_file = process_file

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python ingest_audio.py <file_path> <course_name> <topic_name> [YYYY-MM-DD] [model_name] [--dense-math]")
    else:
        arg_file = sys.argv[1]
        arg_course = sys.argv[2]
        arg_topic = sys.argv[3]
        arg_date = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else None
        arg_model = sys.argv[5] if len(sys.argv) > 5 and not sys.argv[5].startswith("--") else None
        is_dense = "--dense-math" in sys.argv
        process_file(arg_file, arg_course, arg_topic, arg_date, arg_model, is_dense_math=is_dense)
