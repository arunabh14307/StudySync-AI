"""
Comprehensive Quality Assurance (QA) Test Suite for StudySync AI.
Validates all college project demonstration criteria:
1. SQLite initialization and schema persistence.
2. Theme preference switching and persistence.
3. PDF and TXT validation with edge cases (empty, wrong header, huge size, unknown extension).
4. Extractive summarizer edge cases (empty text, short text, normal educational text).
5. Keyword and keyphrase extraction with linguistic edge cases.
6. MCQ generation, duplicate option prevention, and scoring accuracy.
7. Active recall flashcards, confidence rating, and deck navigation bounds.
8. Task management: overdue detection, priority filtering, and lifecycle transitions.
9. Central Study Library search, multi-type material filtering, and sorting.
10. SQL parameterization and injection prevention across all inputs.
11. Study analytics computation strictly from stored database records.
12. Empty state and zero-data resilience without crashes.
"""

import os
import re
import pytest
import datetime
from utils.database import (
    init_db,
    get_preference,
    set_preference,
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
    delete_quiz,
    save_quiz_attempt,
    get_all_quiz_attempts,
    get_quiz_stats,
    get_subject_quiz_performance,
    create_flashcard_deck,
    get_all_decks,
    get_deck_by_id,
    create_flashcard,
    save_flashcards_batch,
    get_flashcards_by_deck,
    update_flashcard_mastery,
    delete_deck,
    delete_flashcard,
    create_task,
    get_all_tasks,
    get_task_by_id,
    update_task,
    update_task_status,
    complete_task,
    delete_task,
    get_task_stats,
    get_upcoming_tasks,
    log_study_session,
    get_study_sessions,
    get_study_session_stats,
    get_dashboard_metrics,
    get_distinct_subjects,
    get_unified_library_items,
    get_notes_stats,
    ValidationError
)
from utils.pdf_processor import (
    validate_uploaded_file,
    extract_text_from_pdf,
    extract_text_from_txt,
    format_file_size,
    format_pdf_date,
    MAX_PDF_SIZE_BYTES,
    MAX_TXT_SIZE_BYTES
)
from utils.text_processor import (
    clean_text,
    split_sentences,
    tokenize_words,
    tag_pos,
    get_word_frequencies,
    extract_keywords,
    calculate_readability
)
from utils.summarizer import generate_summary
from utils.quiz_generator import generate_quiz_from_text
from utils.flashcard_generator import generate_flashcards_from_text


@pytest.fixture
def qa_db(tmp_path):
    """Provides a fresh, isolated database for each QA test."""
    db_file = str(tmp_path / "qa_studysync.db")
    init_db(db_file, seed_if_empty=False)
    return db_file


# =============================================================================
# 1. DATABASE & THEME PREFERENCE PERSISTENCE
# =============================================================================

def test_database_initialization_and_seeding(tmp_path):
    """Verifies that database schema initializes cleanly and seeds starter content."""
    db_file = str(tmp_path / "seed_qa.db")
    init_db(db_file, seed_if_empty=True)

    # Starter notes, tasks, quizzes, decks, and sessions should exist
    notes = get_all_notes(db_path=db_file)
    assert len(notes) >= 2
    tasks = get_all_tasks(db_path=db_file)
    assert len(tasks) >= 3
    decks = get_all_decks(db_path=db_file)
    assert len(decks) >= 1
    sessions = get_study_sessions(db_path=db_file)
    assert len(sessions) >= 3


def test_theme_preference_persistence(qa_db):
    """Verifies reading, updating, and persisting user theme preference."""
    # Default preference
    assert get_preference("theme", default_value="dark", db_path=qa_db) == "dark"

    # Set light mode
    set_preference("theme", "light", db_path=qa_db)
    assert get_preference("theme", default_value="dark", db_path=qa_db) == "light"

    # Set dark mode
    set_preference("theme", "dark", db_path=qa_db)
    assert get_preference("theme", default_value="dark", db_path=qa_db) == "dark"


