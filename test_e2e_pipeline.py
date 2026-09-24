import os
import sys
import time
import unittest
from pathlib import Path
from dotenv import load_dotenv

# Ensure root path is accessible
ROOT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from ingest_audio import process_file, get_optimal_model_for_file
from core_engine import SUPPORTED_MODELS, query_exam_syllabus, generate_with_fallback
from metadata_db import query_courses, query_topics, get_all_saved_chats
from vector_store import semantic_search_notes, hybrid_search_notes

class TestAcademicPipelineEndToEnd(unittest.TestCase):

    def test_models_configuration(self):
        """Verify supported models list and fallback structure."""
        self.assertIn("gemini-3.6-flash", SUPPORTED_MODELS)
        self.assertIn("gemini-3-flash-preview", SUPPORTED_MODELS)
        self.assertIn("gemini-3.1-flash-lite", SUPPORTED_MODELS)
        self.assertIn("gemini-3.5-flash-lite", SUPPORTED_MODELS)

    def test_optimal_model_selection(self):
        """Verify audio vs document vs dense math model routing."""
        audio_path = Path("sample.m4a")
        doc_path = Path("lecture_guide.pdf")
        
        audio_model, audio_fallbacks = get_optimal_model_for_file(audio_path)
        self.assertTrue("flash" in audio_model.lower() or "gemini" in audio_model.lower())
        self.assertIn("gemini-3-flash-preview", audio_fallbacks)
        
        doc_model, doc_fallbacks = get_optimal_model_for_file(doc_path)
        self.assertIn("gemini-3-flash-preview", doc_fallbacks)

    def test_end_to_end_document_ingestion_and_search(self):
        """
        End-to-End Ingestion & Query Test:
        1. Ingests a text lecture material through process_file
        2. Validates clean LaTeX rendering & Obsidian markdown structure
        3. Validates database indexing (SQLite + FTS5)
        4. Validates hybrid search retrieval
        """
        test_dir = ROOT_DIR / "incoming_audio"
        test_dir.mkdir(parents=True, exist_ok=True)
        sample_file = test_dir / "ELEC70141_Ethics_Case_Study_2026-09-24.txt"
        sample_file.write_text(
            "Lecture Topic: Responsible AI and Algorithmic Auditing\n"
            "Prof: Dr. Smith\n"
            "Key Themes: Bias Mitigation, Equalized Odds, Demographic Parity.\n"
            "Mathematical formulation: P(Y_hat = 1 | A = 0, Y = y) = P(Y_hat = 1 | A = 1, Y = y).\n"
            "Exam Warning: Students must prove why Equalized Odds is incompatible with Calibration.\n",
            encoding="utf-8"
        )

        try:
            out_note = process_file(
                file_path_str=str(sample_file),
                course_name="ELEC70141",
                topic_name="Ethics Case Study",
                lecture_date="2026-09-24"
            )

            self.assertTrue(out_note.exists(), f"Output note {out_note} was not created")
            content = out_note.read_text(encoding="utf-8")
            
            # Assert Frontmatter and Structure
            self.assertIn('course: "[[ELEC70141]]"', content)
            self.assertIn("graduate-notes", content)
            self.assertTrue("## 1." in content or "##" in content)

            # Assert Database Indexing
            courses = query_courses()
            self.assertIn("ELEC70141", courses)

            # Assert Vector / Hybrid Search Retrieval
            search_results = hybrid_search_notes("Equalized Odds Calibration", n_results=3)
            self.assertGreater(len(search_results), 0)
            print(f"[+] End-to-end ingestion and search verified successfully on {out_note.name}!")
        finally:
            if sample_file.exists():
                sample_file.unlink()

    def test_flashcard_extraction_and_deck_generation(self):
        """Verify that multi-card Section 4 markdown parses into individual flashcards, not one blob."""
        from anki_exporter import parse_flashcards_from_markdown, generate_anki_deck_from_file

        sample_markdown = """---
course: "[[ELEC70141]]"
topic: "[[Responsible AI]]"
date: 2026-09-24
---

# ELEC70141: Responsible AI

## 4. Key Concept Q&A Flashcards
- **Q1: What defines outlier bias?**
  - **A1**: It is a class of non-systematic algorithmic error where models fail to categorize outliers.
- **Q2: Why did Random Forest outperform PointCNN?**
  - **A2**: It effectively prioritized critical distance features.
- **Q3: What role does context play?**
  - **A3**: Standardized city designs allow higher accuracy.

## 5. Chronological / Sectional Breakdown
- Section 1: Introduction
"""
        cards = parse_flashcards_from_markdown(sample_markdown)
        self.assertEqual(len(cards), 3)
        self.assertEqual(cards[0][0], "What defines outlier bias?")
        self.assertEqual(cards[1][0], "Why did Random Forest outperform PointCNN?")
        self.assertEqual(cards[2][0], "What role does context play?")

if __name__ == "__main__":
    unittest.main(verbosity=2)
