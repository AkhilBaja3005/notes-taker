import re
import datetime
from pathlib import Path
import frontmatter

def generate_course_moc(lectures_dir: Path, course_name: str) -> Path:
    """
    Generates/Updates an Obsidian Map of Content (MOC) index note for a course:
    - Master Chronological Syllabus list
    - Key Derivations and Theorems Index
    - High-Yield Exam Pitfalls aggregation
    """
    clean_course = course_name.replace("[[", "").replace("]]", "").strip()
    clean_target = clean_course.lower()
    
    matching_notes = []
    theorems = []
    pitfalls = []

    for file_path in sorted(lectures_dir.glob("*.md")):
        if file_path.name.endswith("_MOC.md"):
            continue
        try:
            post = frontmatter.load(file_path)
            raw_c = str(post.get("course", "")).replace("[[", "").replace("]]", "").strip()
            topic = str(post.get("topic", "")).replace("[[", "").replace("]]", "").strip()
            date_str = str(post.get("date", ""))
            
            if raw_c.lower() == clean_target:
                matching_notes.append({
                    "path": file_path,
                    "date": date_str,
                    "topic": topic,
                    "content": post.content
                })

                # Extract theorems / derivations
                math_matches = re.findall(r"### (.*?)\n(.*?)(?=\n###|\n##|\Z)", post.content, flags=re.DOTALL)
                for heading, text in math_matches:
                    if any(w in heading.lower() for w in ["theorem", "proof", "derivation", "equation", "formulation"]):
                        theorems.append((date_str, topic, heading.strip(), file_path.stem))

                # Extract exam warnings
                warning_match = re.search(r"> \[!WARNING\][^\n]*\n((?:> .*\n?)+)", post.content)
                if warning_match:
                    pitfalls.append((date_str, topic, warning_match.group(1).strip(), file_path.stem))

        except Exception:
            continue

    if not matching_notes:
        return None

    # Construct MOC Markdown Content
    moc_content = f"""---
title: "{clean_course} Map of Content (MOC)"
course: "[[{clean_course}]]"
type: "moc"
updated: "{datetime.date.today().isoformat()}"
tags:
  - moc
  - course/{clean_course.replace(' ', '')}
---

# 🗺️ {clean_course}: Map of Content (MOC)

> [!NOTE] Master Course Knowledge Hub
> This hub connects all lecture notes, derivations, and exam warnings for **{clean_course}**.

---

## 📅 1. Chronological Lecture Syllabus

| Date | Topic | Note Link |
| :--- | :--- | :--- |
"""
    for n in matching_notes:
        moc_content += f"| `{n['date']}` | {n['topic']} | [[{n['path'].stem}\\|{n['topic']} Note]] |\n"

    moc_content += "\n---\n\n## 📐 2. Key Derivations & Theorems Index\n\n"
    if theorems:
        for d, t, heading, stem in theorems:
            moc_content += f"- **[[{stem}#{heading}|{heading}]]** _(Topic: {t}, Date: `{d}`)_\n"
    else:
        moc_content += "_No formal theorems indexed yet._\n"

    moc_content += "\n---\n\n## ⚠️ 3. High-Yield Exam Pitfalls Aggregator\n\n"
    if pitfalls:
        for d, t, warn_text, stem in pitfalls:
            moc_content += f"### From [[{stem}|{t} ({d})]]:\n{warn_text}\n\n"
    else:
        moc_content += "_No exam warnings indexed yet._\n"

    moc_file = lectures_dir / f"{clean_course.replace(' ', '_')}_MOC.md"
    moc_file.write_text(moc_content, encoding="utf-8")
    print(f"[+] Updated Obsidian Course MOC: {moc_file.name}")
    return moc_file

def update_all_course_mocs(lectures_dir: Path):
    """Scans and updates MOCs for all active courses in lectures_dir."""
    courses = set()
    for file_path in lectures_dir.glob("*.md"):
        if file_path.name.endswith("_MOC.md"):
            continue
        try:
            post = frontmatter.load(file_path)
            if "course" in post:
                raw_c = str(post["course"]).replace("[[", "").replace("]]", "").strip()
                courses.add(raw_c)
        except Exception:
            continue

    for c in courses:
        generate_course_moc(lectures_dir, c)

if __name__ == "__main__":
    test_dir = Path("./lectures")
    update_all_course_mocs(test_dir)
