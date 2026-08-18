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

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
LECTURES_DIR = Path(os.environ.get("LECTURES_DIR", "./lectures"))
LECTURES_DIR.mkdir(parents=True, exist_ok=True)

# Tiered Model Architecture
DEFAULT_AUDIO_MODEL = os.environ.get("AUDIO_MODEL", "gemini-3.6-flash")
DEFAULT_DOC_MODEL = os.environ.get("DOC_MODEL", "gemini-3.1-flash-lite")
DEFAULT_DENSE_MODEL = os.environ.get("DENSE_MATH_MODEL", "gemini-3.6-flash")

AUDIO_FALLBACKS = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
DOC_FALLBACKS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.6-flash"]

SUPPORTED_AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".flac", ".wma"}
SUPPORTED_DOC_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md", ".pptx", ".ppt"}
SUPPORTED_EXTS = SUPPORTED_AUDIO_EXTS.union(SUPPORTED_DOC_EXTS)

def get_optimal_model_for_file(file_path: Path, is_dense_math: bool = False) -> tuple[str, list[str]]:
    """
    Intelligently routes files to the optimal model based on workload:
    - Audio (Ambient Hall Acoustic / Spoken Math) -> Gemini Flash (3.6-flash / 3.5-flash)
    - Clean Slides / Typed Text / Docs           -> Gemini Flash-Lite (3.1-flash-lite / 3.5-flash-lite)
    - Hand-Annotated / Dense Math Papers         -> Gemini Flash (3.6-flash)
    """
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

    suffix = file_path.suffix.lower()
    is_audio = suffix in SUPPORTED_AUDIO_EXTS
    content_type_label = "audio recording" if is_audio else ("dense mathematical document" if is_dense_math else "academic slides/document")

    # Dynamic tiered model selection
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

    Generate your response in standard Markdown (compatible with Obsidian math & callouts) using EXACTLY the following structure:
    
    # {course_name}: {topic_name}
    
    ## 1. Executive Summary
    - 3 to 5 concise bullet points capturing the core conceptual thesis.
    
    ## 2. Mathematical Definitions, Derivations & Proofs
    - Render every equation, variable, and proof in clean standard LaTeX ($...$ for inline, $$...$$ for display).
    - If writing multi-line aligned equations with '&' and '\\\\', always wrap inside '$$\\begin{{aligned}} ... \\end{{aligned}}$$'.
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
            with contextlib.redirect_stderr(io.StringIO()):
                uploaded_remote_file = client.files.upload(file=str(file_path))
            contents_payload = [uploaded_remote_file, prompt]
        else:
            contents_payload = [f"Document Content for {file_path.name}:\n\n{text_content}", prompt]
    elif suffix in [".txt", ".md"]:
        text_content = file_path.read_text(encoding="utf-8", errors="ignore")
        contents_payload = [f"Document Content for {file_path.name}:\n\n{text_content}", prompt]
    else:
        print(f"[*] Uploading {file_path.name} to Gemini File API...")
        with contextlib.redirect_stderr(io.StringIO()):
            uploaded_remote_file = client.files.upload(file=str(file_path))
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

{response.text}
"""

    safe_course = course_name.strip().replace(" ", "_")
    safe_topic = topic_name.strip().replace(" ", "_")
    output_filename = LECTURES_DIR / f"{lecture_date}_{safe_course}_{safe_topic}.md"
    
    output_filename.write_text(file_content, encoding="utf-8")
    print(f"[+] Successfully saved structured notes to: {output_filename}")
    
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
