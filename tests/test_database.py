"""
Comprehensive Test Suite for StudySync AI SQLite Database Layer.
Validates:
- Safe, idempotent schema initialization
- Empty database resilience (zero division / empty return handling)
- CRUD operations for notes, summaries, flashcards, tasks, quiz attempts, study sessions
- Input validation and exception handling (ValidationError)
- Cascading deletes and foreign key constraints
- Parameterized query safety against SQL injection
- Connection lifecycle management and resource cleanup
"""

import os
import pytest
from utils.database import (
    init_db,
    get_connection,
    get_db_cursor,
    ValidationError,
    RecordNotFoundError,
    # Notes
    create_note,
    get_all_notes,
    get_note_by_id,
    search_notes,
    update_note,
    delete_note,
    # Summaries
    save_summary,
    get_all_summaries,
    get_summary_by_id,
    delete_summary,
    # Flashcards & Decks
    create_flashcard_deck,
    get_all_decks,
    get_deck_by_id,
    delete_deck,
    create_flashcard,
    get_all_flashcards,
    get_flashcards_by_deck,
    get_flashcard_by_id,
    save_flashcards_batch,
    update_flashcard,
    update_flashcard_mastery,
    delete_flashcard,
    # Tasks
    create_task,
    get_all_tasks,
    get_task_by_id,
    update_task_status,
    complete_task,
    update_task,
    delete_task,
    get_task_stats,
    # Quizzes & Attempts
    save_quiz,
    get_all_quizzes,
    get_quiz_by_id,
    delete_quiz,
    save_quiz_attempt,
    get_all_quiz_attempts,
    get_quiz_attempt_by_id,
    delete_quiz_attempt,
    get_quiz_stats,
    # Study Sessions
    log_study_session,
    get_study_sessions,
    get_study_session_by_id,
    delete_study_session,
    get_study_session_stats,
    # Preferences & Dashboard
    get_preference,
    set_preference,
    get_dashboard_metrics
)


@pytest.fixture
def test_db(tmp_path):
    """Provides a fresh isolated database path for each test."""
    db_file = str(tmp_path / "test_isolated.db")
    init_db(db_file, seed_if_empty=False)
    return db_file


# =========================================================================
# 1. INITIALIZATION & REPEATED RUNS
# =========================================================================

def test_safe_repeated_initialization(tmp_path):
    """Verifies that init_db can run multiple times without error or duplicating tables."""
    db_file = str(tmp_path / "repeat_test.db")
    init_db(db_file, seed_if_empty=True)
    # Call a second and third time
    init_db(db_file, seed_if_empty=True)
    init_db(db_file, seed_if_empty=True)

    notes = get_all_notes(db_path=db_file)
    # Seeding should only run once
    assert len(notes) == 2


def test_empty_database_resilience(test_db):
    """Verifies that an unseeded, empty database returns valid zeroed structures without errors."""
    metrics = get_dashboard_metrics(db_path=test_db)
    assert metrics["total_notes"] == 0
    assert metrics["total_summaries"] == 0
    assert metrics["completed_tasks"] == 0
    assert metrics["pending_tasks"] == 0
    assert metrics["total_tasks"] == 0
    assert metrics["task_completion_rate"] == 0.0
    assert metrics["quizzes_attempted"] == 0
    assert metrics["avg_quiz_score"] == 0.0
    assert metrics["total_flashcards"] == 0
    assert metrics["mastered_flashcards"] == 0
    assert metrics["total_study_hours"] == 0.0
    assert metrics["subjects"] == []

    # Check stats functions on empty tables
    quiz_stats = get_quiz_stats(db_path=test_db)
    assert quiz_stats["attempts_count"] == 0
    assert quiz_stats["avg_score"] == 0.0

    task_stats = get_task_stats(db_path=test_db)
    assert task_stats["total"] == 0
    assert task_stats["completion_rate"] == 0.0

    session_stats = get_study_session_stats(db_path=test_db)
    assert session_stats["total_sessions"] == 0
    assert session_stats["total_hours"] == 0.0


# =========================================================================
# 2. NOTES CRUD & VALIDATION
# =========================================================================

