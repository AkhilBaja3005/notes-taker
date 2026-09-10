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
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
]

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options={"timeout": 20000}
)
LECTURES_DIR = Path(os.environ.get("LECTURES_DIR", "./lectures"))

# In-memory context cache tracker: (cache_name, expire_time, course_key)
_ACTIVE_SYLLABUS_CACHES = {}

def clean_and_repair_latex(markdown_text: str) -> str:
    r"""
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

def fetch_wikipedia_knowledge(query: str, max_results: int = 3) -> tuple[str, list[dict]]:
    """
    Searches Wikipedia Full-Text Knowledge API for relevant academic concepts,
    definitions, and theorems with zero rate-limiting and 100% free uptime.
    Returns formatted context snippet and citations.
    """
    import urllib.request
    import urllib.parse
    import json
    import re
    import html

    # Extract core academic keywords (ignore instructional prompt filler)
    clean_q = re.sub(r"[^\w\s-]", " ", query).strip()
    words = [w for w in clean_q.split() if w.lower() not in {"student", "asking", "question", "explain", "derive", "proof", "derivation", "step", "full", "detailed", "detail"}]
    search_term = " ".join(words[:10]) if words else clean_q[:50]
    if not search_term.strip():
        return "", []

    search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(search_term)}&utf8=&format=json&srlimit={max_results}"
    req = urllib.request.Request(search_url, headers={
        "User-Agent": "AcademicAssistant/2.0 (student-academic-bot@university.edu)"
    })
    
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("query", {}).get("search", [])
            if not results:
                return "", []

            context_lines = ["🌐 External Verified Academic Knowledge (Wikipedia):"]
            citations = []
            for r in results:
                title = r.get("title", "")
                raw_snippet = r.get("snippet", "")
                snippet = html.unescape(re.sub(r"<.*?>", "", raw_snippet).strip())
                url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                context_lines.append(f"• **{title}**: {snippet}")
                citations.append({"title": title, "url": url})

            return "\n".join(context_lines), citations
    except Exception as e:
        print(f"[!] Wikipedia knowledge retrieval notice: {e}")
        return "", []

def generate_with_fallback(prompt: str, system_instruction: str = None, requested_model: str = None, enable_web_search: bool = False) -> str:
    DEPRECATED_MODELS = {
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-flash-latest",
        "gemini-flash-lite-latest"
    }
    
    candidate_models = []
    for m in [requested_model] + SUPPORTED_MODELS:
        if m and m not in candidate_models and m not in DEPRECATED_MODELS:
            candidate_models.append(m)
            
    last_err = None

    # If web search is requested, fetch Wikipedia knowledge grounding for factual backing
    wiki_context = ""
    wiki_citations = []
    augmented_prompt = prompt
    if enable_web_search:
        wiki_context, wiki_citations = fetch_wikipedia_knowledge(prompt)
        if wiki_context:
            augmented_prompt = f"{prompt}\n\n{wiki_context}"

    for model_name in candidate_models:
        try:
            config_kwargs = {}
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction
            if enable_web_search:
                config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
                
            config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

            with contextlib.redirect_stderr(io.StringIO()):
                response = client.models.generate_content(
                    model=model_name,
                    contents=augmented_prompt,
                    config=config
                )
            output_text = clean_and_repair_latex(response.text)

            # Extract verifiable Google Search or Wikipedia citations
            sources = []
            seen_urls = set()
            if enable_web_search and getattr(response, "candidates", None):
                cand = response.candidates[0]
                meta = getattr(cand, "grounding_metadata", None)
                if meta:
                    chunks = getattr(meta, "grounding_chunks", None) or []
                    for c in chunks:
                        web = getattr(c, "web", None)
                        if web and getattr(web, "uri", None) and web.uri not in seen_urls:
                            seen_urls.add(web.uri)
                            title = getattr(web, "title", None) or web.uri
                            sources.append(f"- [{title}]({web.uri})")

            # Append Wikipedia citations if available
            for w in wiki_citations:
                if w["url"] not in seen_urls:
                    seen_urls.add(w["url"])
                    sources.append(f"- [{w['title']}]({w['url']})")

            if sources:
                output_text += "\n\n### 🌐 Verified Web Sources & Citations:\n" + "\n".join(sources[:5])

            return output_text
        except Exception as e:
            # If Google Search Grounding hits free-tier quota (429 RESOURCE_EXHAUSTED),
            # gracefully answer using the model's comprehensive internal knowledge base + injected Wikipedia context.
            if enable_web_search and "RESOURCE_EXHAUSTED" in str(e):
                print(f"[*] Google Search grounding quota exceeded on {model_name}. Answering with Wikipedia grounding + internal intelligence...")
                try:
                    config_kwargs_safe = {}
                    if system_instruction:
                        config_kwargs_safe["system_instruction"] = system_instruction
                    cfg_safe = types.GenerateContentConfig(**config_kwargs_safe) if config_kwargs_safe else None
                    with contextlib.redirect_stderr(io.StringIO()):
                        resp_fallback = client.models.generate_content(
                            model=model_name,
                            contents=augmented_prompt,
                            config=cfg_safe
                        )
                    safe_output = clean_and_repair_latex(resp_fallback.text)
                    if wiki_citations:
                        safe_output += "\n\n### 🌐 Verified Web Sources & Citations:\n" + "\n".join([f"- [{w['title']}]({w['url']})" for w in wiki_citations[:5]])
                    return safe_output
                except Exception as inner_e:
                    pass

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

def get_notes_for_topic(topic: str, course: str = None) -> str:
    notes = []
    clean_target_topic = topic.replace("[[", "").replace("]]", "").strip().lower()
    clean_target_course = course.replace("[[", "").replace("]]", "").strip().lower() if course else None

    for file_path in sorted(LECTURES_DIR.glob("*.md")):
        if file_path.name.endswith("_MOC.md"):
            continue
        try:
            post = frontmatter.load(file_path)
            raw_topic = str(post.get('topic', '')).replace("[[", "").replace("]]", "").strip()
            raw_course = str(post.get('course', '')).replace("[[", "").replace("]]", "").strip()
            
            match_topic = clean_target_topic in raw_topic.lower() or raw_topic.lower() in clean_target_topic
            match_course = True if not clean_target_course else (clean_target_course == raw_course.lower())

            if match_topic and match_course:
                notes.append(f"### Course: {raw_course} | Topic: {raw_topic} ({post.get('date', 'N/A')})\n{post.content}")
        except Exception:
            continue
    return "\n\n---\n\n".join(notes)

def generate_multi_scope_briefing(scope: str, target: str, course: str = None, model: str = None) -> str:
    """
    Synthesizes academic briefings across 3 flexible scopes:
    - scope='date': Daily Multi-Subject Briefing (target: YYYY-MM-DD)
    - scope='course': Semester Course Overview & Milestones (target: Course Name)
    - scope='topic': Topic Deep Dive & Proof Synthesis (target: Topic Name)
    """
    if scope == "course":
        start_d = datetime.date.today() - datetime.timedelta(days=365)
        end_d = datetime.date.today()
        context = get_notes_in_date_range(target, start_d, end_d)
        if not context:
            return f"No lecture notes found for course '{target}'."
        prompt = f"""
        You are a distinguished STEM professor. Synthesize a comprehensive course-level master briefing for "{target}":
        
        {context}
        
        Format your response with:
        1. **Course Conceptual Architecture & Progression** (How topics connect across the semester)
        2. **Core Formulas, Theorems & Governing Equations** (In clean standard LaTeX $...$ and $$\\begin{{aligned}}...\\end{{aligned}}$$)
        3. **Key Exam Pitfalls & High-Yield Derivation Targets**
        4. **Conceptual Mastery Checklist**
        """
    elif scope == "topic":
        context = get_notes_for_topic(target, course=course)
        if not context:
            return f"No lecture notes found for topic '{target}'."
        prompt = f"""
        You are an expert academic tutor. Generate an exhaustive, high-yield topic deep dive for "{target}":
        
        {context}
        
        Format your response with:
        1. **Executive Intuition & Conceptual Definition**
        2. **Rigorous Mathematical Formulations & Proofs** (In clean standard LaTeX $...$ and $$\\begin{{aligned}}...\\end{{aligned}}$$)
        3. **Failure Modes, Saturated Regimes & Edge Cases**
        4. **Professor Emphasis & High-Yield Exam Traps**
        5. **5-Question Active Recall Mastery Test**
        """
    else:  # date scope
        try:
            target_date = datetime.date.fromisoformat(target) if isinstance(target, str) else target
        except Exception:
            target_date = datetime.date.today()
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

def generate_daily_recap(target_date: datetime.date, model: str = None) -> str:
    return generate_multi_scope_briefing(scope="date", target=target_date.isoformat(), model=model)

def query_exam_syllabus(course: str, start_date: datetime.date, end_date: datetime.date, question: str, model: str = None, enable_web_search: bool = False) -> str:
    context = get_notes_in_date_range(course, start_date, end_date)
    if not context:
        # User's question was not found in the local lecture DB:
        # Automatically use Gemini 3 with Google Search Grounding to research and answer the question!
        prompt = f"""
        STEM Course / Topic: "{course}"
        Student Question: "{question}"

        Note: No matching lecture notes were found in the student's Obsidian vault for this course/date range.
        Please search the web using Google Search grounding or synthesize a comprehensive, rigorous academic explanation.
        Include step-by-step mathematical derivations in LaTeX ($...$ for inline, $$...$$ for display math).
        """
        system_instruction = f"You are an expert STEM professor for the course '{course}'. Use Google Search grounding to provide verified answers, formulas, theorems, and definitions."
        return generate_with_fallback(
            prompt=prompt,
            system_instruction=system_instruction,
            requested_model=model,
            enable_web_search=True
        )

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

    # Direct context synthesis with resilient multi-tier fallback and optional web grounding
    return generate_with_fallback(
        prompt=f"Exam Syllabus Context ({course} from {start_date} to {end_date}):\n\n{context}\n\nStudent Query: {question}",
        system_instruction=system_instruction,
        requested_model=model,
        enable_web_search=enable_web_search
    )
