"""
Tests for StudySync AI - Task Manager & Study Analytics Modules.
Validates task CRUD, status transitions, validation errors, sorting, multi-attribute filtering,
overdue detection, upcoming deadlines, quiz analytics, study session tracking,
date-range filtering, and empty-state resilience.
"""

import os
import pytest
import datetime
from utils.database import (
    init_db,
    create_task,
    get_all_tasks,
    get_task_by_id,
    update_task,
    update_task_status,
    complete_task,
    delete_task,
    get_task_stats,
    get_upcoming_tasks,
    create_note,
    get_notes_stats,
    save_quiz,
    save_quiz_attempt,
    get_all_quiz_attempts,
    get_quiz_stats,
    get_subject_quiz_performance,
    log_study_session,
    get_study_sessions,
    get_study_session_stats,
    delete_study_session,
    ValidationError
)


@pytest.fixture
def clean_db(tmp_path):
    """Provides a fresh, isolated test database for each test function."""
    db_file = str(tmp_path / "test_tm_analytics.db")
    init_db(db_file, seed_if_empty=False)
    return db_file


# =============================================================================
# 1. TASK CRUD & FIELD EDITING TESTS
# =============================================================================

def test_create_task_with_all_fields(clean_db):
    """Verifies creating an academic task with custom attributes and initial status."""
    task_id = create_task(
        title="Operating Systems Lab 2",
        subject="Computer Science",
        description="Implement round-robin CPU scheduler in C++",
        priority="High",
        deadline="2026-11-05",
        estimated_hours=4.5,
        status="In Progress",
        db_path=clean_db
    )
    assert task_id > 0

    task = get_task_by_id(task_id, db_path=clean_db)
    assert task is not None
    assert task["title"] == "Operating Systems Lab 2"
    assert task["subject"] == "Computer Science"
    assert task["description"] == "Implement round-robin CPU scheduler in C++"
    assert task["priority"] == "High"
    assert task["deadline"] == "2026-11-05"
    assert task["estimated_hours"] == 4.5
    assert task["status"] == "In Progress"
    assert task["completed_at"] is None


def test_create_task_completed_sets_timestamp(clean_db):
    """Verifies that creating a task with Completed status automatically sets completed_at."""
    task_id = create_task(
        title="Read Syllabus",
        subject="Psychology",
        priority="Low",
        deadline="2026-10-20",
        estimated_hours=0.5,
        status="Completed",
        db_path=clean_db
    )
    task = get_task_by_id(task_id, db_path=clean_db)
    assert task["status"] == "Completed"
    assert task["completed_at"] is not None


def test_task_validation_errors(clean_db):
    """Verifies validation constraints on title, priority, status, and estimated hours."""
    # Empty title
    with pytest.raises(ValidationError, match="Task title cannot be empty"):
        create_task(title="   ", subject="CS", db_path=clean_db)

    # Invalid priority
    with pytest.raises(ValidationError, match="Invalid priority"):
        create_task(title="Valid Title", subject="CS", priority="Critical", db_path=clean_db)

    # Invalid status
    with pytest.raises(ValidationError, match="Invalid status"):
        create_task(title="Valid Title", subject="CS", status="Abandoned", db_path=clean_db)

    # Non-positive estimated hours
    with pytest.raises(ValidationError, match="Estimated hours must be greater than zero"):
        create_task(title="Valid Title", subject="CS", estimated_hours=0.0, db_path=clean_db)

    with pytest.raises(ValidationError, match="Estimated hours must be greater than zero"):
        create_task(title="Valid Title", subject="CS", estimated_hours=-1.5, db_path=clean_db)


def test_edit_task_all_fields(clean_db):
    """Verifies editing existing task attributes including deadline, priority, and status."""
    task_id = create_task(
        title="Linear Algebra Quiz Review",
        subject="Mathematics",
        priority="Medium",
        deadline="2026-10-28",
        estimated_hours=2.0,
        db_path=clean_db
    )

    success = update_task(
        task_id=task_id,
        title="Linear Algebra Midterm Prep",
        subject="Math Advanced",
        description="Focus on eigenvalues and eigenvectors.",
        priority="High",
        deadline="2026-10-31",
        status="In Progress",
        estimated_hours=5.0,
        db_path=clean_db
    )
    assert success is True

    updated = get_task_by_id(task_id, db_path=clean_db)
    assert updated["title"] == "Linear Algebra Midterm Prep"
    assert updated["subject"] == "Math Advanced"
    assert updated["description"] == "Focus on eigenvalues and eigenvectors."
    assert updated["priority"] == "High"
    assert updated["deadline"] == "2026-10-31"
    assert updated["status"] == "In Progress"
    assert updated["estimated_hours"] == 5.0