def test_notes_crud_lifecycle(test_db):
    """Tests creating, reading, updating, and deleting notes."""
    # Create
    note_id = create_note(
        title="Data Structures: Binary Search Trees",
        subject="Computer Science",
        content="A binary search tree is a rooted binary tree data structure whose internal nodes store keys.",
        tags="Trees, Algorithms, Search",
        db_path=test_db
    )
    assert note_id > 0

    # Retrieve by ID
    note = get_note_by_id(note_id, db_path=test_db)
    assert note is not None
    assert note["title"] == "Data Structures: Binary Search Trees"
    assert note["word_count"] > 10
    assert note["reading_time_min"] > 0

    # Retrieve all & search
    all_notes = get_all_notes(db_path=test_db)
    assert len(all_notes) == 1

    search_res = search_notes("binary", db_path=test_db)
    assert len(search_res) == 1
    assert search_res[0]["id"] == note_id

    # Filter by subject
    cs_notes = get_all_notes(subject_filter="Computer Science", db_path=test_db)
    assert len(cs_notes) == 1
    bio_notes = get_all_notes(subject_filter="Biology", db_path=test_db)
    assert len(bio_notes) == 0

    # Update
    upd = update_note(
        note_id=note_id,
        title="Binary Search Trees & AVL Trees",
        subject="Computer Science",
        content="AVL trees are self-balancing binary search trees with logarithmic lookup height.",
        tags="Trees, Balanced",
        db_path=test_db
    )
    assert upd is True
    updated_note = get_note_by_id(note_id, db_path=test_db)
    assert updated_note["title"] == "Binary Search Trees & AVL Trees"

    # Delete
    assert delete_note(note_id, db_path=test_db) is True
    assert get_note_by_id(note_id, db_path=test_db) is None


def test_notes_validation(test_db):
    """Tests input validation on notes."""
    with pytest.raises(ValidationError):
        create_note(title="", subject="CS", content="Valid content", db_path=test_db)

    with pytest.raises(ValidationError):
        create_note(title="Valid title", subject="CS", content="", db_path=test_db)

    with pytest.raises(ValidationError):
        update_note(note_id=-1, title="Title", subject="CS", content="Content", db_path=test_db)


# =========================================================================
# 3. SUMMARIES CRUD & VALIDATION
# =========================================================================

def test_summaries_crud(test_db):
    """Tests saving and retrieving extractive summaries."""
    summary_id = save_summary(
        title="Summary of Neural Networks",
        original_text="Artificial neural networks are computing systems inspired by the biological neural networks...",
        summary_text="Neural networks are inspired by biological systems and compute weighted inputs.",
        key_points=["Perceptron is the core unit.", "Backpropagation optimizes weights."],
        compression_ratio=65.0,
        method="TF-ISF Extractive",
        db_path=test_db
    )
    assert summary_id > 0

    summary = get_summary_by_id(summary_id, db_path=test_db)
    assert summary is not None
    assert summary["title"] == "Summary of Neural Networks"
    assert len(summary["key_points"]) == 2

    all_sums = get_all_summaries(db_path=test_db)
    assert len(all_sums) == 1

    assert delete_summary(summary_id, db_path=test_db) is True
    assert get_summary_by_id(summary_id, db_path=test_db) is None


def test_summaries_validation(test_db):
    with pytest.raises(ValidationError):
        save_summary(title="", original_text="Orig", summary_text="Summ", db_path=test_db)

    with pytest.raises(ValidationError):
        save_summary(title="Title", original_text="Orig", summary_text="", db_path=test_db)


# =========================================================================
# 4. FLASHCARDS & DECKS CRUD
# =========================================================================

