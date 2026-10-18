"""
Text Processing and NLP Engine for StudySync AI.
Provides text normalization, abbreviation-aware sentence segmentation,
tokenization, stopword filtering, word frequencies, key phrase extraction,
and readability metrics.
"""

import re
import string
import math
from typing import List, Dict, Any, Tuple, Set
from collections import Counter

# Safe NLTK imports with robust fallback handling
try:
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
    from nltk import pos_tag
    _NLTK_AVAILABLE = True
except Exception:
    _NLTK_AVAILABLE = False

# Academic and common English stopwords fallback
DEFAULT_STOPWORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've",
    "you'll", "you'd", 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself',
    'she', "she's", 'her', 'hers', 'herself', 'it', "it's", 'its', 'itself', 'they', 'them',
    'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', "that'll",
    'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
    'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or',
    'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against',
    'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from',
    'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once',
    'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more',
    'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
    'too', 'very', 's', 't', 'can', 'will', 'just', 'don', "don't", 'should', "should've",
    'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn', "couldn't",
    'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't",
    'isn', "isn't", 'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan',
    "shan't", 'shouldn', "shouldn't", 'wasn', "wasn't", 'weren', "weren't", 'won', "won't",
    'wouldn', "wouldn't", 'also', 'furthermore', 'therefore', 'however', 'moreover', 'thus',
    'et', 'al', 'eg', 'ie', 'figure', 'table', 'chapter', 'section', 'page', 'one', 'two', 'using'
}

# Common academic abbreviations to protect from false sentence boundaries
COMMON_ABBREVIATIONS = (
    'e.g.', 'i.e.', 'et al.', 'dr.', 'prof.', 'vs.', 'fig.', 'vol.', 'no.',
    'approx.', 'dept.', 'univ.', 'ed.', 'ref.', 'inc.', 'co.', 'corp.'
)


def get_stop_words() -> set:
    """Returns a set of English stop words (from NLTK if available, else default set)."""
    if _NLTK_AVAILABLE:
        try:
            sw = set(stopwords.words('english'))
            sw.update({'also', 'thus', 'therefore', 'furthermore', 'moreover', 'figure', 'table', 'example', 'one', 'two'})
            return sw
        except Exception:
            pass
    return DEFAULT_STOPWORDS


def clean_text(text: str) -> str:
    """
    Cleans and standardizes input text without destroying meaningful punctuation,
    math symbols, or hyphenated terms.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Normalize unicode quotes and dashes
    text = text.replace('“', '"').replace('”', '"').replace('’', "'").replace('‘', "'")
    text = text.replace('—', ' - ').replace('–', ' - ')
    
    # Fix hyphenated line breaks (e.g., 'trans-\nport' -> 'transport')
    text = re.sub(r'(\b[a-zA-Z]+)-\s*\n\s*([a-zA-Z]+\b)', r'\1\2', text)
    
    # Standardize line breaks and tabs to spaces
    text = re.sub(r'[\r\n\t]+', ' ', text)
    
    # Collapse multiple spaces into a single space
    text = re.sub(r'[ ]{2,}', ' ', text)
    
    return text.strip()


def split_sentences(text: str) -> List[str]:
    """
    Splits text into sentences, preserving abbreviations and decimal numbers.
    Filters out empty lines and non-sentence fragments.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return []

    cleaned = clean_text(text)
    if not cleaned:
        return []

    # Protect abbreviations by temporarily replacing period with placeholder
    protected_text = cleaned
    for abbr in COMMON_ABBREVIATIONS:
        placeholder = abbr.replace('.', '@#@')
        protected_text = re.sub(re.escape(abbr), placeholder, protected_text, flags=re.IGNORECASE)

    # Protect decimal numbers (e.g., 3.14 -> 3@#@14)
    protected_text = re.sub(r'(\d+)\.(\d+)', r'\1@#@\2', protected_text)

    # Sentence splitting
    if _NLTK_AVAILABLE:
        try:
            raw_sentences = sent_tokenize(protected_text)
        except Exception:
            raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', protected_text)
    else:
        raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', protected_text)

    # Restore placeholders and clean
    sentences = []
    for s in raw_sentences:
        restored = s.replace('@#@', '.').strip()
        # Keep sentences with at least 2 words and reasonable character length
        if len(restored.split()) >= 2 and len(restored) >= 12:
            sentences.append(restored)

    return sentences


def tokenize_words(text: str, lower: bool = True, strip_punct: bool = True) -> List[str]:
    """Tokenizes text into individual words."""
    if not text or not isinstance(text, str):
        return []

    if lower:
        text = text.lower()

    if _NLTK_AVAILABLE:
        try:
            tokens = word_tokenize(text)
            if strip_punct:
                return [t for t in tokens if t.isalnum() and len(t) > 1 and not t.isdigit()]
            return [t for t in tokens if t.strip()]
        except Exception:
            pass

    # Regex tokenization fallback
    if strip_punct:
        return [w for w in re.findall(r'\b[a-zA-Z][a-zA-Z0-9\-]*\b', text) if len(w) > 1 and not w.isdigit()]
    return re.findall(r'\S+', text)


