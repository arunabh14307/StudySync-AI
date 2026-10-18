"""
Automated Test Suite for StudySync AI Core Modules.
Covers SQLite Database, Text Processing, PDF Extraction,
Extractive Summarizer, Quiz Formulation, and Flashcard Generation.
"""

import os
import pytest
import tempfile
import fitz  # PyMuPDF
from utils.database import (
    init_db,
    get_connection,
    create_note,
    get_all_notes,
    get_note_by_id,
    update_note,
    delete_note,
    save_summary,
    get_all_summaries,
    delete_summary,
    save_quiz,
    get_all_quizzes,
    get_quiz_by_id,
    delete_quiz,
    save_quiz_attempt,
    get_all_quiz_attempts,
    get_quiz_stats,
    create_flashcard_deck,
    get_all_decks,
    save_flashcards_batch,
    get_flashcards_by_deck,
    update_flashcard_mastery,
    delete_deck,
    create_task,
    get_all_tasks,
    update_task_status,
    delete_task,
    get_task_stats,
    get_dashboard_metrics
)
from utils.text_processor import (
    clean_text,
    split_sentences,
    tokenize_words,
    tag_pos,
    extract_keywords,
    calculate_readability
)
from utils.pdf_processor import extract_text_from_pdf, extract_text_from_txt
from utils.summarizer import generate_summary
from utils.quiz_generator import generate_quiz_from_text
from utils.flashcard_generator import generate_flashcards_from_text


# =========================================================================
# 1. DATABASE TESTS
# =========================================================================

def test_database_init_and_crud(tmp_path):
    """Verifies that database schema initializes, seeds, and supports full CRUD."""
    test_db = str(tmp_path / "test_studysync.db")
    init_db(test_db)

    # Verify seed note exists
    notes = get_all_notes()
    assert len(notes) >= 2

    # Test creating a new note
    new_id = create_note(
        title="Operating Systems Memory Hierarchy",
        subject="Computer Science",
        content="Virtual memory allows executing processes that are not completely in memory.",
        tags="OS, Memory, Virtual"
    )
    assert new_id > 0

    note = get_note_by_id(new_id)
    assert note is not None
    assert note["title"] == "Operating Systems Memory Hierarchy"
    assert note["subject"] == "Computer Science"

    # Test updating the note
    upd_success = update_note(
        note_id=new_id,
        title="Operating Systems Memory Hierarchy - Updated",
        subject="Computer Science",
        content="Virtual memory abstracts physical storage into uniform address space.",
        tags="OS, Paging"
    )
    assert upd_success is True

    # Test deleting note
    del_success = delete_note(new_id)
    assert del_success is True
    assert get_note_by_id(new_id) is None


def test_task_management_crud():
    """Verifies task creation, filtering, status transition, and statistics."""
    task_id = create_task(
        title="Submit Linear Algebra Assignment",
        subject="Mathematics",
        description="Eigenvalues and Eigenvectors problem set",
        priority="High",
        deadline="2026-11-01",
        estimated_hours=3.5
    )
    assert task_id > 0

    # Test status change
    upd = update_task_status(task_id, "Completed")
    assert upd is True

    stats = get_task_stats()
    assert stats["total"] > 0
    assert stats["completed"] >= 1

    # Cleanup
    assert delete_task(task_id) is True


def test_quiz_and_attempt_crud():
    """Verifies quiz saving and recording student attempts."""
    questions = [
        {
            "id": 1,
            "question": "What is 2 + 2?",
            "options": ["A) 3", "B) 4", "C) 5", "D) 6"],
            "correct_option": "B",
            "explanation": "2 + 2 equals 4."
        }
    ]
    quiz_id = save_quiz(
        title="Math Basics Quiz",
        subject="Mathematics",
        questions=questions
    )
    assert quiz_id > 0

    q = get_quiz_by_id(quiz_id)
    assert q is not None
    assert len(q["questions"]) == 1

    # Record attempt
    attempt_id = save_quiz_attempt(
        quiz_id=quiz_id,
        quiz_title="Math Basics Quiz",
        subject="Mathematics",
        score=1,
        total_questions=1,
        time_taken_sec=15
    )
    assert attempt_id > 0

    stats = get_quiz_stats()
    assert stats["attempts_count"] > 0

    # Cleanup
    assert delete_quiz(quiz_id) is True


# =========================================================================
# 2. TEXT PROCESSOR TESTS
# =========================================================================

def test_text_cleaning_and_tokenization():
    raw_text = "This is a “quoted” sentence.\n\nHere is   another one with  spaces—and dashes!"
    cleaned = clean_text(raw_text)
    assert '“' not in cleaned
    assert '”' not in cleaned
    assert "  " not in cleaned

    sentences = split_sentences(cleaned)
    assert len(sentences) >= 2

    tokens = tokenize_words(cleaned)
    assert "quoted" in tokens
    assert "sentence" in tokens


