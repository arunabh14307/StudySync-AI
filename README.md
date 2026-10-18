# StudySync AI – Academic Productivity Workspace

**StudySync AI** is a comprehensive, privacy-first, offline-capable academic productivity web application designed for college and university students. Built with Python, Streamlit, local Natural Language Processing (NLP), PyMuPDF, and SQLite, StudySync AI operates 100% locally with zero paid API keys, zero external model subscriptions, and complete offline persistence.

---

## 🌟 Features Overview

### 1. 📊 Academic Dashboard (`pages/1_Dashboard.py`)
- Real-time productivity metrics computed from stored database records:
  - Saved notes and extractive summaries count
  - Completed vs. active and pending coursework tasks
  - Practice quiz attempts and cumulative accuracy average
  - Study hours logged across focus sessions
- Dynamic Plotly visualizations for task velocity and quiz accuracy trajectory.
- Upcoming deadline alert feed with one-click task completion.
- Timeline feed of recent study activities with quick study session logger.

### 2. 📝 Smart Notes (`pages/2_Smart_Notes.py`)
- **Document Text Extraction:** Upload lecture notes, book chapters, and research papers in `.pdf` or `.txt` format.
- Uses **PyMuPDF (`fitz`)** for high-performance digital text stream extraction, preserving document metadata (title, author, creation date, modification date, page count).
- **Format Validation & Safety Limits:** Enforces a 25 MB limit for PDFs, 10 MB for TXT files, and header integrity checking (`%PDF-`).
- **Scanned Document Detection:** Detects image-only scans that lack digital text layers, alerting students that Optical Character Recognition (OCR) is required.
- **Readability & Linguistic Intelligence:** Computes Flesch Reading Ease score, average sentence length, syllable count, and estimated reading time.
- **Top Concept Extraction:** Frequency-weighted keyword and keyphrase extraction.
- **Integrated Note Actions:** Launch instant summarization, practice quiz formulation, or flashcard deck generation directly from any saved note.
- **Full Note Lifecycle:** Save, search, filter, in-place edit, and delete with safety confirmation.

### 3. ⚡ AI Document Summarizer (`pages/3_AI_Summarizer.py`)
- Transparent, explainable extractive text summarization without generative hallucinations:
  - **TF-ISF (Term Frequency - Inverse Sentence Frequency):** Ranks sentences by information density.
  - **Structural Position Bias:** Weights introductory and concluding thesis sentences typical in academic textbooks.
  - **Academic Cue Detection:** Boosts definitions, mechanisms, and key experimental findings.
  - **Maximal Marginal Relevance (MMR) Diversity Filter:** Eliminates redundant or repetitive sentences.
- Adjustable compression slider (15% to 65% length retention).
- High-yield bulleted key takeaways extraction.
- Quantitative compression metrics (original words, summary words, % reduction, time saved).
- Save summaries to database or export directly as Markdown (`.md`).

### 4. 🎯 Practice Quiz Generator (`pages/4_Quiz_Generator.py`)
- Automated Multiple-Choice Question (MCQ) formulation from study notes:
  - Definitional questions and Cloze / fill-in-the-blank statements.
  - **Semantic Distractor Generation:** Employs WordNet co-hyponyms (sibling concepts sharing hypernyms) and in-context domain terminology.
  - Citations and detailed explanations referencing the exact source text.
- **Interactive Quiz Modes:**
  - *All Questions at Once:* Multi-question exam view.
  - *One Question at a Time:* Step-by-step review with progress stepper.
- **Safe Attempt Grading:** Prevents duplicate submissions, computes score percentage, time elapsed, and logs attempt history to SQLite.
- Re-take any saved quiz directly from the library.

### 5. 🗂️ Active Recall Flashcards (`pages/5_Flashcards.py`)
- Automated concept extraction from text using definition and colon patterns.
- Interactive study deck mode with question-first flip card display (Front: Question/Concept, Back: Answer/Definition).
- **Spaced Retention Confidence Rating:** 3-tier rating system (*Needs Work [Level 1]*, *Reviewing [Level 2]*, *Mastered [Level 3]*).
- Manual card and deck creator supporting custom subject tagging.
- Deck and card manager with individual card editing and cascade deck deletion.

### 6. ✅ Academic Task Manager (`pages/6_Task_Manager.py`)
- Comprehensive assignment, project, and exam preparation tracker.
- Metadata: Title, instructions, course/subject (preset or custom), due date, priority (*High*, *Medium*, *Low*), initial status (*Pending*, *In Progress*, *Completed*), and estimated hours.
- **Overdue Task Detection:** Identifies overdue tasks (`deadline < today AND status != 'Completed'`) with alert banners, days overdue tags, and an *Overdue* filter.
- **Upcoming Deadlines Panel:** Highlights tasks due within the next 7 days with countdown badges (`Due Today`, `Due Tomorrow`, `Due in X days`).
- Multi-attribute filtering (Status, Priority, Subject, Keyword search) and sorting (Deadlines, Priority, Title).
- In-place popover task editing and deletion confirmation popovers.

