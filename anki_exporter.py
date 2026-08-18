import re
import random
import frontmatter
from pathlib import Path
import genanki

# Fixed Anki Model IDs
ANKI_MODEL_ID = 1607392319
ANKI_DECK_ID_BASE = 2059400110

# Academic STEM Anki Card Template with LaTeX KaTeX support and styling
STEM_ANKI_MODEL = genanki.Model(
    ANKI_MODEL_ID,
    'Graduate STEM Flashcard (LaTeX/KaTeX)',
    fields=[
        {'name': 'Question'},
        {'name': 'Answer'},
        {'name': 'Course'},
        {'name': 'Topic'},
        {'name': 'Date'},
    ],
    templates=[
        {
            'name': 'Card 1',
            'qfmt': '''
                <div style="font-family: -apple-system, system-ui, sans-serif; padding: 20px; background-color: #1e1e2e; color: #cdd6f4; border-radius: 12px;">
                    <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #89b4fa; margin-bottom: 8px;">
                        📚 {{Course}} &nbsp;•&nbsp; 🏷️ {{Topic}}
                    </div>
                    <div style="font-size: 18px; font-weight: 600; line-height: 1.5; color: #f5e0dc;">
                        {{Question}}
                    </div>
                </div>
            ''',
            'afmt': '''
                {{FrontSide}}
                <hr style="border: 0; height: 1px; background: #45475a; margin: 15px 0;">
                <div style="font-family: -apple-system, system-ui, sans-serif; padding: 20px; background-color: #181825; color: #a6adc8; border-radius: 12px; font-size: 16px; line-height: 1.6;">
                    <div style="color: #a6e3a1; font-weight: 500; margin-bottom: 6px;">💡 Answer:</div>
                    {{Answer}}
                    <div style="margin-top: 15px; font-size: 11px; color: #6c7086; text-align: right;">
                        Lecture Date: {{Date}}
                    </div>
                </div>
            ''',
        },
    ],
    css='''
        .card { font-family: -apple-system, system-ui, sans-serif; text-align: left; background-color: #11111b; }
    '''
)

def parse_flashcards_from_markdown(markdown_text: str) -> list[tuple[str, str]]:
    """Extracts (Question, Answer) pairs from Section 4 of note markdown."""
    cards = []
    qa_pattern = r"(?:\*\*Q\d*:\s*|\*\*Question\d*:\s*|Q\d*:\s*)(.*?)(?:\*\*|\n)(?:\s*\*\*A\d*:\s*|\s*\*\*Answer\d*:\s*|\s*A\d*:\s*)(.*?)(?=\n\s*(?:\*\*Q|Q\d*:|##|\Z))"
    matches = re.findall(qa_pattern, markdown_text, flags=re.DOTALL)

    for q, a in matches:
        clean_q = q.strip().strip("*").strip()
        clean_a = a.strip().strip("*").strip()
        if clean_q and clean_a:
            cards.append((clean_q, clean_a))
            
    return cards

def generate_anki_deck_from_file(file_path: Path) -> Path:
    """Creates a .apkg Anki deck file from a single lecture note."""
    post = frontmatter.load(file_path)
    course = str(post.get("course", "General")).replace("[[", "").replace("]]", "").strip()
    topic = str(post.get("topic", file_path.stem)).replace("[[", "").replace("]]", "").strip()
    date_str = str(post.get("date", ""))

    cards = parse_flashcards_from_markdown(post.content)
    if not cards:
        return None

    deck_id = ANKI_DECK_ID_BASE + abs(hash(course)) % 1000000
    deck = genanki.Deck(deck_id, f"Academic::{course}::{topic}")

    for q, a in cards:
        note = genanki.Note(
            model=STEM_ANKI_MODEL,
            fields=[q, a, course, topic, date_str]
        )
        deck.add_note(note)

    out_dir = file_path.parent / "Anki_Decks"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    clean_course = course.replace(" ", "_")
    clean_topic = topic.replace(" ", "_")
    out_file = out_dir / f"{date_str}_{clean_course}_{clean_topic}.apkg"
    
    genanki.Package(deck).write_to_file(str(out_file))
    return out_file

def generate_anki_deck_for_course(lectures_dir: Path, course_name: str) -> Path:
    """Creates a unified .apkg Anki deck containing all flashcards for an entire course."""
    clean_target_course = course_name.replace("[[", "").replace("]]", "").strip().lower()
    deck_id = ANKI_DECK_ID_BASE + abs(hash(course_name)) % 1000000
    deck = genanki.Deck(deck_id, f"Academic::{course_name}::Complete Syllabus")

    card_count = 0
    for file_path in sorted(lectures_dir.glob("*.md")):
        try:
            post = frontmatter.load(file_path)
            raw_c = str(post.get("course", "")).replace("[[", "").replace("]]", "").strip()
            topic = str(post.get("topic", "")).replace("[[", "").replace("]]", "").strip()
            date_str = str(post.get("date", ""))
            
            if raw_c.lower() == clean_target_course:
                cards = parse_flashcards_from_markdown(post.content)
                for q, a in cards:
                    note = genanki.Note(
                        model=STEM_ANKI_MODEL,
                        fields=[q, a, raw_c, topic, date_str]
                    )
                    deck.add_note(note)
                    card_count += 1
        except Exception:
            continue

    if card_count == 0:
        return None

    out_dir = lectures_dir / "Anki_Decks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{course_name.replace(' ', '_')}_Complete_Deck.apkg"
    genanki.Package(deck).write_to_file(str(out_file))
    return out_file

if __name__ == "__main__":
    test_file = Path("./lectures/2026-10-15_Machine_Learning_Backpropagation.md")
    if test_file.exists():
        apkg = generate_anki_deck_from_file(test_file)
        print(f"[+] Anki Deck generated: {apkg}")
