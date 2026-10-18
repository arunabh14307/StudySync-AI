"""
Comprehensive Test Suite for StudySync AI Core NLP Engine.
Covers all required edge cases and scenarios:
1. Empty input (text, PDF, TXT, summaries, quizzes)
2. Very short text
3. Normal educational paragraphs
4. Repeated words (word frequency and keyword scoring)
5. Duplicate sentences (summarizer deduplication)
6. Incorrect file types (invalid PDF header, corrupt bytes)
7. PDFs with no extractable text (blank or scanned/image-only pages requiring OCR)
8. Quiz questions with insufficient distractors (option deduplication & rejection)
"""

import pytest
import fitz  # PyMuPDF
from utils.text_processor import (
    clean_text,
    split_sentences,
    tokenize_words,
    get_word_frequencies,
    extract_keywords,
    calculate_readability,
    tag_pos
)
from utils.summarizer import generate_summary
from utils.quiz_generator import generate_quiz_from_text
from utils.pdf_processor import extract_text_from_pdf, extract_text_from_txt


# =========================================================================
# 1. EMPTY INPUT
# =========================================================================

def test_empty_input_handling():
    """Verifies that all NLP functions gracefully handle empty or whitespace-only inputs."""
    assert clean_text("") == ""
    assert clean_text("   \n\t  ") == ""
    assert split_sentences("") == []
    assert split_sentences("   ") == []
    assert tokenize_words("") == []
    assert get_word_frequencies("") == {}
    assert extract_keywords("") == []

    # Readability on empty
    readability = calculate_readability("")
    assert readability["word_count"] == 0
    assert readability["sentence_count"] == 0
    assert readability["flesch_score"] == 0.0

    # Summarizer on empty
    sum_res = generate_summary("")
    assert sum_res["success"] is False
    assert "too short" in sum_res["error"].lower()

    # Quiz generator on empty
    quiz_res = generate_quiz_from_text("")
    assert quiz_res["success"] is False
    assert "too short" in quiz_res["error"].lower()

    # PDF & TXT on empty bytes
    pdf_res = extract_text_from_pdf(b"")
    assert pdf_res["success"] is False
    assert "empty" in pdf_res["error"].lower()

    txt_res = extract_text_from_txt(b"")
    assert txt_res["success"] is False
    assert "empty" in txt_res["error"].lower()


# =========================================================================
# 2. VERY SHORT TEXT
# =========================================================================

def test_very_short_text_handling():
    """Verifies graceful handling of short text fragments without misleading outputs."""
    short_input = "Hello world."

    # Text processing
    tokens = tokenize_words(short_input)
    assert len(tokens) == 2

    kw = extract_keywords(short_input)
    assert isinstance(kw, list)

    readability = calculate_readability(short_input)
    assert readability["word_count"] == 2

    # Summarizer rejects short documents
    sum_res = generate_summary(short_input)
    assert sum_res["success"] is False
    assert "too short" in sum_res["error"].lower()

    # Quiz generator rejects short text
    quiz_res = generate_quiz_from_text(short_input)
    assert quiz_res["success"] is False
    assert "too short" in quiz_res["error"].lower()


# =========================================================================
# 3. NORMAL EDUCATIONAL PARAGRAPHS
# =========================================================================

def test_normal_educational_paragraph():
    """Verifies standard textbook material processing across all modules."""
    educational_text = (
        "Mitochondria are membrane-bound organelles that generate most of the chemical energy needed to power the cell's biochemical reactions. "
        "Chemical energy produced by the mitochondria is stored in a small molecule called adenosine triphosphate (ATP). "
        "Glycolysis occurs in the cytoplasm and breaks one glucose molecule into two molecules of pyruvate, generating a net gain of two ATP molecules. "
        "The citric acid cycle takes place in the mitochondrial matrix, producing electron carriers NADH and FADH2 alongside carbon dioxide. "
        "Oxidative phosphorylation occurs along the inner mitochondrial membrane via the electron transport chain and ATP synthase. "
        "This terminal stage generates the majority of cellular energy, yielding approximately thirty to thirty-two ATP molecules per glucose."
    )

    # 1. Text processing & keywords
    sentences = split_sentences(educational_text)
    assert len(sentences) >= 5

    keywords = extract_keywords(educational_text, top_n=5)
    assert len(keywords) >= 3
    kw_names = [k[0].lower() for k in keywords]
    assert any("mitochondria" in k or "atp" in k or "cellular" in k for k in kw_names)

    # 2. Readability
    read = calculate_readability(educational_text)
    assert read["word_count"] > 50
    assert read["sentence_count"] >= 5
    assert 0 <= read["flesch_score"] <= 100

    # 3. Summarization
    sum_res = generate_summary(educational_text, ratio=0.4)
    assert sum_res["success"] is True
    assert sum_res["summary_word_count"] < sum_res["original_word_count"]
    assert len(sum_res["key_points"]) >= 1
    # Verify original sentence wording is preserved in summary
    assert any(s in educational_text for s in sum_res["key_points"])

    # 4. Quiz generation
    quiz_res = generate_quiz_from_text(educational_text, num_questions=3)
    assert quiz_res["success"] is True
    assert len(quiz_res["questions"]) >= 1

    for q in quiz_res["questions"]:
        assert len(q["options"]) == 4
        assert len(set(q["options"])) == 4  # Exactly 4 unique options
        assert q["correct_option"] in ['A', 'B', 'C', 'D']
        assert q["correct_text"] is not None
        assert "explanation" in q