def test_task_status_transitions_and_reopen(clean_db):
    """Verifies completing, updating status, and reopening tasks."""
    task_id = create_task(
        title="Submit Essay Draft",
        subject="Literature",
        priority="Medium",
        db_path=clean_db
    )

    # Mark complete
    assert complete_task(task_id, db_path=clean_db) is True
    t_comp = get_task_by_id(task_id, db_path=clean_db)
    assert t_comp["status"] == "Completed"
    assert t_comp["completed_at"] is not None

    # Reopen to Pending
    assert update_task_status(task_id, "Pending", db_path=clean_db) is True
    t_reopen = get_task_by_id(task_id, db_path=clean_db)
    assert t_reopen["status"] == "Pending"
    assert t_reopen["completed_at"] is None

    # Transition to In Progress
    assert update_task_status(task_id, "In Progress", db_path=clean_db) is True
    t_prog = get_task_by_id(task_id, db_path=clean_db)
    assert t_prog["status"] == "In Progress"


def test_task_deletion(clean_db):
    """Verifies deleting tasks by ID and non-existent ID handling."""
    task_id = create_task(title="Temporary Task", subject="CS", db_path=clean_db)
    assert delete_task(task_id, db_path=clean_db) is True
    assert get_task_by_id(task_id, db_path=clean_db) is None
    # Deleting non-existent ID
    assert delete_task(99999, db_path=clean_db) is False


# =============================================================================
# 2. FILTERING, SORTING, OVERDUE & UPCOMING DEADLINES
# =============================================================================

def test_task_filtering_by_status_priority_subject(clean_db):
    """Tests multi-attribute filtering across status, priority, and subject."""
    create_task(title="Task A", subject="Biology", priority="High", status="Pending", db_path=clean_db)
    create_task(title="Task B", subject="Biology", priority="Low", status="Completed", db_path=clean_db)
    create_task(title="Task C", subject="Physics", priority="High", status="In Progress", db_path=clean_db)
    create_task(title="Task D", subject="Physics", priority="Medium", status="Pending", db_path=clean_db)

    # Filter by status
    pending = get_all_tasks(status_filter="Pending", db_path=clean_db)
    assert len(pending) == 2
    assert {t["title"] for t in pending} == {"Task A", "Task D"}

    # Filter by priority
    high_prio = get_all_tasks(priority_filter="High", db_path=clean_db)
    assert len(high_prio) == 2
    assert {t["title"] for t in high_prio} == {"Task A", "Task C"}

    # Filter by subject
    bio_tasks = get_all_tasks(subject_filter="Biology", db_path=clean_db)
    assert len(bio_tasks) == 2
    assert {t["title"] for t in bio_tasks} == {"Task A", "Task B"}

    # Combined filter
    combined = get_all_tasks(status_filter="Pending", priority_filter="High", subject_filter="Biology", db_path=clean_db)
    assert len(combined) == 1
    assert combined[0]["title"] == "Task A"


def test_task_sorting_options(clean_db):
    """Verifies sorting by deadline (asc/desc), priority (high/low), and title."""
    create_task(title="Charlie Task", subject="CS", priority="Low", deadline="2026-11-10", db_path=clean_db)
    create_task(title="Alpha Task", subject="CS", priority="High", deadline="2026-11-01", db_path=clean_db)
    create_task(title="Bravo Task", subject="CS", priority="Medium", deadline="2026-11-05", db_path=clean_db)

    # Deadline ascending
    dl_asc = get_all_tasks(sort_by="deadline_asc", db_path=clean_db)
    assert [t["title"] for t in dl_asc] == ["Alpha Task", "Bravo Task", "Charlie Task"]

    # Deadline descending
    dl_desc = get_all_tasks(sort_by="deadline_desc", db_path=clean_db)
    assert [t["title"] for t in dl_desc] == ["Charlie Task", "Bravo Task", "Alpha Task"]

    # Priority high first
    prio_high = get_all_tasks(sort_by="priority_high_first", db_path=clean_db)
    assert [t["priority"] for t in prio_high] == ["High", "Medium", "Low"]

    # Priority low first
    prio_low = get_all_tasks(sort_by="priority_low_first", db_path=clean_db)
    assert [t["priority"] for t in prio_low] == ["Low", "Medium", "High"]

    # Title ascending
    title_asc = get_all_tasks(sort_by="title_asc", db_path=clean_db)
    assert [t["title"] for t in title_asc] == ["Alpha Task", "Bravo Task", "Charlie Task"]