def tag_pos(tokens: List[str]) -> List[Tuple[str, str]]:
    """Part-of-speech tagging for tokens."""
    if not tokens:
        return []
    if _NLTK_AVAILABLE:
        try:
            return pos_tag(tokens)
        except Exception:
            pass
    # Fallback heuristic: assume nouns for capitalized words or alphanumeric tokens
    return [(w, 'NNP' if w and w[0].isupper() else 'NN') for w in tokens]


def get_word_frequencies(text: str, remove_stopwords: bool = True) -> Dict[str, int]:
    """Calculates word frequency counts for a document."""
    if not text or not isinstance(text, str):
        return {}

    tokens = tokenize_words(text, lower=True, strip_punct=True)
    if remove_stopwords:
        stop_words = get_stop_words()
        tokens = [t for t in tokens if t not in stop_words]

    return dict(Counter(tokens))


def extract_keywords(text: str, top_n: int = 10, include_phrases: bool = True) -> List[Tuple[str, float]]:
    """
    Extracts high-value keywords and key phrases (bigrams/noun collocations)
    using frequency-length scoring and stopword filtration.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return []

    words = tokenize_words(text, lower=True, strip_punct=True)
    stop_words = get_stop_words()
    filtered_words = [w for w in words if w not in stop_words and len(w) > 2]

    if not filtered_words:
        return []

    total_words = len(filtered_words)
    word_counts = Counter(filtered_words)
    candidate_scores: Dict[str, float] = {}

    # 1. Unigram scoring (Normalized TF * Length Bonus)
    for word, count in word_counts.items():
        tf = count / total_words
        length_bonus = 1.0 + (min(len(word), 12) / 25.0)
        score = tf * length_bonus * 100.0
        candidate_scores[word.title()] = round(score, 2)

    # 2. Key phrase extraction (Bigrams & Trigrams)
    if include_phrases and len(words) >= 4:
        raw_words = tokenize_words(text, lower=False, strip_punct=True)
        # Find adjacent pairs of meaningful words (Noun-Noun, Adj-Noun)
        for i in range(len(raw_words) - 1):
            w1 = raw_words[i]
            w2 = raw_words[i + 1]
            if (w1.lower() not in stop_words and w2.lower() not in stop_words and
                    len(w1) > 2 and len(w2) > 2 and not w1.isdigit() and not w2.isdigit()):
                phrase = f"{w1} {w2}".title()
                # Count phrase occurrences in cleaned text
                phrase_count = len(re.findall(re.escape(phrase), text, re.IGNORECASE))
                if phrase_count >= 1:
                    phrase_score = (phrase_count / (total_words / 2.0)) * 140.0
                    candidate_scores[phrase] = round(phrase_score, 2)

    # Sort descending by score
    sorted_candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_candidates[:top_n]


def count_syllables(word: str) -> int:
    """Estimates the number of syllables in an English word."""
    word = word.lower().strip()
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    word = re.sub(r'(?:[^laeiouy]|ed|es|e)$', '', word)
    word = re.sub(r'^y', '', word)
    matches = re.findall(r'[aeiouy]{1,2}', word)
    return max(1, len(matches))


def calculate_readability(text: str) -> Dict[str, Any]:
    """
    Calculates readability statistics including Flesch Reading Ease score,
    average sentence length, word count, and estimated reading time.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return {
            "flesch_score": 0.0,
            "reading_ease": "N/A",
            "word_count": 0,
            "sentence_count": 0,
            "avg_sentence_length": 0.0,
            "estimated_reading_time_min": 0.0
        }

    sentences = split_sentences(text)
    words = tokenize_words(text, lower=False)
    
    word_count = len(words)
    sentence_count = max(1, len(sentences))
    
    if word_count == 0:
        return {
            "flesch_score": 0.0,
            "reading_ease": "N/A",
            "word_count": 0,
            "sentence_count": 0,
            "avg_sentence_length": 0.0,
            "estimated_reading_time_min": 0.0
        }

    syllable_count = sum(count_syllables(w) for w in words)
    avg_sentence_len = word_count / sentence_count
    avg_syllables_per_word = syllable_count / word_count
    
    # Flesch Reading Ease Formula
    flesch = 206.835 - (1.015 * avg_sentence_len) - (84.6 * avg_syllables_per_word)
    flesch = max(0.0, min(100.0, round(flesch, 1)))

    if flesch >= 80:
        level = "Very Easy (Middle School)"
    elif flesch >= 65:
        level = "Standard / Plain English"
    elif flesch >= 50:
        level = "Fairly Difficult (High School)"
    elif flesch >= 30:
        level = "Difficult (College Level)"
    else:
        level = "Very Academic / Technical"

    reading_time = round(word_count / 200, 1)

    return {
        "flesch_score": flesch,
        "reading_ease": level,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": round(avg_sentence_len, 1),
        "estimated_reading_time_min": reading_time
    }
