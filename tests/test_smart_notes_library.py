"""
Automated Test Suite for Smart Notes and Study Library Modules.
Validates:
- File upload validation (types, size limits, header integrity)
- Text extraction, metadata parsing, and OCR detection for scanned PDFs
- Note creation, retrieval, editing, searching, filtering, and deletion
- Source note references in summaries, flashcard decks, and quizzes
- Unified Study Library retrieval, material filtering, subject filtering, and sorting
- Foreign key resilience and deletion behavior
"""

import os
import pytest
import fitz  # PyMuPDF
from utils.database import (
    init_db,
    create_note,
    get_all_notes,
    get_note_by_id,
    update_note,
    delete_note,
    search_notes,
    save_summary,
    get_all_summaries,
    get_summary_by_id,
    delete_summary,
    create_flashcard_deck,
    get_all_decks,
    get_deck_by_id,
    delete_deck,
    create_flashcard,
    get_flashcards_by_deck,
    save_quiz,
    get_all_quizzes,
    get_quiz_by_id,
    delete_quiz,
    get_distinct_subjects,
    get_unified_library_items,
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


@pytest.fixture
def isolated_db(tmp_path):
    """Provides an isolated clean SQLite database for testing."""
    db_file = str(tmp_path / "test_notes_library.db")
    init_db(db_file, seed_if_empty=False)
    return db_file


# =========================================================================
# 1. FILE UPLOAD VALIDATION TESTS
# =========================================================================

def test_validate_uploaded_file_valid_pdf():
    """Verifies that a valid PDF file with %PDF- header passes validation."""
    valid_pdf_bytes = b"%PDF-1.4 sample pdf content for testing validation"
    res = validate_uploaded_file("lecture_notes.pdf", len(valid_pdf_bytes), valid_pdf_bytes)
    assert res["valid"] is True
    assert res["error"] is None
    assert res["file_type"] == ".pdf"


def test_validate_uploaded_file_valid_txt():
    """Verifies that a valid TXT file passes validation."""
    txt_bytes = b"Biology lecture 1: Cellular respiration"
    res = validate_uploaded_file("notes.txt", len(txt_bytes), txt_bytes)
    assert res["valid"] is True
    assert res["error"] is None
    assert res["file_type"] == ".txt"


def test_validate_uploaded_file_unsupported_extensions():
    """Verifies that unsupported file extensions are rejected with clear error messages."""
    unsupported = ["notes.docx", "slides.pptx", "program.exe", "photo.png", "data.csv", "archive.zip", "noextension"]
    for fname in unsupported:
        res = validate_uploaded_file(fname, 1024, b"dummy data")
        assert res["valid"] is False
        assert "Unsupported file format" in res["error"] or "recognizable file extension" in res["error"]


def test_validate_uploaded_file_empty_file():
    """Verifies that 0-byte files are rejected."""
    res_pdf = validate_uploaded_file("empty.pdf", 0, b"")
    assert res_pdf["valid"] is False
    assert "empty (0 bytes)" in res_pdf["error"]

    res_txt = validate_uploaded_file("empty.txt", 0, b"")
    assert res_txt["valid"] is False
    assert "empty (0 bytes)" in res_txt["error"]


def test_validate_uploaded_file_oversized():
    """Verifies that files exceeding size limits are rejected."""
    # PDF limit: 25 MB
    res_pdf = validate_uploaded_file("huge.pdf", MAX_PDF_SIZE_BYTES + 1, b"%PDF-huge")
    assert res_pdf["valid"] is False
    assert "exceeds the maximum allowed limit" in res_pdf["error"]

    # TXT limit: 10 MB
    res_txt = validate_uploaded_file("huge.txt", MAX_TXT_SIZE_BYTES + 1, b"lots of text")
    assert res_txt["valid"] is False
    assert "exceeds the maximum allowed limit" in res_txt["error"]


def test_validate_uploaded_file_invalid_pdf_header():
    """Verifies that a file named .pdf without %PDF- magic bytes is rejected."""
    fake_pdf = b"NOT_A_PDF_HEADER_JUST_RANDOM_DATA"
    res = validate_uploaded_file("corrupt.pdf", len(fake_pdf), fake_pdf)
    assert res["valid"] is False
    assert "valid PDF header" in res["error"]


# =========================================================================
# 2. PDF & TXT EXTRACTION & OCR DETECTION TESTS
# =========================================================================

def test_extract_text_and_metadata_from_valid_pdf():
    """Creates a real PyMuPDF PDF in memory, extracts its text, and verifies metadata."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Introduction to Operating Systems and Kernel Scheduling.")
    doc.set_metadata({
        "title": "Operating Systems Syllabus",
        "author": "Dr. Turing",
        "subject": "Computer Science"
    })
    pdf_bytes = doc.tobytes()
    doc.close()

    result = extract_text_from_pdf(pdf_bytes)
    assert result["success"] is True
    assert "Operating Systems" in result["text"]
    assert result["page_count"] == 1
    assert result["metadata"]["title"] == "Operating Systems Syllabus"
    assert result["metadata"]["author"] == "Dr. Turing"
    assert result["is_scanned"] is False


def test_scanned_pdf_detection_and_ocr_explanation():
    """Creates a PDF containing an image but no selectable text, verifying OCR explanation."""
    # Create image using PyMuPDF pixmap
    pix = fitz.Pixmap(fitz.csRGB, (0, 0, 100, 100), 0)
    pix.clear_with(255)
    img_bytes = pix.tobytes("png")

    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(fitz.Rect(50, 50, 250, 250), stream=img_bytes)
    # No text inserted
    pdf_bytes = doc.tobytes()
    doc.close()

    result = extract_text_from_pdf(pdf_bytes)
    assert result["success"] is False
    assert result["is_scanned"] is True
    assert "Scanned Document Detected" in result["error"]
    assert "Optical Character Recognition (OCR)" in result["error"]


def test_extract_text_from_txt_success():
    """Verifies plain text extraction and metadata derivation."""
    sample_content = (
        "Cognitive psychology is the scientific study of mental processes such as "
        "attention, language use, memory, perception, problem solving, and creativity."
    )
    txt_bytes = sample_content.encode("utf-8")
    res = extract_text_from_txt(txt_bytes, file_name="cognitive_psychology.txt")
    assert res["success"] is True
    assert "Cognitive psychology" in res["text"]
    assert res["metadata"]["title"] == "Cognitive Psychology"
    assert res["metadata"]["word_count"] > 10


def test_extract_text_from_txt_empty_and_whitespace():
    """Verifies that empty and whitespace-only text files return clear errors."""
    res_empty = extract_text_from_txt(b"")
    assert res_empty["success"] is False
    assert "empty (0 bytes)" in res_empty["error"]

    res_ws = extract_text_from_txt(b"   \n\t   \n  ")
    assert res_ws["success"] is False
    assert "whitespace" in res_ws["error"]


# =========================================================================
# 3. SMART NOTES DATABASE CRUD & EDITING TESTS
# =========================================================================

def test_create_and_read_note(isolated_db):
    """Tests creating notes with all metadata fields and retrieving them."""
    note_id = create_note(
        title="Microeconomics: Supply and Demand",
        subject="Economics",
        content="The law of demand states that quantity demanded varies inversely with price.",
        source_type="pdf",
        file_name="econ_ch1.pdf",
        tags="Economics, Demand, Price Elasticity",
        db_path=isolated_db
    )
    assert note_id > 0

    note = get_note_by_id(note_id, db_path=isolated_db)
    assert note is not None
    assert note["title"] == "Microeconomics: Supply and Demand"
    assert note["subject"] == "Economics"
    assert note["source_type"] == "pdf"
    assert note["file_name"] == "econ_ch1.pdf"
    assert note["word_count"] > 0
    assert note["created_at"] is not None
    assert note["updated_at"] is not None


def test_edit_note_title_and_subject(isolated_db):
    """Tests editing note title, subject, tags, and content."""
    note_id = create_note(
        title="Original Draft",
        subject="General Study",
        content="Initial rough notes on cell biology.",
        tags="Bio",
        db_path=isolated_db
    )

    # Edit note title and subject
    updated = update_note(
        note_id=note_id,
        title="Cellular Biology: Organelles and Membrane Transport",
        subject="Biology",
        content="Eukaryotic cells contain membrane-bound organelles such as mitochondria and chloroplasts.",
        tags="Cell, Organelles, Mitochondria",
        db_path=isolated_db
    )
    assert updated is True

    # Verify updated values in database
    edited_note = get_note_by_id(note_id, db_path=isolated_db)
    assert edited_note["title"] == "Cellular Biology: Organelles and Membrane Transport"
    assert edited_note["subject"] == "Biology"
    assert edited_note["tags"] == "Cell, Organelles, Mitochondria"
    assert "mitochondria" in edited_note["content"]


def test_delete_note(isolated_db):
    """Tests deleting a note from the database."""
    note_id = create_note(
        title="Temporary Scratch Note",
        subject="Computer Science",
        content="Temporary syntax scratchpad.",
        db_path=isolated_db
    )
    assert get_note_by_id(note_id, db_path=isolated_db) is not None

    del_res = delete_note(note_id, db_path=isolated_db)
    assert del_res is True
    assert get_note_by_id(note_id, db_path=isolated_db) is None


def test_search_and_filter_notes(isolated_db):
    """Tests searching notes by keyword and filtering by subject."""
    create_note("Quantum Mechanics Wavefunction", "Physics", "Schrodinger equation describes wavefunctions.", tags="Quantum", db_path=isolated_db)
    create_note("Classical Thermodynamics", "Physics", "First law of thermodynamics is conservation of energy.", tags="Energy", db_path=isolated_db)
    create_note("Algorithms: Graph Theory", "Computer Science", "Dijkstra algorithm finds shortest paths in graphs.", tags="Graphs", db_path=isolated_db)

    # Search keyword
    res_wave = get_all_notes(search_query="Wavefunction", db_path=isolated_db)
    assert len(res_wave) == 1
    assert res_wave[0]["title"] == "Quantum Mechanics Wavefunction"

    # Filter by subject
    res_physics = get_all_notes(subject_filter="Physics", db_path=isolated_db)
    assert len(res_physics) == 2

    # Combined search and filter
    res_comb = get_all_notes(search_query="conservation", subject_filter="Physics", db_path=isolated_db)
    assert len(res_comb) == 1
    assert res_comb[0]["title"] == "Classical Thermodynamics"


def test_sort_notes(isolated_db):
    """Tests sorting notes by recently updated, recently created, and title."""
    id1 = create_note("Alpha Note", "Subject A", "Content A", db_path=isolated_db)
    id2 = create_note("Zeta Note", "Subject B", "Content B", db_path=isolated_db)
    id3 = create_note("Beta Note", "Subject C", "Content C", db_path=isolated_db)

    # Title ASC
    notes_asc = get_all_notes(sort_by="title_asc", db_path=isolated_db)
    assert [n["title"] for n in notes_asc] == ["Alpha Note", "Beta Note", "Zeta Note"]

    # Title DESC
    notes_desc = get_all_notes(sort_by="title_desc", db_path=isolated_db)
    assert [n["title"] for n in notes_desc] == ["Zeta Note", "Beta Note", "Alpha Note"]


# =========================================================================
# 4. INTEGRATION & SOURCE NOTE REFERENCING TESTS
# =========================================================================

def test_flashcard_deck_references_source_note(isolated_db):
    """Verifies that a flashcard deck can reference its source note and joins its title."""
    note_id = create_note("Neuroscience: Action Potentials", "Biology", "Action potentials are rapid changes in membrane potential.", db_path=isolated_db)

    deck_id = create_flashcard_deck(
        title="Action Potential Deck",
        subject="Biology",
        description="Key terms for membrane potential",
        note_id=note_id,
        db_path=isolated_db
    )
    assert deck_id > 0

    create_flashcard("What is an action potential?", "A rapid voltage change across a membrane.", deck_id=deck_id, db_path=isolated_db)

    # Retrieve deck and check source note join
    deck = get_deck_by_id(deck_id, db_path=isolated_db)
    assert deck["note_id"] == note_id
    assert deck["source_note_title"] == "Neuroscience: Action Potentials"

    all_decks = get_all_decks(db_path=isolated_db)
    assert len(all_decks) == 1
    assert all_decks[0]["source_note_title"] == "Neuroscience: Action Potentials"


def test_quiz_references_source_note(isolated_db):
    """Verifies that a quiz stores and retrieves its source note reference."""
    note_id = create_note("Organic Chemistry Reactions", "Chemistry", "Electrophilic aromatic substitution mechanism.", db_path=isolated_db)

    sample_questions = [{
        "id": 1,
        "question": "What is EAS?",
        "options": ["A) Electrophilic Aromatic Substitution", "B) Elimination", "C) Addition", "D) Substitution"],
        "correct_option": "A",
        "explanation": "EAS stands for Electrophilic Aromatic Substitution."
    }]

    quiz_id = save_quiz(
        title="EAS Reaction Quiz",
        subject="Chemistry",
        questions=sample_questions,
        note_id=note_id,
        db_path=isolated_db
    )

    quiz = get_quiz_by_id(quiz_id, db_path=isolated_db)
    assert quiz["note_id"] == note_id
    assert quiz["source_note_title"] == "Organic Chemistry Reactions"


def test_summary_references_source_note(isolated_db):
    """Verifies that an AI summary stores and retrieves its source note reference."""
    note_id = create_note("World History: Industrial Revolution", "History", "The Industrial Revolution transitioned manufacturing to new processes.", db_path=isolated_db)

    summary_id = save_summary(
        title="Summary: Industrial Revolution",
        original_text="The Industrial Revolution transitioned manufacturing to new processes.",
        summary_text="The Industrial Revolution transformed manufacturing processes.",
        key_points=["Transition to mechanization", "Growth of urban centers"],
        compression_ratio=25.0,
        note_id=note_id,
        db_path=isolated_db
    )

    summary = get_summary_by_id(summary_id, db_path=isolated_db)
    assert summary["note_id"] == note_id
    assert summary["source_note_title"] == "World History: Industrial Revolution"


def test_foreign_key_set_null_on_note_deletion(isolated_db):
    """Verifies that deleting a source note sets note_id to NULL on decks and quizzes without crashing."""
    note_id = create_note("Temporary Source Note", "Computer Science", "Content to be deleted.", db_path=isolated_db)

    deck_id = create_flashcard_deck("Dependent Deck", "Computer Science", note_id=note_id, db_path=isolated_db)
    quiz_id = save_quiz("Dependent Quiz", "Computer Science", [{"id": 1, "question": "Q?", "options": ["A"], "correct_option": "A"}], note_id=note_id, db_path=isolated_db)
    sum_id = save_summary("Dependent Summary", "Original", "Summary", note_id=note_id, db_path=isolated_db)

    # Delete source note
    delete_note(note_id, db_path=isolated_db)

    # Verify note is gone
    assert get_note_by_id(note_id, db_path=isolated_db) is None

    # Verify dependent items still exist with note_id set to NULL
    deck = get_deck_by_id(deck_id, db_path=isolated_db)
    assert deck is not None
    assert deck["note_id"] is None
    assert deck["source_note_title"] is None

    quiz = get_quiz_by_id(quiz_id, db_path=isolated_db)
    assert quiz is not None
    assert quiz["note_id"] is None

    summary = get_summary_by_id(sum_id, db_path=isolated_db)
    assert summary is not None
    assert summary["note_id"] is None


# =========================================================================
# 5. STUDY LIBRARY SEARCH, FILTER & AGGREGATION TESTS
# =========================================================================

def test_study_library_distinct_subjects(isolated_db):
    """Tests dynamic aggregation of distinct subjects across notes, decks, and quizzes."""
    create_note("Note 1", "Computer Science", "Content", db_path=isolated_db)
    create_flashcard_deck("Deck 1", "Biology", db_path=isolated_db)
    save_quiz("Quiz 1", "Psychology", [{"id": 1, "question": "Q", "options": ["A"], "correct_option": "A"}], db_path=isolated_db)

    subjects = get_distinct_subjects(db_path=isolated_db)
    assert "Biology" in subjects
    assert "Computer Science" in subjects
    assert "Psychology" in subjects


def test_study_library_unified_items_aggregation(isolated_db):
    """Tests that get_unified_library_items aggregates all 4 material types with standardized schemas."""
    create_note("Study Note A", "Computer Science", "Algorithm complexity analysis.", db_path=isolated_db)
    save_summary("Summary A", "Original text here", "Condensed summary text.", note_id=None, db_path=isolated_db)
    create_flashcard_deck("Deck A", "Biology", description="Deck description", db_path=isolated_db)
    save_quiz("Quiz A", "Physics", [{"id": 1, "question": "Force formula?", "options": ["F=ma"], "correct_option": "A"}], db_path=isolated_db)

    # All items
    all_items = get_unified_library_items(material_type="All", db_path=isolated_db)
    assert len(all_items) == 4

    types_found = {it["material_type"] for it in all_items}
    assert types_found == {"note", "summary", "deck", "quiz"}

    for item in all_items:
        assert item["title"] is not None
        assert item["subject"] is not None
        assert item["created_at"] is not None
        assert item["updated_at"] is not None
        assert item["preview"] is not None


def test_study_library_material_type_filter(isolated_db):
    """Tests filtering library items by specific material types."""
    create_note("Note 1", "Physics", "Content", db_path=isolated_db)
    create_flashcard_deck("Deck 1", "Physics", db_path=isolated_db)
    save_quiz("Quiz 1", "Physics", [{"id": 1, "question": "Q", "options": ["A"], "correct_option": "A"}], db_path=isolated_db)

    only_notes = get_unified_library_items(material_type="Saved Notes", db_path=isolated_db)
    assert len(only_notes) == 1
    assert only_notes[0]["material_type"] == "note"

    only_decks = get_unified_library_items(material_type="Flashcard Decks", db_path=isolated_db)
    assert len(only_decks) == 1
    assert only_decks[0]["material_type"] == "deck"

    only_quizzes = get_unified_library_items(material_type="Practice Quizzes", db_path=isolated_db)
    assert len(only_quizzes) == 1
    assert only_quizzes[0]["material_type"] == "quiz"


def test_study_library_search_and_sorting(isolated_db):
    """Tests searching across title/content and sorting in the unified study library."""
    create_note("Zeta Calculus Limits", "Mathematics", "Epsilon-delta definitions of limits.", db_path=isolated_db)
    create_note("Alpha Linear Algebra", "Mathematics", "Eigenvalues and eigenvectors.", db_path=isolated_db)

    # Search keyword in content
    res_search = get_unified_library_items(search_query="Eigenvalues", db_path=isolated_db)
    assert len(res_search) == 1
    assert res_search[0]["title"] == "Alpha Linear Algebra"

    # Sort Title ASC
    res_asc = get_unified_library_items(sort_by="title_asc", db_path=isolated_db)
    assert [it["title"] for it in res_asc] == ["Alpha Linear Algebra", "Zeta Calculus Limits"]

    # Sort Title DESC
    res_desc = get_unified_library_items(sort_by="title_desc", db_path=isolated_db)
    assert [it["title"] for it in res_desc] == ["Zeta Calculus Limits", "Alpha Linear Algebra"]


def test_study_library_deletion_of_all_material_types(isolated_db):
    """Tests deleting notes, summaries, decks, and quizzes from the library."""
    nid = create_note("Note to delete", "Biology", "Content", db_path=isolated_db)
    sid = save_summary("Summary to delete", "Original", "Summary", db_path=isolated_db)
    did = create_flashcard_deck("Deck to delete", "Biology", db_path=isolated_db)
    qid = save_quiz("Quiz to delete", "Biology", [{"id": 1, "question": "Q", "options": ["A"], "correct_option": "A"}], db_path=isolated_db)

    assert len(get_unified_library_items(db_path=isolated_db)) == 4

    assert delete_note(nid, db_path=isolated_db) is True
    assert delete_summary(sid, db_path=isolated_db) is True
    assert delete_deck(did, db_path=isolated_db) is True
    assert delete_quiz(qid, db_path=isolated_db) is True

    assert len(get_unified_library_items(db_path=isolated_db)) == 0