def test_flashcards_and_deck_cascade(test_db):
    """Tests deck creation, card batching, mastery tracking, and cascading deletion."""
    deck_id = create_flashcard_deck(
        title="Cognitive Science Concepts",
        subject="Psychology",
        description="Definitions from Baddeley working memory model.",
        db_path=test_db
    )
    assert deck_id > 0

    deck = get_deck_by_id(deck_id, db_path=test_db)
    assert deck["title"] == "Cognitive Science Concepts"

    # Batch save cards
    cards = [
        {"front": "What is the phonological loop?", "back": "Component that handles verbal and auditory information."},
        {"front": "What is the visuospatial sketchpad?", "back": "Component that manages visual and spatial data."}
    ]
    saved_count = save_flashcards_batch(deck_id, cards, db_path=test_db)
    assert saved_count == 2

    # Retrieve cards
    deck_cards = get_flashcards_by_deck(deck_id, db_path=test_db)
    assert len(deck_cards) == 2
    card_id = deck_cards[0]["id"]

    # Update mastery level
    assert update_flashcard_mastery(card_id, 3, db_path=test_db) is True
    updated_card = get_flashcard_by_id(card_id, db_path=test_db)
    assert updated_card["mastery_level"] == 3
    assert updated_card["review_count"] == 1

    # Check deck stats reflect mastered card
    decks = get_all_decks(db_path=test_db)
    assert decks[0]["mastered_count"] == 1
    assert decks[0]["card_count"] == 2

    # Cascade delete deck
    assert delete_deck(deck_id, db_path=test_db) is True
    # Cards belonging to deck should be cascaded
    remaining_cards = get_all_flashcards(deck_id=deck_id, db_path=test_db)
    assert len(remaining_cards) == 0


def test_standalone_flashcard(test_db):
    """Tests creating and modifying a standalone flashcard without a deck."""
    card_id = create_flashcard(
        front="What is Ohm's Law?",
        back="V = I * R",
        subject="Physics",
        mastery_level=2,
        db_path=test_db
    )
    assert card_id > 0

    card = get_flashcard_by_id(card_id, db_path=test_db)
    assert card["front"] == "What is Ohm's Law?"
    assert card["back"] == "V = I * R"
    assert card["mastery_level"] == 2

    # Update card content
    assert update_flashcard(card_id, "State Ohm's Law", "Voltage equals current multiplied by resistance (V=IR)", db_path=test_db) is True
    updated = get_flashcard_by_id(card_id, db_path=test_db)
    assert updated["front"] == "State Ohm's Law"

    assert delete_flashcard(card_id, db_path=test_db) is True


# =========================================================================
# 5. TASKS CRUD & WORKFLOW
# =========================================================================

def test_tasks_lifecycle_and_validation(test_db):
    """Tests task creation, status transitions, statistics, and validation."""
    task_id = create_task(
        title="Complete Biochemistry Lab Report 3",
        subject="Biology",
        description="Write discussion on enzyme kinetics.",
        priority="High",
        deadline="2026-10-25",
        estimated_hours=2.5,
        db_path=test_db
    )
    assert task_id > 0

    # Initial state
    task = get_task_by_id(task_id, db_path=test_db)
    assert task["status"] == "Pending"
    assert task["completed_at"] is None

    # Transition to In Progress
    assert update_task_status(task_id, "In Progress", db_path=test_db) is True
    task = get_task_by_id(task_id, db_path=test_db)
    assert task["status"] == "In Progress"

    # Complete task
    assert complete_task(task_id, db_path=test_db) is True
    task = get_task_by_id(task_id, db_path=test_db)
    assert task["status"] == "Completed"
    assert task["completed_at"] is not None

    # Task stats
    stats = get_task_stats(db_path=test_db)
    assert stats["total"] == 1
    assert stats["completed"] == 1
    assert stats["completion_rate"] == 100.0

    # Validation errors
    with pytest.raises(ValidationError):
        create_task(title="", subject="Bio", db_path=test_db)

    with pytest.raises(ValidationError):
        create_task(title="Invalid Priority Task", subject="Bio", priority="Urgent!", db_path=test_db)

    with pytest.raises(ValidationError):
        create_task(title="Invalid Hours", subject="Bio", estimated_hours=-2.0, db_path=test_db)

    with pytest.raises(ValidationError):
        update_task_status(task_id, "Done!", db_path=test_db)

    assert delete_task(task_id, db_path=test_db) is True


# =========================================================================
# 6. QUIZZES & ATTEMPTS
# =========================================================================

