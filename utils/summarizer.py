"""
Extractive NLP Summarization Module for StudySync AI.
Implements a transparent, explainable extractive summarizer:
- Word Frequency Weighting (TF-ISF)
- Structural Lead & Position Bias (academic thesis prioritization)
- Academic Cue & Mechanism Matching
- Duplicate Sentence Deduplication
- Maximal Marginal Relevance (MMR) Diversity Filter
- Original Document Order Preservation
"""

import math
import re
from typing import List, Dict, Any, Tuple, Set
from collections import Counter
from utils.text_processor import (
    split_sentences,
    tokenize_words,
    get_stop_words,
    clean_text,
    get_word_frequencies
)

# Academic cue words that indicate core definitions or conclusions
ACADEMIC_CUES = {
    'defined', 'definition', 'refers', 'consists', 'comprises', 'fundamental',
    'crucial', 'essential', 'important', 'significant', 'demonstrates', 'concludes',
    'therefore', 'indicates', 'results', 'primary', 'key', 'main', 'principle',
    'function', 'mechanism', 'pathway', 'process', 'characteristic', 'structure'
}


def _calculate_jaccard_similarity(words1: set, words2: set) -> float:
    """Calculates Jaccard vocabulary similarity between two sets of words."""
    if not words1 or not words2:
        return 0.0
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    return intersection / union if union > 0 else 0.0


def _deduplicate_sentences(sentences: List[str]) -> List[str]:
    """Removes duplicate or near-identical sentences while preserving order."""
    unique_sentences = []
    seen_normalized: Set[str] = set()

    for s in sentences:
        norm = re.sub(r'\W+', '', s.lower())
        if norm not in seen_normalized and len(norm) > 10:
            seen_normalized.add(norm)
            unique_sentences.append(s)

    return unique_sentences