# =========================================================================
# 4. REPEATED WORDS
# =========================================================================

def test_repeated_words_frequency_and_keywords():
    """Verifies that repetitive word distributions are correctly tallied without skewing."""
    text_with_repeats = (
        "Quantum computing relies on quantum bits or qubits. "
        "Quantum superposition allows qubits to exist in multiple states simultaneously. "
        "Quantum entanglement enables correlated states between distant quantum particles."
    )
    freqs = get_word_frequencies(text_with_repeats, remove_stopwords=True)
    assert freqs["quantum"] >= 4
    assert freqs["qubits"] >= 2

    keywords = extract_keywords(text_with_repeats, top_n=5)
    top_word = keywords[0][0].lower()
    assert "quantum" in top_word


# =========================================================================
# 5. DUPLICATE SENTENCES
# =========================================================================

def test_duplicate_sentences_deduplication():
    """Verifies that identical or duplicated sentences are filtered out by the summarizer."""
    text_with_duplicates = (
        "Photosynthesis is the process by which green plants transform light energy into chemical energy. "
        "Photosynthesis is the process by which green plants transform light energy into chemical energy. "
        "Chlorophyll absorbs light in the blue and red portions of the electromagnetic spectrum. "
        "During this process, water and carbon dioxide are converted into oxygen and glucose. "
        "During this process, water and carbon dioxide are converted into oxygen and glucose."
    )
    sum_res = generate_summary(text_with_duplicates, ratio=0.6)
    assert sum_res["success"] is True

    # Check that the summary text does not repeat the exact same sentence twice
    summary_sentences = split_sentences(sum_res["summary_text"])
    unique_summary_sentences = set([s.strip().lower() for s in summary_sentences])
    assert len(summary_sentences) == len(unique_summary_sentences)


# =========================================================================
# 6. INCORRECT FILE TYPES
# =========================================================================

def test_incorrect_file_types_and_corrupt_bytes():
    """Verifies error handling when uploaded files have invalid headers or corrupted structures."""
    # Fake PDF without %PDF header
    invalid_pdf_bytes = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
    res = extract_text_from_pdf(invalid_pdf_bytes)
    assert res["success"] is False
    assert "invalid file format" in res["error"].lower() or "pdf header" in res["error"].lower()

    # Corrupt PDF header with broken trailer
    corrupt_pdf_bytes = b"%PDF-1.4\nCorrupted content without xref or catalog trailer."
    corrupt_res = extract_text_from_pdf(corrupt_pdf_bytes)
    assert corrupt_res["success"] is False
    assert "corrupted" in corrupt_res["error"].lower() or "failed to parse" in corrupt_res["error"].lower()


# =========================================================================
# 7. PDFS WITH NO EXTRACTABLE TEXT (SCANNED OR BLANK)
# =========================================================================

def test_pdf_with_no_extractable_text():
    """Verifies that blank or image-only scanned PDFs notify the user that OCR is required."""
    doc = fitz.open()
    page = doc.new_page()
    # Draw a geometric rectangle without any selectable text
    page.draw_rect(fitz.Rect(50, 50, 200, 200), color=(0, 0, 1), fill=(0, 1, 0))
    pdf_bytes = doc.write()
    doc.close()

    res = extract_text_from_pdf(pdf_bytes)
    assert res["success"] is False
    assert "no selectable text" in res["error"].lower() or "blank" in res["error"].lower()


# =========================================================================
# 8. QUIZ QUESTIONS WITH INSUFFICIENT DISTRACTORS
# =========================================================================

def test_quiz_with_insufficient_distractors():
    """
    Verifies that when text lacks enough distinct terms and academic fallback is disabled,
    the generator refuses to emit malformed questions with duplicate options.
    """
    sparse_text = "The cat is asleep. The cat is sleeping peacefully in the quiet room."
    # Without academic fallbacks, cannot formulate 4 unique options
    res = generate_quiz_from_text(sparse_text, num_questions=2, allow_academic_fallback=False)
    # Must either reject or return success=False cleanly
    if not res["success"]:
        assert "insufficient" in res["error"].lower() or "too short" in res["error"].lower()
    else:
        # If any question was formed, all 4 options must be strictly distinct
        for q in res["questions"]:
            clean_opts = [re.sub(r'^[A-D]\)\s*', '', opt).strip().lower() for opt in q["options"]]
            assert len(clean_opts) == len(set(clean_opts))
