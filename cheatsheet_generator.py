import datetime
from pathlib import Path
from core_engine import get_notes_in_date_range, generate_with_fallback

def generate_course_cheatsheet(course: str, start_date: datetime.date, end_date: datetime.date, model: str = None) -> str:
    """
    Generates a dense, comprehensive, high-yield mathematical formula sheet & cheatsheet
    ready for midterms, finals, or quick review.
    """
    context = get_notes_in_date_range(course, start_date, end_date)
    if not context:
        return f"No lecture notes found for course '{course}' between {start_date} and {end_date}."

    prompt = f"""
    You are an expert STEM professor creating an authoritative, comprehensive, 2-page master EXAM CHEATSHEET & FORMULA SHEET for the graduate course:
    Course: "{course}"
    Syllabus Date Range: {start_date} to {end_date}

    Target Course Lectures & Derivations Context:
    {context}

    INSTRUCTIONS:
    Synthesize an ultra-dense, mathematically rigorous reference sheet organized into clear thematic sections:

    # 📋 Master Exam Cheatsheet: {course} ({start_date} to {end_date})

    ## 1. Master Formula Table & Notation Index
    | Symbol / Variable | Mathematical Meaning & Dimensionality | Standard Domain |
    | :--- | :--- | :--- |

    ## 2. Core Theorems, Definitions & Closed-Form Equations
    - Group equations logically by topic.
    - Write all equations in standard LaTeX ($...$ for inline, and wrap all multi-line aligned equations in '$$\\begin{{aligned}} ... \\end{{aligned}}$$').
    - State all exact conditions, prerequisites (e.g. convexity, Slater's condition, invertibility).

    ## 3. High-Yield Gradient & Vector Calculus Derivations
    - Include key matrix inner/outer product dimensions and chain rule formulas.

    ## 4. Exam Traps, Common Mistakes & Asymptotics
    > [!WARNING] High-Frequency Exam Mistakes & Corner Cases
    > - Bullet points of sign errors, transpose order traps, and boundary condition checks.

    ## 5. Algorithmic Steps & Update Rules
    - Step-by-step update formulas and convergence guarantees (e.g. learning rate conditions, subgradient bounds).
    """

    return generate_with_fallback(prompt=prompt, requested_model=model)

if __name__ == "__main__":
    sheet = generate_course_cheatsheet("Machine Learning", datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))
    print(sheet[:500] + "...")