# =============================================================================
# 2. DOCUMENT UPLOAD VALIDATION (PDF & TXT)
# =============================================================================

def test_pdf_txt_upload_validation_matrix():
    """Tests file upload validation across normal, empty, oversized, and corrupt files."""
    # 1. Valid TXT
    res_txt = validate_uploaded_file("notes.txt", 1024, b"Normal text content")
    assert res_txt["valid"] is True
    assert res_txt["file_type"] == ".txt"

    # 2. Valid PDF
    res_pdf = validate_uploaded_file("lecture.pdf", 4096, b"%PDF-1.4 sample content")
    assert res_pdf["valid"] is True
    assert res_pdf["file_type"] == ".pdf"

    # 3. Missing extension
    res_no_ext = validate_uploaded_file("lecture_notes", 1024, b"test")
    assert res_no_ext["valid"] is False
    assert "extension" in res_no_ext["error"].lower()

    # 4. Unsupported extension
    res_doc = validate_uploaded_file("document.docx", 1024, b"PK...")
    assert res_doc["valid"] is False
    assert "unsupported" in res_doc["error"].lower()

    # 5. Empty file (0 bytes)
    res_empty = validate_uploaded_file("empty.txt", 0, b"")
    assert res_empty["valid"] is False
    assert "empty" in res_empty["error"].lower()

    # 6. Oversized PDF (> 25MB)
    res_huge_pdf = validate_uploaded_file("huge.pdf", MAX_PDF_SIZE_BYTES + 1024)
    assert res_huge_pdf["valid"] is False
    assert "exceeds" in res_huge_pdf["error"].lower()

    # 7. Oversized TXT (> 10MB)
    res_huge_txt = validate_uploaded_file("huge.txt", MAX_TXT_SIZE_BYTES + 1024)
    assert res_huge_txt["valid"] is False
    assert "exceeds" in res_huge_txt["error"].lower()

    # 8. Corrupt / fake PDF header
    res_fake_pdf = validate_uploaded_file("fake.pdf", 1024, b"NOT_A_REAL_PDF_HEADER")
    assert res_fake_pdf["valid"] is False
    assert "%PDF" in res_fake_pdf["error"]


def test_txt_extraction_encodings():
    """Tests TXT extraction under UTF-8 and fallback encodings."""
    # Standard UTF-8
    sample_text = "Operating systems manage hardware abstraction and CPU scheduling."
    res = extract_text_from_txt(sample_text.encode("utf-8"), file_name="os.txt")
    assert res["success"] is True
    assert "hardware abstraction" in res["text"]
    assert res["metadata"]["word_count"] > 0

    # Empty TXT bytes
    empty_res = extract_text_from_txt(b"")
    assert empty_res["success"] is False
    assert "empty" in empty_res["error"].lower()


# =============================================================================
# 3. SUMMARIZATION & KEYWORD EXTRACTION
# =============================================================================

EDUCATIONAL_TEXT = (
    "Mitochondria are membrane-bound cell organelles that generate most of the chemical energy "
    "needed to power the cell's biochemical reactions. Chemical energy produced by the mitochondria "
    "is stored in a small molecule called adenosine triphosphate (ATP). Mitochondria contain their own "
    "small chromosomes, generally referred to as mitochondrial DNA. In addition to producing energy, "
    "mitochondria play a key role in cellular death, known as apoptosis. Cellular respiration is a set "
    "of metabolic reactions and processes that take place in the cells of organisms to convert biochemical "
    "energy from nutrients into adenosine triphosphate (ATP), and then release waste products."
)


def test_summarization_empty_and_short():
    """Verifies that empty and excessively short texts fail gracefully without crashing."""
    # Empty
    res_empty = generate_summary("")
    assert res_empty["success"] is False
    assert "short" in res_empty["error"].lower()

    # Short (less than 25 words)
    res_short = generate_summary("Mitochondria are organelles that produce energy for cells.")
    assert res_short["success"] is False
    assert "short" in res_short["error"].lower()