### 7. 📈 Study Analytics & Insights (`pages/7_Study_Analytics.py`)
- Performance metrics computed strictly from genuine database records (no fabricated streaks or mock data):
  - Total notes created and cumulative word volume.
  - Total tasks, completion velocity (%), completed, pending, and overdue counts.
  - Quiz attempt volume, average score (%), best score (%), and total questions solved.
  - Total study hours and sessions logged.
- **Interactive Date-Range Filter:** Filter across *All Time*, *Last 7 Days*, *Last 30 Days*, *Last 90 Days*, or *Custom Range*.
- **Plotly Visualizations:**
  - Quiz score trajectory over time with an 80% mastery benchmark line.
  - Subject-wise average score vs. best score comparison bar chart.
  - Task completion breakdown donut chart.
  - Study hours by activity type donut chart.
  - Focused study hours by course bar chart.
- Study session history log and quick focus session recorder.

### 8. 📚 Central Study Library (`pages/8_Study_Library.py`)
- Unified searchable repository for all study materials: Notes, Summaries, Flashcard Decks, and Quizzes.
- Multi-attribute filtering by material type and course subject.
- Full text search across titles, contents, tags, and questions.
- Pagination controls with configurable items per page.
- Direct export to Plain Text (`.txt`) and Markdown (`.md`).
- Delete items with safety confirmation dialogs.

### 9. 🌓 Light & Dark Theme Support
- Persistent theme toggle in the unified sidebar.
- Persisted to SQLite `user_preferences` table across page transitions and reloads.
- CSS variables tailored for both sleek dark mode and high-contrast light mode.

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Core Language** | Python 3.10+ (Tested on 3.13) | Backend logic, NLP pipeline, and database integration |
| **Web Framework** | Streamlit (>= 1.35.0) | Multi-page reactive UI, session state, and component rendering |
| **Document Processing** | PyMuPDF / `fitz` (>= 1.24.0) | High-performance PDF parsing and metadata extraction |
| **Linguistics & NLP** | NLTK (>= 3.8.0) | Sentence tokenization, POS tagging, stopwords, and WordNet ontology |
| **Data & Visualizations**| Pandas (>= 2.0.0), Plotly (>= 5.18.0) | Data frames and dynamic charts |
| **Database** | SQLite3 | Local embedded relational database with parameterized queries |
| **Automated Testing** | Pytest (>= 8.0.0) | Unit, integration, and regression test suites |

---

## 📂 Project Architecture

```
StudySync AI/
├── app.py                      # Application launcher routing to Dashboard
├── requirements.txt            # Python dependencies
├── README.md                   # System documentation
├── .gitignore                  # Git ignore rules
│
├── .streamlit/
│   └── config.toml             # Streamlit server and theme configuration
│
├── pages/
│   ├── 1_Dashboard.py          # Academic productivity dashboard & KPI tiles
│   ├── 2_Smart_Notes.py        # PDF & TXT text extraction, readability scoring
│   ├── 3_AI_Summarizer.py      # Extractive NLP summarizer & key takeaways
│   ├── 4_Quiz_Generator.py     # Practice MCQ generator with WordNet distractors
│   ├── 5_Flashcards.py         # Spaced-repetition flip cards & mastery rating
│   ├── 6_Task_Manager.py       # Coursework tasks, priority levels, deadlines
│   ├── 7_Study_Analytics.py    # Learning analytics and study habit charts
│   └── 8_Study_Library.py      # Global search, artifact browser, and export
│
├── utils/
│   ├── __init__.py
│   ├── database.py             # SQLite CRUD, auto-seeding, and connection manager
│   ├── pdf_processor.py        # PyMuPDF document loader and metadata parser
│   ├── text_processor.py       # Sentence/word tokenization, POS, readability
│   ├── summarizer.py           # Multi-factor TF-ISF extractive summarizer
│   ├── quiz_generator.py       # Question formulation and distractor generation
│   ├── flashcard_generator.py  # Concept-definition pair extractor
│   └── helpers.py              # CSS injection, theme persistence, UI components
│
├── assets/
│   └── styles.css              # Custom SaaS stylesheet, dark/light themes
│
├── data/
│   ├── .gitkeep
│   └── studysync.db            # SQLite database (auto-initialized)
│
└── tests/
    ├── __init__.py
    ├── test_core.py            # Core database and helper tests
    ├── test_database.py        # Database CRUD, foreign keys, and validation
    ├── test_nlp_engine.py      # Tokenizer, POS tagging, and readability
    ├── test_quiz_flashcards.py # Quiz generator and flashcard extractor
    ├── test_smart_notes_library.py # PDF processing and library tests
    ├── test_task_manager_analytics.py # Task management and analytics tests
    └── test_qa_full_pass.py    # Comprehensive QA regression test suite
```

