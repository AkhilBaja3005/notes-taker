import os
import datetime
from pathlib import Path
import frontmatter
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Prioritize highly available and stable Flash models (excluding 3.7)
SUPPORTED_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite"
]

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
LECTURES_DIR = Path(os.environ.get("LECTURES_DIR", "./lectures"))

def generate_with_fallback(prompt: str, system_instruction: str = None, requested_model: str = None) -> str:
    """Robust generator with automatic fallback across stable Gemini Flash models."""
    if requested_model is None or requested_model == "gemini-3.7-flash":
        requested_model = DEFAULT_MODEL

    candidate_models = [requested_model] + [m for m in SUPPORTED_MODELS if m != requested_model]
    last_err = None

    for model_name in candidate_models:
        try:
            config_kwargs = {}
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction
                
            config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            print(f"[!] Warning: Model {model_name} failed with: {e}. Retrying with next available model...")
            last_err = e

    raise RuntimeError(f"All Gemini models were unavailable or busy. Last error: {last_err}")

def get_available_courses() -> list[str]:
    courses = set()
    for file_path in LECTURES_DIR.glob("*.md"):
        try:
            post = frontmatter.load(file_path)
            if "course" in post:
                raw_c = str(post["course"]).replace("[[", "").replace("]]", "").strip()
                courses.add(raw_c)
        except Exception:
            continue
    return sorted(list(courses))

def get_notes_for_date(target_date: datetime.date) -> str:
    notes = []
    for file_path in sorted(LECTURES_DIR.glob("*.md")):
        try:
            post = frontmatter.load(file_path)
            note_date = post.get("date")
            if isinstance(note_date, str):
                note_date = datetime.date.fromisoformat(note_date)
            if note_date == target_date:
                course_label = str(post.get('course', '')).replace("[[", "").replace("]]", "")
                topic_label = str(post.get('topic', '')).replace("[[", "").replace("]]", "")
                notes.append(f"## Course: {course_label} | Topic: {topic_label}\n{post.content}")
        except Exception:
            continue
    return "\n\n---\n\n".join(notes)

def get_notes_in_date_range(course: str, start_date: datetime.date, end_date: datetime.date) -> str:
    notes = []
    clean_target_course = course.replace("[[", "").replace("]]", "").strip().lower()

    for file_path in sorted(LECTURES_DIR.glob("*.md")):
        try:
            post = frontmatter.load(file_path)
            note_date = post.get("date")
            raw_course = str(post.get("course", "")).replace("[[", "").replace("]]", "").strip()
            
            if isinstance(note_date, str):
                note_date = datetime.date.fromisoformat(note_date)
            
            if raw_course.lower() == clean_target_course and note_date and (start_date <= note_date <= end_date):
                topic_label = str(post.get('topic', '')).replace("[[", "").replace("]]", "")
                notes.append(f"### Lecture Date: {note_date} | Topic: {topic_label}\n{post.content}")
        except Exception:
            continue
    return "\n\n---\n\n".join(notes)

def generate_daily_recap(target_date: datetime.date, model: str = None) -> str:
    context = get_notes_for_date(target_date)
    if not context:
        return f"No lecture records found for {target_date.isoformat()}."

    prompt = f"""
    You are an executive academic tutor. Synthesize a comprehensive briefing from all classes recorded on {target_date.isoformat()}:
    
    {context}
    
    Format your response with:
    1. **Master Daily Overview** (High-level synthesis connecting today's topics)
    2. **Key Formulas, Theorems & Proofs** (Organized by Course, in clean LaTeX)
    3. **Immediate Action Items & Upcoming Deadlines** (Assignments, reading mentions, lab deadlines)
    """
    
    return generate_with_fallback(prompt=prompt, requested_model=model)

def query_exam_syllabus(course: str, start_date: datetime.date, end_date: datetime.date, question: str, model: str = None) -> str:
    context = get_notes_in_date_range(course, start_date, end_date)
    if not context:
        return f"No notes found for course '{course}' between {start_date} and {end_date}."

    system_instruction = f"""
    You are an expert STEM examination prep tutor for the course "{course}".
    You have access to the complete lecture syllabus notes for the target window ({start_date} to {end_date}):
    
    {context}
    
    Rules:
    - Answer doubts strictly based on the provided lectures.
    - Always cite the exact lecture dates for specific concepts, proofs, and definitions.
    - If asked for mock exams, generate challenging problems matching the professor's emphasis with step-by-step solutions and marking schemes.
    - Render all mathematical equations in LaTeX ($...$ for inline, $$...$$ for display).
    """

    return generate_with_fallback(
        prompt=question,
        system_instruction=system_instruction,
        requested_model=model
    )
