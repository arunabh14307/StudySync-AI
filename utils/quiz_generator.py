"""
Rule-Based NLP Quiz Generator for StudySync AI.
Formulates transparent, rule-based multiple-choice questions (MCQs) from study material
using Part-of-Speech tagging, definitional syntactic patterns, WordNet ontology,
and in-context domain distractors.
"""

import re
import random
from typing import List, Dict, Any, Optional, Set, Tuple
from utils.text_processor import (
    split_sentences,
    tokenize_words,
    tag_pos,
    get_stop_words,
    clean_text
)

# Safe WordNet import for semantic distractor generation
try:
    from nltk.corpus import wordnet as wn
    _WORDNET_AVAILABLE = True
except Exception:
    _WORDNET_AVAILABLE = False


def _get_wordnet_distractors(target_word: str, target_pos: str = 'n', count: int = 3) -> List[str]:
    """
    Finds semantically plausible distractors via WordNet co-hyponyms
    (concepts sharing the same parent category/hypernym).
    """
    if not _WORDNET_AVAILABLE or not target_word:
        return []

    distractors: Set[str] = set()
    try:
        wn_pos = wn.NOUN if target_pos.startswith('n') else wn.VERB if target_pos.startswith('v') else None
        if not wn_pos:
            return []

        synsets = wn.synsets(target_word.lower(), pos=wn_pos)
        if not synsets:
            return []

        # Find hypernyms (parent classes) to discover sibling concepts
        primary_syn = synsets[0]
        hypernyms = primary_syn.hypernyms()
        for hyper in hypernyms:
            for sibling in hyper.hyponyms():
                for lemma in sibling.lemmas():
                    name = lemma.name().replace('_', ' ')
                    if (name.lower() != target_word.lower() and
                            len(name) > 2 and
                            name.isalpha() and
                            name.lower() not in [d.lower() for d in distractors]):
                        formatted = name.capitalize() if target_word[0].isupper() else name.lower()
                        distractors.add(formatted)
                        if len(distractors) >= count * 2:
                            break
    except Exception:
        pass

    return list(distractors)[:count]


def _extract_candidate_facts(sentences: List[str]) -> List[Dict[str, Any]]:
    """
    Scans sentences for definitive, factual, or explanatory statements suitable for MCQs.
    Identifies target keywords using POS tags and definition patterns.
    """
    candidates = []
    stop_words = get_stop_words()

    for sentence in sentences:
        s_clean = sentence.strip()
        words = s_clean.split()
        if len(words) < 6 or len(words) > 45:
            continue

        tokens = tokenize_words(s_clean, lower=False, strip_punct=True)
        if len(tokens) < 4:
            continue

        tagged = tag_pos(tokens)

        # 1. Definitional Copular Patterns: "X is a Y", "X refers to Y", "X is defined as Y"
        definition_pattern = re.search(
            r'^(?P<subject>[A-Z][a-zA-Z\s\-]{1,30}?)\s+(?:is|are|was|were|refers to|is defined as|consists of|is known as)\s+(?P<predicate>.+)$',
            s_clean,
            re.IGNORECASE
        )

        if definition_pattern:
            subj = definition_pattern.group('subject').strip()
            pred = definition_pattern.group('predicate').strip()
            subj_words = subj.split()
            if 1 <= len(subj_words) <= 3 and subj.lower() not in stop_words and len(subj) >= 3:
                candidates.append({
                    "sentence": s_clean,
                    "target": subj,
                    "type": "definition",
                    "predicate": pred
                })
                continue

        # 2. Key entity / noun extraction for cloze question
        nouns = [
            word for word, tag in tagged
            if tag.startswith('NN') and len(word) > 3 and word.lower() not in stop_words and not word.isdigit()
        ]
        if nouns:
            # Prioritize capitalized terms or longer descriptive nouns
            sorted_nouns = sorted(nouns, key=lambda w: (w[0].isupper(), len(w)), reverse=True)
            chosen_target = sorted_nouns[0]
            candidates.append({
                "sentence": s_clean,
                "target": chosen_target,
                "type": "cloze",
                "predicate": ""
            })

    return candidates