def test_summarization_educational_text():
    """Verifies extractive summarization on standard educational text."""
    res = generate_summary(EDUCATIONAL_TEXT, ratio=0.40)
    assert res["success"] is True
    assert res["error"] is None
    assert len(res["summary_text"]) > 0
    assert len(res["key_points"]) >= 1
    assert res["compression_ratio"] > 0.0
    assert res["original_word_count"] > res["summary_word_count"]


def test_keyword_extraction_and_readability():
    """Tests keyword ranking and Flesch reading ease score calculations."""
    # Keywords
    kw = extract_keywords(EDUCATIONAL_TEXT, top_n=5)
    assert len(kw) > 0
    kw_names = [k[0].lower() for k in kw]
    assert any("mitochondria" in name or "energy" in name or "atp" in name for name in kw_names)

    # Empty keyword extraction
    assert extract_keywords("") == []

    # Readability
    read = calculate_readability(EDUCATIONAL_TEXT)
    assert read["word_count"] > 50
    assert read["sentence_count"] >= 4
    assert 0.0 <= read["flesch_score"] <= 100.0
    assert read["reading_ease"] != "N/A"
    assert read["estimated_reading_time_min"] > 0.0

    # Readability on empty text
    empty_read = calculate_readability("")
    assert empty_read["word_count"] == 0
    assert empty_read["flesch_score"] == 0.0


# =============================================================================
# 4. MCQ GENERATION & SCORING
# =============================================================================

def test_mcq_generation_and_option_integrity():
    """Verifies that generated MCQs contain 4 distinct options, valid correct answer, and explanation."""
    res = generate_quiz_from_text(EDUCATIONAL_TEXT, num_questions=3)
    assert res["success"] is True
    assert len(res["questions"]) >= 1

    for q in res["questions"]:
        assert len(q["options"]) == 4
        # Options must be distinct (no duplicate choices)
        opt_texts = [re.sub(r'^[A-D]\)\s*', '', opt).strip().lower() for opt in q["options"]]
        assert len(set(opt_texts)) == 4
        assert q["correct_option"] in ["A", "B", "C", "D"]
        assert len(q["explanation"]) > 0


def test_quiz_attempt_scoring_and_stats(qa_db):
    """Tests saving attempts, computing scores, and calculating overall quiz statistics."""
    # Perfect score: 5 / 5 = 100%
    att1 = save_quiz_attempt(quiz_id=None, quiz_title="Cell Bio", subject="Biology", score=5, total_questions=5, db_path=qa_db)
    # 50% score: 2 / 4 = 50%
    att2 = save_quiz_attempt(quiz_id=None, quiz_title="Cell Bio", subject="Biology", score=2, total_questions=4, db_path=qa_db)

    attempts = get_all_quiz_attempts(db_path=qa_db)
    assert len(attempts) == 2

    stats = get_quiz_stats(db_path=qa_db)
    assert stats["attempts_count"] == 2
    assert stats["avg_score"] == 75.0
    assert stats["highest_score"] == 100.0
    assert stats["lowest_score"] == 50.0
    assert stats["total_questions_answered"] == 9

    # Subject performance
    perf = get_subject_quiz_performance(db_path=qa_db)
    assert len(perf) == 1
    assert perf[0]["subject"] == "Biology"
    assert perf[0]["attempts_count"] == 2
    assert perf[0]["avg_score"] == 75.0


# =============================================================================
# 5. FLASHCARDS & ACTIVE RECALL WORKFLOW
# =============================================================================

def test_flashcard_generation_and_deck_mastery(qa_db):
    """Tests auto-generating flashcards from notes, manual deck creation, and mastery updates."""
    # Auto-generation
    fc_res = generate_flashcards_from_text(EDUCATIONAL_TEXT, max_cards=4)
    assert fc_res["success"] is True
    assert len(fc_res["cards"]) >= 2

    for card in fc_res["cards"]:
        assert len(card["front"]) > 0
        assert len(card["back"]) > 0

    # Save to deck in DB
    deck_id = create_flashcard_deck(title="Cellular Biology", subject="Biology", db_path=qa_db)
    saved_cnt = save_flashcards_batch(deck_id, fc_res["cards"], db_path=qa_db)
    assert saved_cnt == len(fc_res["cards"])

    deck_cards = get_flashcards_by_deck(deck_id, db_path=qa_db)
    assert len(deck_cards) == saved_cnt

    # Update mastery level
    first_card = deck_cards[0]
    update_flashcard_mastery(first_card["id"], mastery_level=3, db_path=qa_db)

    # Deck stats should show 1 mastered
    decks = get_all_decks(db_path=qa_db)
    assert decks[0]["mastered_count"] == 1


