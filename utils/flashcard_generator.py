"""
Flashcard Generator Module for StudySync AI.
Extracts key academic definitions, relationships, processes, and principles
from text notes to create structured Front/Back study flashcards.
"""

import re
from typing import List, Dict, Any, Optional
from utils.text_processor import split_sentences, tokenize_words, tag_pos, get_stop_words, clean_text


def generate_flashcards_from_text(text: str, max_cards: int = 8) -> Dict[str, Any]:
    """
    Extracts high-yield concept-definition pairs from study text to form flashcards.

    Parameters:
        text (str): Source study notes.
        max_cards (int): Maximum number of cards to generate.

    Returns:
        Dict[str, Any]: {
            "success": bool,
            "error": Optional[str],
            "cards": List[Dict[str, str]],
            "total_cards": int
        }
    """
    cleaned = clean_text(text)
    if not cleaned or len(cleaned.split()) < 30:
        return {
            "success": False,
            "error": "The study text is too short to generate flashcards. Please provide at least 30-40 words of study material.",
            "cards": [],
            "total_cards": 0
        }

    sentences = split_sentences(cleaned)
    if not sentences:
        return {
            "success": False,
            "error": "No valid sentences found in the provided text.",
            "cards": [],
            "total_cards": 0
        }

    cards: List[Dict[str, str]] = []
    seen_fronts = set()
    stop_words = get_stop_words()

    # Pattern 1: Definition copular forms ("X is a Y", "X refers to Y", "X is defined as Y")
    def_regex = re.compile(
        r'^(?P<concept>[A-Z][a-zA-Z\s\-]{1,35}?)\s+(?:is|are|refers to|is defined as|consists of|is known as)\s+(?P<definition>.+)$',
        re.IGNORECASE
    )

    # Pattern 2: Colon notation ("Concept: Explanation")
    colon_regex = re.compile(r'^(?P<concept>[A-Za-z\s\-]{2,30}):\s+(?P<definition>.+)$')

    for s in sentences:
        s_clean = s.strip()

        # Check Colon pattern
        colon_match = colon_regex.match(s_clean)
        if colon_match:
            concept = colon_match.group('concept').strip()
            def_text = colon_match.group('definition').strip()
            if concept.lower() not in seen_fronts and len(concept.split()) <= 4:
                cards.append({
                    "front": f"What is {concept}?",
                    "back": def_text
                })
                seen_fronts.add(concept.lower())
                continue

        # Check Definition pattern
        match = def_regex.match(s_clean)
        if match:
            concept = match.group('concept').strip()
            def_text = match.group('definition').strip()
            words_c = concept.split()
            if 1 <= len(words_c) <= 4 and concept.lower() not in stop_words and concept.lower() not in seen_fronts:
                # Format a crisp question
                cards.append({
                    "front": f"What is {concept}?",
                    "back": s_clean
                })
                seen_fronts.add(concept.lower())
                continue

        # Pattern 3: Functional / Mechanism sentence ("X plays a key role in...", "X enables...")
        func_match = re.search(r'([A-Z][a-zA-Z\s\-]{2,25}?)\s+(?:enables|causes|produces|generates|regulates|controls|involves)\s+(.+)', s_clean)
        if func_match and len(cards) < max_cards:
            subj = func_match.group(1).strip()
            if subj.lower() not in seen_fronts and len(subj.split()) <= 3 and subj.lower() not in stop_words:
                cards.append({
                    "front": f"What is the function / effect of {subj}?",
                    "back": s_clean
                })
                seen_fronts.add(subj.lower())

    # Fallback: if we found fewer than 2 definition cards, extract key concepts by salient noun phrases
    if len(cards) < 2:
        for s in sentences:
            if len(cards) >= max_cards:
                break
            tokens = tokenize_words(s, lower=False)
            tagged = tag_pos(tokens)
            nouns = [w for w, tag in tagged if tag.startswith('NN') and len(w) > 3 and w.lower() not in stop_words]
            if nouns:
                top_noun = nouns[0]
                if top_noun.lower() not in seen_fronts:
                    cards.append({
                        "front": f"Explain the role of: {top_noun}",
                        "back": s.strip()
                    })
                    seen_fronts.add(top_noun.lower())

    cards = cards[:max_cards]

    if not cards:
        return {
            "success": False,
            "error": "Could not identify distinct concepts to extract into flashcards. Please provide descriptive text.",
            "cards": [],
            "total_cards": 0
        }

    return {
        "success": True,
        "error": None,
        "cards": cards,
        "total_cards": len(cards)
    }