def generate_quiz_from_text(text: str, num_questions: int = 5,
                            difficulty: str = "Medium", allow_academic_fallback: bool = True) -> Dict[str, Any]:
    """
    Generates rule-based multiple-choice practice questions with distinct distractors,
    explanations, and separate storage of the correct answer.

    Parameters:
        text (str): Source study material.
        num_questions (int): Number of questions to formulate.
        difficulty (str): 'Easy', 'Medium', 'Hard'.
        allow_academic_fallback (bool): Whether to use domain fallbacks if text lacks distractors.

    Returns:
        Dict[str, Any] with success status, questions list, and error details.
    """
    cleaned = clean_text(text)
    words = cleaned.split()
    total_words = len(words)

    # Validate input content length
    if not cleaned or total_words < 35:
        return {
            "success": False,
            "error": "The study material is too short to generate a reliable quiz (minimum 35-40 words required).",
            "questions": [],
            "total_questions": 0
        }

    sentences = split_sentences(cleaned)
    if len(sentences) < 2:
        return {
            "success": False,
            "error": "The study material does not contain enough distinct sentences to formulate questions.",
            "questions": [],
            "total_questions": 0
        }

    candidates = _extract_candidate_facts(sentences)
    if not candidates:
        return {
            "success": False,
            "error": "Could not identify clear factual or conceptual statements in the text to formulate test questions.",
            "questions": [],
            "total_questions": 0
        }

    # Extract all candidate domain nouns from text as potential distractors
    all_tokens = tokenize_words(cleaned, lower=False, strip_punct=True)
    all_tagged = tag_pos(all_tokens)
    stop_words = get_stop_words()
    domain_nouns = list(set([
        w for w, tag in all_tagged
        if tag.startswith('NN') and len(w) > 3 and w.lower() not in stop_words and not w.isdigit()
    ]))

    # Deterministic seed for consistent generation with fallback
    random.seed(42)
    random.shuffle(candidates)

    selected_questions: List[Dict[str, Any]] = []
    used_targets: Set[str] = set()

    academic_fallbacks = [
        "Equilibrium", "Hypothesis", "Synthesis", "Variables", "Correlation",
        "Catalyst", "Parameters", "Molecules", "Substrates", "Coefficients"
    ]

    for cand in candidates:
        if len(selected_questions) >= num_questions:
            break

        target = cand["target"]
        target_lower = target.lower()
        if target_lower in used_targets:
            continue

        sentence = cand["sentence"]

        # Formulate question stem
        if cand["type"] == "definition" and cand.get("predicate"):
            pred = cand["predicate"]
            if difficulty == "Easy":
                q_text = f"What is defined as: \"{pred[:110]}{'...' if len(pred) > 110 else ''}\"?"
            else:
                blanked = re.sub(r'\b' + re.escape(target) + r'\b', '___________', sentence, count=1, flags=re.IGNORECASE)
                q_text = f"Complete the statement: \"{blanked}\""
        else:
            blanked = re.sub(r'\b' + re.escape(target) + r'\b', '___________', sentence, count=1, flags=re.IGNORECASE)
            q_text = f"Fill in the blank: \"{blanked}\""

        # Distractor assembly
        distractors: List[str] = []

        # 1. WordNet co-hyponyms
        wn_dist = _get_wordnet_distractors(target, count=3)
        for d in wn_dist:
            if d.lower() != target_lower and d.lower() not in [x.lower() for x in distractors]:
                distractors.append(d)

        # 2. In-context domain nouns from other sentences
        if len(distractors) < 3:
            filtered_domain = [
                d for d in domain_nouns
                if d.lower() != target_lower and d.lower() not in [x.lower() for x in distractors]
            ]
            random.shuffle(filtered_domain)
            for d in filtered_domain:
                distractors.append(d)
                if len(distractors) >= 3:
                    break

        # 3. Academic fallback concepts (if permitted)
        if len(distractors) < 3 and allow_academic_fallback:
            for fb in academic_fallbacks:
                if (fb.lower() != target_lower and
                        fb.lower() not in [x.lower() for x in distractors]):
                    distractors.append(fb)
                    if len(distractors) >= 3:
                        break

        # Strictly verify we have exactly 3 distinct distractors
        distractors = distractors[:3]
        if len(distractors) < 3:
            # Cannot formulate valid 4-option MCQ without duplicate options; reject candidate
            continue

        # Assemble 4 unique options
        all_options = [target] + distractors
        # Verify no duplicate options
        if len(set([opt.lower() for opt in all_options])) != 4:
            continue

        random.shuffle(all_options)
        correct_idx = all_options.index(target)
        option_letters = ['A', 'B', 'C', 'D']
        correct_letter = option_letters[correct_idx]

        formatted_options = [f"{letter}) {opt}" for letter, opt in zip(option_letters, all_options)]
        explanation = f"Correct Answer: {correct_letter} ({target}).\nContext from notes: \"{sentence}\""

        selected_questions.append({
            "id": len(selected_questions) + 1,
            "question": q_text,
            "options": formatted_options,
            "correct_option": correct_letter,
            "correct_text": target,
            "explanation": explanation
        })

        used_targets.add(target_lower)

    if not selected_questions:
        return {
            "success": False,
            "error": "Insufficient distinct terminology in the source material to formulate multiple-choice options with valid distractors.",
            "questions": [],
            "total_questions": 0
        }

    return {
        "success": True,
        "error": None,
        "questions": selected_questions,
        "total_questions": len(selected_questions)
    }