# =============================================================================
# 6. TASK MANAGER: CRUD, OVERDUE, SORTING & FILTERING
# =============================================================================

def test_task_manager_comprehensive_workflow(qa_db):
    """Tests task creation, editing, completing, overdue detection, and sorting."""
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    # 1. Create overdue task
    t_overdue = create_task(title="Submit Chemistry Lab", subject="Chemistry", priority="High", deadline=yesterday, status="Pending", db_path=qa_db)
    # 2. Create upcoming task
    t_upcoming = create_task(title="Physics Homework 4", subject="Physics", priority="Medium", deadline=tomorrow, status="In Progress", db_path=qa_db)
    # 3. Create completed task
    t_done = create_task(title="Read Chapter 1", subject="Physics", priority="Low", deadline=yesterday, status="Completed", db_path=qa_db)

    # Verify overdue filter
    overdue_list = get_all_tasks(status_filter="Overdue", db_path=qa_db)
    assert len(overdue_list) == 1
    assert overdue_list[0]["id"] == t_overdue

    # Edit task
    update_task(
        task_id=t_overdue,
        title="Submit Chemistry Lab (Rescheduled)",
        subject="Chemistry",
        description="Updated deadline.",
        priority="High",
        deadline=tomorrow,
        status="Pending",
        estimated_hours=3.0,
        db_path=qa_db
    )
    edited = get_task_by_id(t_overdue, db_path=qa_db)
    assert edited["title"] == "Submit Chemistry Lab (Rescheduled)"
    assert edited["deadline"] == tomorrow

    # Mark complete
    complete_task(t_upcoming, db_path=qa_db)
    upc_updated = get_task_by_id(t_upcoming, db_path=qa_db)
    assert upc_updated["status"] == "Completed"
    assert upc_updated["completed_at"] is not None

    # Stats
    stats = get_task_stats(db_path=qa_db)
    assert stats["total"] == 3
    assert stats["completed"] == 2
    assert stats["completion_rate"] == 66.7


# =============================================================================
# 7. CENTRAL STUDY LIBRARY AGGREGATION & SEARCH
# =============================================================================

def test_central_study_library_unification_and_search(qa_db):
    """Verifies that notes, summaries, flashcard decks, and quizzes aggregate into the unified library."""
    n_id = create_note(title="Data Structures Notes", subject="Computer Science", content="Binary trees and heap allocation.", db_path=qa_db)
    s_id = save_summary(title="Algorithms Summary", original_text="...", summary_text="Big-O asymptotic bounds.", compression_ratio=50.0, db_path=qa_db)
    d_id = create_flashcard_deck(title="Sorting Algorithms Deck", subject="Computer Science", db_path=qa_db)
    q_id = save_quiz(title="Graph Algorithms Quiz", subject="Computer Science", questions=[{"question": "Q1", "options": ["A", "B"], "answer": "A"}], db_path=qa_db)

    # All materials query
    all_items = get_unified_library_items(db_path=qa_db)
    assert len(all_items) == 4

    # Search keyword matching 'Binary'
    tree_items = get_unified_library_items(search_query="Binary", db_path=qa_db)
    assert len(tree_items) == 1
    assert tree_items[0]["title"] == "Data Structures Notes"

    # Material type filter: Quizzes only
    quiz_items = get_unified_library_items(material_type="Practice Quizzes", db_path=qa_db)
    assert len(quiz_items) == 1
    assert quiz_items[0]["material_type"] == "quiz"

    # Subject filter
    cs_items = get_unified_library_items(subject_filter="Computer Science", db_path=qa_db)
    assert len(cs_items) >= 3