def test_overdue_task_detection_and_filtering(clean_db):
    """Tests overdue logic: deadline < today and status != 'Completed'."""
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    last_week = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    # Overdue task 1: Pending with yesterday's deadline
    t1 = create_task(title="Overdue Homework", subject="Math", deadline=yesterday, status="Pending", db_path=clean_db)
    # Overdue task 2: In Progress with last week's deadline
    t2 = create_task(title="Overdue Project", subject="CS", deadline=last_week, status="In Progress", db_path=clean_db)
    # Not overdue: Completed despite past deadline
    t3 = create_task(title="Finished Lab", subject="Bio", deadline=yesterday, status="Completed", db_path=clean_db)
    # Not overdue: Future deadline
    t4 = create_task(title="Upcoming Quiz", subject="Physics", deadline=tomorrow, status="Pending", db_path=clean_db)

    # Filter with status_filter='Overdue'
    overdue_tasks = get_all_tasks(status_filter="Overdue", db_path=clean_db)
    assert len(overdue_tasks) == 2
    assert {t["id"] for t in overdue_tasks} == {t1, t2}

    # Verify task stats reflect correct overdue count
    stats = get_task_stats(db_path=clean_db)
    assert stats["overdue"] == 2
    assert stats["total"] == 4
    assert stats["completed"] == 1