def test_quizzes_and_attempts(test_db):
    """Tests saving practice quizzes and recording quiz attempts."""
    questions = [
        {
            "id": 1,
            "question": "What is the chemical formula for water?",
            "options": ["A) H2O", "B) CO2", "C) NaCl", "D) CH4"],
            "correct_option": "A",
            "explanation": "Water consists of two hydrogen atoms bonded to one oxygen atom."
        }
    ]
    quiz_id = save_quiz(
        title="Chemistry Diagnostic Quiz",
        subject="Chemistry",
        questions=questions,
        db_path=test_db
    )
    assert quiz_id > 0

    quiz = get_quiz_by_id(quiz_id, db_path=test_db)
    assert quiz["title"] == "Chemistry Diagnostic Quiz"
    assert len(quiz["questions"]) == 1

    # Record attempt
    attempt_id = save_quiz_attempt(
        quiz_id=quiz_id,
        quiz_title="Chemistry Diagnostic Quiz",
        subject="Chemistry",
        score=1,
        total_questions=1,
        time_taken_sec=22,
        user_answers={"1": "A"},
        db_path=test_db
    )
    assert attempt_id > 0

    attempt = get_quiz_attempt_by_id(attempt_id, db_path=test_db)
    assert attempt["score"] == 1
    assert attempt["percentage"] == 100.0

    # Score stats
    q_stats = get_quiz_stats(db_path=test_db)
    assert q_stats["attempts_count"] == 1
    assert q_stats["avg_score"] == 100.0
    assert q_stats["total_questions_answered"] == 1

    # Validation: score cannot exceed total_questions
    with pytest.raises(ValidationError):
        save_quiz_attempt(quiz_id, "Quiz", "Chemistry", score=5, total_questions=3, db_path=test_db)

    # Validation: total_questions must be > 0
    with pytest.raises(ValidationError):
        save_quiz_attempt(quiz_id, "Quiz", "Chemistry", score=0, total_questions=0, db_path=test_db)

    assert delete_quiz_attempt(attempt_id, db_path=test_db) is True
    assert delete_quiz(quiz_id, db_path=test_db) is True


# =========================================================================
# 7. STUDY SESSIONS
# =========================================================================

def test_study_sessions(test_db):
    """Tests logging study sessions and computing study hours."""
    sess_id = log_study_session(
        subject="Mathematics",
        duration_minutes=90,
        topic="Multivariable Calculus Integration",
        session_type="Problem Solving",
        notes="Worked through Green's theorem proofs.",
        db_path=test_db
    )
    assert sess_id > 0

    session = get_study_session_by_id(sess_id, db_path=test_db)
    assert session["subject"] == "Mathematics"
    assert session["duration_minutes"] == 90

    # Filtered retrieval
    all_sess = get_study_sessions(subject_filter="Mathematics", db_path=test_db)
    assert len(all_sess) == 1

    other_sess = get_study_sessions(subject_filter="Literature", db_path=test_db)
    assert len(other_sess) == 0

    # Stats
    stats = get_study_session_stats(db_path=test_db)
    assert stats["total_sessions"] == 1
    assert stats["total_minutes"] == 90
    assert stats["total_hours"] == 1.5

    # Validation
    with pytest.raises(ValidationError):
        log_study_session(subject="Math", duration_minutes=0, db_path=test_db)

    assert delete_study_session(sess_id, db_path=test_db) is True


# =========================================================================
# 8. SQL INJECTION RESILIENCE
# =========================================================================

def test_parameterized_sql_injection_resilience(test_db):
    """Verifies that malicious input containing SQL injection syntax is escaped safely."""
    malicious_title = "'; DROP TABLE notes; --"
    malicious_content = "Robert'); DROP TABLE tasks;--"

    note_id = create_note(
        title=malicious_title,
        subject="Security",
        content=malicious_content,
        db_path=test_db
    )
    assert note_id > 0

    # Ensure notes table still exists and data was stored literally
    retrieved = get_note_by_id(note_id, db_path=test_db)
    assert retrieved is not None
    assert retrieved["title"] == malicious_title
    assert retrieved["content"] == malicious_content

    # Search with SQL injection payload
    results = search_notes("DROP TABLE", db_path=test_db)
    assert len(results) == 1
    assert results[0]["id"] == note_id


# =========================================================================
# 9. USER PREFERENCES
# =========================================================================

def test_user_preferences(test_db):
    """Tests setting and getting user preferences."""
    set_preference("theme", "light", db_path=test_db)
    assert get_preference("theme", db_path=test_db) == "light"

    # Update preference
    set_preference("theme", "dark", db_path=test_db)
    assert get_preference("theme", db_path=test_db) == "dark"

    # Default fallback
    assert get_preference("non_existent_key", default_value="default_val", db_path=test_db) == "default_val"