---

## 🧠 NLP Methodology

StudySync AI uses an explainable, deterministic, and locally executed NLP architecture:

1. **Extractive Summarization (TF-ISF + MMR)**:
   - **Term Frequency - Inverse Sentence Frequency (TF-ISF)**: Assesses the information importance of words relative to sentence frequency in the text.
   - **Positional Weighting**: Boosts the opening sentences (introductory/thesis statements) and final sentences (conclusions) common in academic textbook chapters.
   - **Academic Cue Matching**: Identifies structural indicator tokens (`defined as`, `mechanism`, `crucial`, `consists of`, `pathway`).
   - **Maximal Marginal Relevance (MMR)**: Calculates Jaccard vocabulary similarity between selected candidate sentences; rejects candidates with >65% lexical overlap to guarantee diversity.
   - **Order Preservation**: Re-orders selected sentences back into original document sequence to maintain narrative coherence.

2. **MCQ & Semantic Distractor Formulation**:
   - Scans sentences using regex patterns for definitional copular structures (`X is defined as Y`, `X refers to Y`).
   - Applies Part-of-Speech (POS) tagging to isolate key conceptual nouns.
   - Generates distractors by querying the WordNet lexical database for co-hyponyms (sibling concepts under the same hypernym category) or in-context domain nouns from other document sentences.
   - Guarantees 4 mutually distinct options per question.

3. **Readability Scoring (Flesch Reading Ease)**:
   - Evaluates linguistic complexity using the standard formula:
     $$\text{Score} = 206.835 - (1.015 \times \text{ASL}) - (84.6 \times \text{ASW})$$
     Where $\text{ASL}$ is Average Sentence Length and $\text{ASW}$ is Average Syllables per Word.

---

## 💻 Python Version Requirements

- **Supported Python Versions:** Python 3.10, 3.11, 3.12, 3.13
- **Operating Systems:** Windows 10/11, macOS, Linux

---

## ⚙️ Setup & Installation

### 1. Clone or Open the Repository
```bash
cd "c:\Users\arunabh singh\Desktop\StudySync AI"
```

### 2. Set Up a Virtual Environment (Recommended)
```bash
# On Windows (PowerShell):
python -m venv venv
.\venv\Scripts\activate

# On macOS / Linux:
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Verify Local NLTK Corpus Assets
When StudySync AI runs for the first time, required NLTK corpora (`punkt`, `stopwords`, `averaged_perceptron_tagger`, `wordnet`) are downloaded automatically. To pre-download them manually:
```bash
python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True); nltk.download('stopwords', quiet=True); nltk.download('averaged_perceptron_tagger', quiet=True); nltk.download('averaged_perceptron_tagger_eng', quiet=True); nltk.download('wordnet', quiet=True); print('NLTK assets ready!')"
```

---

## ▶️ Application Startup

Launch StudySync AI using Streamlit:

```bash
streamlit run app.py
```

Or via python module runner:

```bash
python -m streamlit run app.py
```

The application will launch and open automatically in your browser at:
`http://localhost:8501`

---

## 🧪 Test Execution

StudySync AI includes a comprehensive automated test suite with **94 test cases** spanning all components:

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run the QA verification suite specifically
python -m pytest tests/test_qa_full_pass.py -v
```

---

## ⚠️ Known Limitations

1. **Scanned PDF Documents**:
   - PyMuPDF extracts text directly from digital text streams. Scanned PDFs (photographs or raster page images without selectable text) require Optical Character Recognition (OCR) preprocessing via tools like Tesseract, Adobe Acrobat, or Google Drive before uploading. The application detects scanned PDFs and alerts the user accordingly.
2. **Extractive vs. Abstractive Summarization**:
   - Summarization is purely extractive: it selects and preserves exact original sentences from the text rather than generating new synthetic text. This guarantees factual accuracy and eliminates hallucinations, but does not rephrase colloquial notes into formal prose.
3. **Language Optimization**:
   - The NLP rules, POS tagging patterns, stopword lists, and WordNet ontology are optimized for English educational materials. Text in non-English languages will be extracted and saved, but linguistic scoring and distractors will fall back to general frequency heuristics.
4. **Local Hardware Constraints**:
   - Document upload size is capped at 25 MB for PDFs and 10 MB for text files to ensure responsive, lag-free in-memory processing on standard student laptops.