def test_readability_metrics():
    academic_text = (
        "Cellular respiration is a metabolic pathway that breaks down glucose and produces ATP. "
        "The complete process comprises three major stages: glycolysis, the citric acid cycle, and oxidative phosphorylation. "
        "Glycolysis occurs in the cytoplasm and breaks one glucose molecule into two molecules of pyruvate."
    )
    res = calculate_readability(academic_text)
    assert res["word_count"] > 20
    assert res["sentence_count"] >= 3
    assert 0 <= res["flesch_score"] <= 100
    assert res["estimated_reading_time_min"] > 0


# =========================================================================
# 3. PDF PROCESSOR TESTS
# =========================================================================

def test_pdf_extraction_with_fitz():
    """Generates an in-memory test PDF using fitz and verifies extraction."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "StudySync AI Test Document Page 1\nExtractive NLP for Academic Notes.")
    doc.set_metadata({"title": "StudySync Test Doc", "author": "Automated Test Suite"})
    pdf_bytes = doc.write()
    doc.close()

    result = extract_text_from_pdf(pdf_bytes)
    assert result["success"] is True
    assert result["page_count"] == 1
    assert "StudySync AI Test Document" in result["text"]
    assert result["metadata"]["title"] == "StudySync Test Doc"


def test_pdf_extraction_empty_bytes():
    result = extract_text_from_pdf(b"")
    assert result["success"] is False
    assert "empty" in result["error"].lower()


def test_txt_extraction():
    text_sample = "Operating Systems Lab Notes:\n1. Thread synchronization\n2. Mutex locks"
    result = extract_text_from_txt(text_sample.encode('utf-8'))
    assert result["success"] is True
    assert "Mutex locks" in result["text"]


# =========================================================================
# 4. SUMMARIZER TESTS
# =========================================================================

def test_extractive_summarizer():
    sample_text = (
        "Artificial neural networks are computational models inspired by biological neural structures. "
        "The fundamental unit in an artificial neural network is the perceptron, which computes a weighted sum. "
        "Activation functions such as ReLU and Sigmoid introduce non-linearity into the network output. "
        "Deep networks feature multiple hidden layers that capture complex compositional features in high-dimensional data. "
        "Backpropagation is an optimization algorithm that calculates gradients of the error function using the chain rule. "
        "Gradient descent systematically updates network parameters to minimize model prediction loss over epochs."
    )
    res = generate_summary(sample_text, ratio=0.5)
    assert res["success"] is True
    assert len(res["summary_text"]) > 0
    assert res["summary_word_count"] < res["original_word_count"]
    assert len(res["key_points"]) >= 1


def test_summarizer_short_text():
    res = generate_summary("Too short.")
    assert res["success"] is False
    assert "too short" in res["error"].lower()


# =========================================================================
# 5. QUIZ GENERATOR TESTS
# =========================================================================

def test_quiz_generation():
    material = (
        "Mitochondria are membrane-bound cell organelles that generate most of the chemical energy needed to power the cell's biochemical reactions. "
        "Chemical energy produced by the mitochondria is stored in a small molecule called adenosine triphosphate. "
        "Glycolysis is the metabolic pathway that converts glucose into pyruvate, releasing free energy in the cytoplasm. "
        "Ribosomes are macromolecular machines found within all living cells that perform biological protein synthesis."
    )
    quiz_res = generate_quiz_from_text(material, num_questions=2)
    assert quiz_res["success"] is True
    assert len(quiz_res["questions"]) >= 1

    first_q = quiz_res["questions"][0]
    assert "question" in first_q
    assert len(first_q["options"]) == 4
    assert first_q["correct_option"] in ['A', 'B', 'C', 'D']
    assert "explanation" in first_q


def test_quiz_generation_short_text():
    res = generate_quiz_from_text("Short text.")
    assert res["success"] is False
    assert "too short" in res["error"].lower()


# =========================================================================
# 6. FLASHCARD GENERATOR TESTS
# =========================================================================

def test_flashcard_generation():
    text = (
        "Mitochondria: The powerhouse of the cell responsible for ATP cellular respiration. "
        "Ribosome: A molecular machine that conducts biological protein synthesis. "
        "Chloroplast is an organelle found in plant cells that conducts photosynthesis."
    )
    fc_res = generate_flashcards_from_text(text, max_cards=3)
    assert fc_res["success"] is True
    assert len(fc_res["cards"]) >= 2
    for card in fc_res["cards"]:
        assert "front" in card
        assert "back" in card
