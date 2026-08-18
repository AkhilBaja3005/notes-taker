import os
import datetime
from pathlib import Path
# pyrefly: ignore [missing-import]
import frontmatter
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
from google.genai import types

load_dotenv()

SUPPORTED_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.0-flash",
]

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash")

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
LECTURES_DIR = Path(os.environ.get("LECTURES_DIR", "./lectures"))

def get_available_courses() -> list[str]:
    courses = set()
    for file_path in LECTURES_DIR.glob("*.md"):
        try:
            post = frontmatter.load(file_path)
            if "course" in post:
                courses.add(post["course"])
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
                notes.append(f"## Course: {post.get('course')} | Topic: {post.get('topic')}\n{post.content}")
        except Exception:
            continue
    return "\n\n---\n\n".join(notes)

def get_notes_in_date_range(course: str, start_date: datetime.date, end_date: datetime.date) -> str:
    notes = []
    for file_path in sorted(LECTURES_DIR.glob("*.md")):
        try:
            post = frontmatter.load(file_path)
            note_date = post.get("date")
            note_course = post.get("course")
            if isinstance(note_date, str):
                note_date = datetime.date.fromisoformat(note_date)
            
            if note_course == course and note_date and (start_date <= note_date <= end_date):
                notes.append(f"### Lecture Date: {note_date} | Topic: {post.get('topic')}\n{post.content}")
        except Exception:
            continue
    return "\n\n---\n\n".join(notes)

def generate_daily_recap(target_date: datetime.date, model: str = None) -> str:
    if model is None:
        model = DEFAULT_MODEL

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
    
    response = client.models.generate_content(
        model=model,
        contents=prompt
    )
    return response.text

def query_exam_syllabus(course: str, start_date: datetime.date, end_date: datetime.date, question: str, model: str = None) -> str:
    if model is None:
        model = DEFAULT_MODEL

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

    response = client.models.generate_content(
        model=model,
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction
        )
    )
    return response.text