def generate_summary(text: str, ratio: float = 0.35, min_sentences: int = 2,
                     max_sentences: int = 10, method: str = "Extractive Hybrid") -> Dict[str, Any]:
    """
    Generates an extractive summary by ranking sentences based on term frequency,
    position bias, and academic significance. Preserves exact original sentence wording.

    Parameters:
        text (str): Source study material.
        ratio (float): Summary ratio (0.10 to 0.75).
        min_sentences (int): Minimum sentences to extract.
        max_sentences (int): Maximum sentences in the summary.
        method (str): Strategy description label.

    Returns:
        Dict[str, Any] containing summary text, bulleted key points, and compression metrics.
    """
    cleaned = clean_text(text)
    words = cleaned.split()
    total_word_count = len(words)

    # Validate input length
    if not cleaned or total_word_count < 25:
        return {
            "success": False,
            "error": "The input text is too short to generate a reliable extractive summary (minimum 25 words required).",
            "summary_text": cleaned,
            "key_points": [],
            "original_word_count": total_word_count,
            "summary_word_count": total_word_count,
            "compression_ratio": 0.0,
            "time_saved_min": 0.0
        }

    raw_sentences = split_sentences(cleaned)
    sentences = _deduplicate_sentences(raw_sentences)
    total_sentences = len(sentences)

    if total_sentences < 2:
        return {
            "success": False,
            "error": "The input text does not contain enough distinct sentences to formulate a summary (minimum 2 distinct sentences required).",
            "summary_text": cleaned,
            "key_points": [s for s in sentences],
            "original_word_count": total_word_count,
            "summary_word_count": total_word_count,
            "compression_ratio": 0.0,
            "time_saved_min": 0.0
        }

    # Word Frequency Analysis
    word_freq = get_word_frequencies(cleaned, remove_stopwords=True)
    if not word_freq:
        return {
            "success": False,
            "error": "No meaningful non-stopword tokens found to score sentence importance.",
            "summary_text": cleaned,
            "key_points": [],
            "original_word_count": total_word_count,
            "summary_word_count": total_word_count,
            "compression_ratio": 0.0,
            "time_saved_min": 0.0
        }

    max_freq = max(word_freq.values())
    stop_words = get_stop_words()

    # Sentence Token representations & Word Sets
    sentence_tokens: List[List[str]] = []
    sentence_word_sets: List[set] = []
    for s in sentences:
        tokens = tokenize_words(s, lower=True)
        filtered = [t for t in tokens if t not in stop_words]
        sentence_tokens.append(filtered)
        sentence_word_sets.append(set(filtered))

    # Sentence Level Scoring
    sentence_scores: List[Tuple[int, float]] = []

    for idx, (sentence, tokens) in enumerate(zip(sentences, sentence_tokens)):
        if not tokens:
            sentence_scores.append((idx, 0.0))
            continue

        # 1. Term Frequency Score (normalized by token count)
        tf_score = sum(word_freq.get(w, 0) / max_freq for w in tokens) / len(tokens)

        # 2. Position Bias: academic texts place thesis statements at beginning or conclusion
        if idx == 0:
            position_bias = 1.35
        elif idx == 1:
            position_bias = 1.20
        elif idx == total_sentences - 1:
            position_bias = 1.15
        else:
            position_bias = 1.0 - (0.20 * (idx / total_sentences))

        # 3. Academic Cue Word Boost
        cue_count = sum(1 for w in tokens if w in ACADEMIC_CUES)
        cue_bonus = 1.0 + (0.12 * min(cue_count, 3))

        # 4. Length Factor (penalize extremely short fragments or run-ons)
        raw_word_count = len(sentence.split())
        if raw_word_count < 8:
            length_factor = 0.5
        elif raw_word_count > 50:
            length_factor = 0.8
        else:
            length_factor = 1.0

        final_score = tf_score * position_bias * cue_bonus * length_factor
        sentence_scores.append((idx, final_score))

    # Determine target number of sentences
    target_count = int(math.ceil(total_sentences * ratio))
    target_count = max(min_sentences, min(target_count, max_sentences, total_sentences))

    # Rank candidate sentences by score
    sorted_candidates = sorted(sentence_scores, key=lambda x: x[1], reverse=True)

    # Apply MMR Diversity Filter to avoid repetitive sentences
    selected_indices: List[int] = []
    for candidate_idx, _ in sorted_candidates:
        if len(selected_indices) >= target_count:
            break

        cand_set = sentence_word_sets[candidate_idx]
        is_redundant = False
        for chosen_idx in selected_indices:
            sim = _calculate_jaccard_similarity(cand_set, sentence_word_sets[chosen_idx])
            if sim > 0.65:  # Over 65% vocabulary overlap indicates redundancy
                is_redundant = True
                break

        if not is_redundant:
            selected_indices.append(candidate_idx)

    # In case diversity filter was too strict, backfill with top scored candidates
    if len(selected_indices) < min_sentences:
        for candidate_idx, _ in sorted_candidates:
            if candidate_idx not in selected_indices:
                selected_indices.append(candidate_idx)
            if len(selected_indices) >= min(min_sentences, total_sentences):
                break

    # Re-order selected sentences chronologically to preserve original narrative order
    selected_indices.sort()
    summary_sentences = [sentences[i] for i in selected_indices]
    summary_text = " ".join(summary_sentences)

    # Key takeaways: Extract top distinct scored sentences as bullet points
    top_bullets_indices = sorted(selected_indices, key=lambda i: dict(sentence_scores)[i], reverse=True)[:3]
    top_bullets_indices.sort()
    key_points = [sentences[i].strip() for i in top_bullets_indices]

    # Metrics
    orig_words = len(cleaned.split())
    summ_words = len(summary_text.split())
    compression = round((1 - (summ_words / orig_words)) * 100, 1) if orig_words > 0 else 0.0
    time_saved = round((orig_words - summ_words) / 200, 1)

    return {
        "success": True,
        "error": None,
        "summary_text": summary_text,
        "key_points": key_points,
        "original_word_count": orig_words,
        "summary_word_count": summ_words,
        "compression_ratio": max(0.0, compression),
        "time_saved_min": max(0.0, time_saved),
        "sentence_reduction": f"{len(summary_sentences)} of {total_sentences} sentences",
        "method": method
    }