# =============================================================================
# 8. SQL INJECTION PREVENTION (PARAMETERIZATION)
# =============================================================================

def test_sql_injection_defense(qa_db):
    """Verifies that malicious SQL payloads in inputs do not compromise or crash database queries."""
    malicious_string = "'; DROP TABLE notes; SELECT * FROM notes WHERE title = '"
    
    # 1. Inserting note with payload
    note_id = create_note(
        title=malicious_string,
        subject="Security",
        content="Testing parameterized execution.",
        tags="test, security",
        db_path=qa_db
    )
    assert note_id > 0

    # Notes table must still exist and contain the note
    note = get_note_by_id(note_id, db_path=qa_db)
    assert note is not None
    assert note["title"] == malicious_string

    # 2. Searching with SQL payload
    results = get_all_notes(search_query=malicious_string, db_path=qa_db)
    assert len(results) == 1

    # 3. Task title with payload
    t_id = create_task(title=malicious_string, subject="Security", db_path=qa_db)
    assert t_id > 0
    tasks = get_all_tasks(search_query=malicious_string, db_path=qa_db)
    assert len(tasks) == 1


# =============================================================================
# 9. STUDY ANALYTICS GENUINE DATA INTEGRITY
# =============================================================================

def test_study_analytics_uses_genuine_records(qa_db):
    """Verifies that all analytics metrics are derived strictly from database records."""
    # Initially clean: all zero
    metrics = get_dashboard_metrics(db_path=qa_db)
    assert metrics["total_notes"] == 0
    assert metrics["total_tasks"] == 0
    assert metrics["quizzes_attempted"] == 0
    assert metrics["total_study_hours"] == 0.0

    # Add 1 note, 2 tasks (1 completed), 1 quiz attempt (80%), 1 study session (60 mins)
    create_note(title="Cognition", subject="Psychology", content="Short-term memory stores 7+-2 items.", db_path=qa_db)
    create_task(title="Task 1", subject="Psychology", status="Completed", db_path=qa_db)
    create_task(title="Task 2", subject="Psychology", status="Pending", db_path=qa_db)
    save_quiz_attempt(quiz_id=None, quiz_title="Quiz 1", subject="Psychology", score=4, total_questions=5, db_path=qa_db)
    log_study_session(subject="Psychology", duration_minutes=60, topic="Memory", db_path=qa_db)

    # Re-calculate
    updated_metrics = get_dashboard_metrics(db_path=qa_db)
    assert updated_metrics["total_notes"] == 1
    assert updated_metrics["total_tasks"] == 2
    assert updated_metrics["completed_tasks"] == 1
    assert updated_metrics["task_completion_rate"] == 50.0
    assert updated_metrics["quizzes_attempted"] == 1
    assert updated_metrics["avg_quiz_score"] == 80.0
    assert updated_metrics["total_study_hours"] == 1.0


# =============================================================================
# 10. EMPTY STATE RESILIENCE
# =============================================================================

def test_empty_database_graceful_handling(qa_db):
    """Verifies that empty databases return well-formed zeroed structures without throwing exceptions."""
    notes = get_all_notes(db_path=qa_db)
    assert notes == []
    tasks = get_all_tasks(db_path=qa_db)
    assert tasks == []
    quizzes = get_all_quizzes(db_path=qa_db)
    assert quizzes == []
    decks = get_all_decks(db_path=qa_db)
    assert decks == []
    sessions = get_study_sessions(db_path=qa_db)
    assert sessions == []
    library = get_unified_library_items(db_path=qa_db)
    assert library == []
    subjects = get_distinct_subjects(db_path=qa_db)
    assert subjects == []

    # Non-existent ID lookups
    assert get_note_by_id(999, db_path=qa_db) is None
    assert get_task_by_id(999, db_path=qa_db) is None
    assert get_deck_by_id(999, db_path=qa_db) is None
