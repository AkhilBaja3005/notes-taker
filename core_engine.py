import os
import re
import io
import sys
import contextlib
import datetime
from pathlib import Path
import frontmatter
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

SUPPORTED_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite"
]

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
LECTURES_DIR = Path(os.environ.get("LECTURES_DIR", "./lectures"))

# In-memory context cache tracker: (cache_name, expire_time, course_key)
_ACTIVE_SYLLABUS_CACHES = {}

def clean_and_repair_latex(markdown_text: str) -> str:
    """
    Comprehensive regex sanitizer & normalizer that converts non-standard LaTeX packages,
    fixes single backslash linebreaks `\ `, wraps isolated `\begin{aligned}` blocks in `$$`,
    and guarantees 100% rendering across Streamlit (KaTeX) and Obsidian (MathJax).
    """
    if not markdown_text:
        return ""

    text = markdown_text

    # 1. Macro Normalization
    text = re.sub(r"\\bm\{([^}]+)\}", r"\\mathbf{\1}", text)
    text = re.sub(r"\\bold\{([^}]+)\}", r"\\mathbf{\1}", text)
    text = re.sub(r"\\argmax(?=[^a-zA-Z]|$)", r"\\operatorname*{argmax}", text)
    text = re.sub(r"\\argmin(?=[^a-zA-Z]|$)", r"\\operatorname*{argmin}", text)
    text = re.sub(r"\\mathbbm\{1\}", r"\\mathbf{1}", text)

    # 2. Fix nested or doubled \begin{aligned}
    text = re.sub(r"\\begin\{aligned\}\s*\\begin\{aligned\}", r"\\begin{aligned}", text)
    text = re.sub(r"\\end\{aligned\}\s*\\end\{aligned\}", r"\\end{aligned}", text)

    # 3. Fix single backslash followed by space where LLM meant line-break `\\`
    text = re.sub(r"(?<=[^\\])\\\s+(?=[a-zA-Z0-9_\\])", r" \\\\\n", text)

    # 4. Strip malformed or trailing delimiters touching \begin / \end{aligned}
    text = re.sub(r"\$\$\s*\\begin\{aligned\}", r"\\begin{aligned}", text)
    text = re.sub(r"\\end\{aligned\}\s*\$\$", r"\\end{aligned}", text)

    # 5. Fix orphan `\end{aligned}` without `\begin{aligned}`
    orphan_pattern = r"(?<!\\begin\{aligned\})(?:^|\n)([^\n\$]*?[a-zA-Z0-9_\(\)\{\}\^\\]+\s*&=\s*.*?)(\\end\{aligned\})"
    def repl_orphan(m):
        content = m.group(1).strip()
        return f"\n\\begin{{aligned}}\n{content}\n\\end{{aligned}}\n"
    text = re.sub(orphan_pattern, repl_orphan, text, flags=re.DOTALL)

    # 6. Wrap ALL \begin{aligned} ... \end{aligned} cleanly in `$$ ... $$` with blank paragraph boundaries
    def wrap_aligned(m):
        content = m.group(0).strip()
        # Clean any accidental duplicate \begin{aligned} inside
        lines = content.splitlines()
        clean_lines = []
        seen_begin = False
        for l in lines:
            if "\\begin{aligned}" in l:
                if not seen_begin:
                    clean_lines.append(l)
                    seen_begin = True
            else:
                clean_lines.append(l)
        content = "\n".join(clean_lines)
        return f"\n\n$$\n{content}\n$$\n\n"

    text = re.sub(r"\\begin\{aligned\}.*?\\end\{aligned\}", wrap_aligned, text, flags=re.DOTALL)

    # 7. Clean duplicate newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

def generate_with_fallback(prompt: str, system_instruction: str = None, requested_model: str = None) -> str:
    """Robust generator with automatic fallback across stable Gemini Flash models and silent stderr."""
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

            with contextlib.redirect_stderr(io.StringIO()):
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
            return clean_and_repair_latex(response.text)
        except Exception as e:
            print(f"[!] Warning: Model {model_name} failed with: {e}. Retrying with next available model...")
            last_err = e

    raise RuntimeError(f"All Gemini models were unavailable or busy. Last error: {last_err}")

def get_available_courses() -> list[str]:
    courses = set()
    for file_path in LECTURES_DIR.glob("*.md"):
        if file_path.name.endswith("_MOC.md"):
            continue
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
        if file_path.name.endswith("_MOC.md"):
            continue
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
        if file_path.name.endswith("_MOC.md"):
            continue
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
    2. **Key Formulas, Theorems & Proofs** (Organized by Course, in clean standard LaTeX. Always enclose all multi-line aligned equations in '$$\\begin{{aligned}} ... \\end{{aligned}}$$'.)
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
    - CRITICAL: Never emit isolated '\\end{{aligned}}'. Always open with '$$\\begin{{aligned}}' and close with '\\end{{aligned}}$$'.
    """

    cache_key = f"{course}_{start_date}_{end_date}"
    now = datetime.datetime.now(datetime.timezone.utc)
    
    if len(context) > 2000 and (model is None or "flash" in model):
        try:
            cached_item = _ACTIVE_SYLLABUS_CACHES.get(cache_key)
            if cached_item and cached_item["expires_at"] > now:
                cache_name = cached_item["name"]
                config = types.GenerateContentConfig(cached_content=cache_name)
                with contextlib.redirect_stderr(io.StringIO()):
                    resp = client.models.generate_content(
                        model=DEFAULT_MODEL,
                        contents=question,
                        config=config
                    )
                return clean_and_repair_latex(resp.text)
            else:
                with contextlib.redirect_stderr(io.StringIO()):
                    new_cache = client.caches.create(
                        model=DEFAULT_MODEL,
                        config=types.CreateCachedContentConfig(
                            contents=[context],
                            system_instruction=system_instruction,
                            ttl="3600s"
                        )
                    )
                    _ACTIVE_SYLLABUS_CACHES[cache_key] = {
                        "name": new_cache.name,
                        "expires_at": now + datetime.timedelta(seconds=3500)
                    }
                    config = types.GenerateContentConfig(cached_content=new_cache.name)
                    resp = client.models.generate_content(
                        model=DEFAULT_MODEL,
                        contents=question,
                        config=config
                    )
                return clean_and_repair_latex(resp.text)
        except Exception as e:
            print(f"[!] Context cache fallback: {e}")

    return generate_with_fallback(
        prompt=question,
        system_instruction=system_instruction,
        requested_model=model
    )