def test_upcoming_tasks_window(clean_db):
    """Verifies get_upcoming_tasks retrieves non-completed tasks within N days."""
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    in_3_days = (datetime.date.today() + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
    in_6_days = (datetime.date.today() + datetime.timedelta(days=6)).strftime("%Y-%m-%d")
    in_14_days = (datetime.date.today() + datetime.timedelta(days=14)).strftime("%Y-%m-%d")

    t_today = create_task(title="Due Today", subject="CS", deadline=today_str, status="Pending", db_path=clean_db)
    t_3d = create_task(title="Due in 3 days", subject="Math", deadline=in_3_days, status="Pending", db_path=clean_db)
    t_6d = create_task(title="Due in 6 days", subject="Bio", deadline=in_6_days, status="In Progress", db_path=clean_db)
    t_far = create_task(title="Due in 2 weeks", subject="Psych", deadline=in_14_days, status="Pending", db_path=clean_db)
    t_done = create_task(title="Completed already", subject="CS", deadline=in_3_days, status="Completed", db_path=clean_db)

    upcoming_7 = get_upcoming_tasks(days=7, db_path=clean_db)
    upcoming_ids = [t["id"] for t in upcoming_7]
    assert t_today in upcoming_ids
    assert t_3d in upcoming_ids
    assert t_6d in upcoming_ids
    assert t_far not in upcoming_ids
    assert t_done not in upcoming_ids


# =============================================================================
# 3. STUDY ANALYTICS: QUIZZES, SESSIONS, AND METRIC CALCULATIONS
# =============================================================================

def test_notes_stats_aggregation_and_date_filtering(clean_db):
    """Verifies notes counts, word counts, and date range filtering."""
    create_note(title="Algorithms", subject="CS", content="Graph traversal and sorting algorithms in detail.", db_path=clean_db)
    create_note(title="Cognition", subject="Psychology", content="Sensory memory, working memory, and long-term encoding.", db_path=clean_db)

    stats = get_notes_stats(db_path=clean_db)
    assert stats["total_notes"] == 2
    assert stats["total_words"] > 0
    assert stats["avg_words"] > 0

    # Specific date range matching today
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    stats_today = get_notes_stats(start_date=today_str, end_date=today_str, db_path=clean_db)
    assert stats_today["total_notes"] == 2

    # Past date range matching nothing
    stats_past = get_notes_stats(start_date="2020-01-01", end_date="2020-01-02", db_path=clean_db)
    assert stats_past["total_notes"] == 0
    assert stats_past["total_words"] == 0


def test_quiz_analytics_and_subject_performance(clean_db):
    """Tests quiz attempt recording, accuracy statistics, and subject-wise breakdown."""
    q_id = save_quiz(
        title="Data Structures Quiz",
        subject="Computer Science",
        questions=[{"question": "What is an array?", "options": ["A", "B"], "answer": "A"}],
        db_path=clean_db
    )

    # Record attempts for Computer Science
    save_quiz_attempt(quiz_id=q_id, quiz_title="Data Structures Quiz", subject="Computer Science", score=4, total_questions=5, db_path=clean_db)  # 80.0%
    save_quiz_attempt(quiz_id=q_id, quiz_title="Data Structures Quiz", subject="Computer Science", score=5, total_questions=5, db_path=clean_db)  # 100.0%

    # Record attempt for Biology
    save_quiz_attempt(quiz_id=None, quiz_title="Cell Biology Quiz", subject="Biology", score=6, total_questions=10, db_path=clean_db)  # 60.0%

    # Overall Quiz Stats
    stats = get_quiz_stats(db_path=clean_db)
    assert stats["attempts_count"] == 3
    assert stats["highest_score"] == 100.0
    assert stats["lowest_score"] == 60.0
    # Average: (80 + 100 + 60) / 3 = 80.0%
    assert stats["avg_score"] == 80.0
    assert stats["total_questions_answered"] == 20

    # Subject-wise performance
    subj_perf = get_subject_quiz_performance(db_path=clean_db)
    assert len(subj_perf) == 2

    cs_perf = next(p for p in subj_perf if p["subject"] == "Computer Science")
    assert cs_perf["attempts_count"] == 2
    assert cs_perf["avg_score"] == 90.0
    assert cs_perf["best_score"] == 100.0

    bio_perf = next(p for p in subj_perf if p["subject"] == "Biology")
    assert bio_perf["attempts_count"] == 1
    assert bio_perf["avg_score"] == 60.0
    assert bio_perf["best_score"] == 60.0


def test_study_session_logging_and_stats(clean_db):
    """Tests logging study sessions and calculating cumulative focused hours."""
    # Duration validation
    with pytest.raises(ValidationError):
        log_study_session(subject="CS", duration_minutes=0, db_path=clean_db)

    with pytest.raises(ValidationError):
        log_study_session(subject="CS", duration_minutes=-30, db_path=clean_db)

    # Valid sessions
    s1 = log_study_session(subject="Computer Science", duration_minutes=60, topic="Dynamic Programming", session_type="Problem Solving", db_path=clean_db)
    s2 = log_study_session(subject="Biology", duration_minutes=30, topic="Cell Membranes", session_type="Reading", db_path=clean_db)
    s3 = log_study_session(subject="Computer Science", duration_minutes=90, topic="Compiler Design", session_type="Project Work", db_path=clean_db)

    assert s1 > 0 and s2 > 0 and s3 > 0

    sessions = get_study_sessions(db_path=clean_db)
    assert len(sessions) == 3

    # Filter sessions by subject
    cs_sessions = get_study_sessions(subject_filter="Computer Science", db_path=clean_db)
    assert len(cs_sessions) == 2

    # Stats
    stats = get_study_session_stats(db_path=clean_db)
    assert stats["total_sessions"] == 3
    assert stats["total_minutes"] == 180
    assert stats["total_hours"] == 3.0
    assert stats["avg_duration_minutes"] == 60.0

    # Delete session
    assert delete_study_session(s1, db_path=clean_db) is True
    assert len(get_study_sessions(db_path=clean_db)) == 2


def test_date_range_filtering_on_analytics(clean_db):
    """Verifies date range filters on quiz attempts and study sessions."""
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # Add records
    save_quiz_attempt(quiz_id=None, quiz_title="Quiz A", subject="CS", score=9, total_questions=10, db_path=clean_db)
    log_study_session(subject="CS", duration_minutes=45, topic="Review", db_path=clean_db)

    # Range covering today
    q_stats = get_quiz_stats(start_date=today_str, end_date=today_str, db_path=clean_db)
    assert q_stats["attempts_count"] == 1
    assert q_stats["avg_score"] == 90.0

    s_stats = get_study_session_stats(start_date=today_str, end_date=today_str, db_path=clean_db)
    assert s_stats["total_sessions"] == 1
    assert s_stats["total_minutes"] == 45

    # Range in the past with no data
    past_start = "2021-01-01"
    past_end = "2021-01-31"

    q_empty = get_quiz_stats(start_date=past_start, end_date=past_end, db_path=clean_db)
    assert q_empty["attempts_count"] == 0
    assert q_empty["avg_score"] == 0.0

    s_empty = get_study_session_stats(start_date=past_start, end_date=past_end, db_path=clean_db)
    assert s_empty["total_sessions"] == 0
    assert s_empty["total_hours"] == 0.0


def test_analytics_empty_state_resilience(clean_db):
    """Verifies that empty tables return zeroed structures without division by zero errors."""
    task_stats = get_task_stats(db_path=clean_db)
    assert task_stats["total"] == 0
    assert task_stats["completed"] == 0
    assert task_stats["completion_rate"] == 0.0
    assert task_stats["overdue"] == 0
    assert task_stats["due_soon"] == 0

    quiz_stats = get_quiz_stats(db_path=clean_db)
    assert quiz_stats["attempts_count"] == 0
    assert quiz_stats["avg_score"] == 0.0
    assert quiz_stats["highest_score"] == 0.0
    assert quiz_stats["lowest_score"] == 0.0

    subj_perf = get_subject_quiz_performance(db_path=clean_db)
    assert subj_perf == []

    session_stats = get_study_session_stats(db_path=clean_db)
    assert session_stats["total_sessions"] == 0
    assert session_stats["total_hours"] == 0.0
    assert session_stats["avg_duration_minutes"] == 0.0

    notes_stats = get_notes_stats(db_path=clean_db)
    assert notes_stats["total_notes"] == 0
    assert notes_stats["total_words"] == 0
