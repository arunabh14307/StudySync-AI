"""
Database module for StudySync AI.
Provides a persistent SQLite database layer with parameterized SQL queries,
connection lifecycle management, automatic schema initialization, starter seeding,
input validation, and CRUD operations across all study entities.
"""

import sqlite3
import os
import json
from contextlib import contextmanager
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Generator, Tuple

# Default database directory and path
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "studysync.db")


# =========================================================================
# Custom Exceptions
# =========================================================================

class DatabaseError(Exception):
    """Base exception for StudySync database errors."""
    pass


class ValidationError(DatabaseError):
    """Raised when data validation fails before executing database queries."""
    pass


class RecordNotFoundError(DatabaseError):
    """Raised when an operation targets a record ID that does not exist."""
    pass


# =========================================================================
# Connection & Lifecycle Management
# =========================================================================

def resolve_db_path(db_path: Optional[str] = None) -> str:
    """Returns the provided db_path or falls back to default DB_PATH."""
    path = db_path if db_path is not None else DB_PATH
    # Handle in-memory database paths
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return path


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Creates and returns a raw connection to the SQLite database.
    Row factory is set to sqlite3.Row and foreign keys are enabled.
    Caller is responsible for closing the connection, or use get_db_cursor().
    """
    path = resolve_db_path(db_path)
    conn = sqlite3.connect(path, timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db_cursor(db_path: Optional[str] = None) -> Generator[sqlite3.Cursor, None, None]:
    """
    Context manager that yields a cursor, automatically commits transactions,
    rolls back on unhandled exceptions, and safely closes the connection.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =========================================================================
# Schema Initialization & Seeding
# =========================================================================

def init_db(db_path: Optional[str] = None, seed_if_empty: bool = True) -> None:
    """
    Initializes database tables and indexes safely.
    Can be run repeatedly without data loss or duplicate tables.
    """
    with get_db_cursor(db_path) as cursor:
        # 1. Notes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                content TEXT NOT NULL,
                source_type TEXT DEFAULT 'manual',
                file_name TEXT,
                tags TEXT,
                word_count INTEGER DEFAULT 0,
                reading_time_min REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_subject ON notes(subject);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at);")

        # 2. Summaries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER,
                title TEXT NOT NULL,
                original_text TEXT NOT NULL,
                summary_text TEXT NOT NULL,
                key_points TEXT,
                compression_ratio REAL DEFAULT 0.0,
                method TEXT DEFAULT 'extractive',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE SET NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_note_id ON summaries(note_id);")

        # 3. Flashcard Decks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flashcard_decks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT,
                note_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE SET NULL
            );
        """)
        cursor.execute("PRAGMA table_info(flashcard_decks);")
        deck_cols = [row[1] for row in cursor.fetchall()]
        if "note_id" not in deck_cols:
            cursor.execute("ALTER TABLE flashcard_decks ADD COLUMN note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL;")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flashcard_decks_note_id ON flashcard_decks(note_id);")

        # 4. Flashcards table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id INTEGER,
                subject TEXT,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                mastery_level INTEGER DEFAULT 0,
                review_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (deck_id) REFERENCES flashcard_decks(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flashcards_deck_id ON flashcards(deck_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flashcards_mastery ON flashcards(mastery_level);")

        # 5. Academic Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT,
                priority TEXT NOT NULL DEFAULT 'Medium' CHECK (priority IN ('High', 'Medium', 'Low')),
                deadline DATE,
                status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'In Progress', 'Completed')),
                estimated_hours REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);")

        # 6. Quizzes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                note_id INTEGER,
                total_questions INTEGER NOT NULL,
                questions_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE SET NULL
            );
        """)

        # 7. Quiz Attempts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER,
                quiz_title TEXT NOT NULL,
                subject TEXT NOT NULL,
                score INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                percentage REAL NOT NULL,
                time_taken_sec INTEGER DEFAULT 0,
                user_answers_json TEXT,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE SET NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quiz_attempts_completed ON quiz_attempts(completed_at);")

        # 8. Study Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                topic TEXT,
                duration_minutes INTEGER NOT NULL,
                session_type TEXT DEFAULT 'Reading',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_study_sessions_subject ON study_sessions(subject);")

        # 9. User Preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                pref_key TEXT PRIMARY KEY,
                pref_value TEXT NOT NULL
            );
        """)

        # Seeding check
        if seed_if_empty:
            cursor.execute("SELECT COUNT(*) FROM notes;")
            count = cursor.fetchone()[0]
            if count == 0:
                _seed_initial_data(cursor)


def _seed_initial_data(cursor: sqlite3.Cursor) -> None:
    """Populates empty databases with realistic academic starter records."""
    # Starter Note 1
    nn_content = (
        "Neural networks are computational models inspired by biological neural structures in animal brains. "
        "A biological neuron receives electrical signals from dendrites, processes them in the cell body, "
        "and transmits signals through an axon to other neurons. "
        "In artificial neural networks, the fundamental processing unit is known as an artificial neuron or perceptron. "
        "Each perceptron computes a weighted sum of its inputs, adds a bias term, and passes the output through a non-linear activation function. "
        "Common activation functions include the Sigmoid, Rectified Linear Unit (ReLU), and Hyperbolic Tangent (Tanh). "
        "Activation functions introduce non-linearity, enabling the network to learn complex patterns and continuous representations. "
        "Deep neural networks consist of an input layer, multiple hidden layers, and an output layer. "
        "Training a neural network involves forward propagation to calculate predictions and backpropagation to calculate error gradients. "
        "Gradient descent optimization algorithms, such as Adam or RMSprop, systematically update weight parameters to minimize loss."
    )
    cursor.execute("""
        INSERT INTO notes (title, subject, content, source_type, tags, word_count, reading_time_min, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "Introduction to Artificial Neural Networks",
        "Computer Science",
        nn_content,
        "manual",
        "AI, Machine Learning, Deep Learning",
        len(nn_content.split()),
        round(len(nn_content.split()) / 200, 1),
        (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    ))
    note_id_1 = cursor.lastrowid

    # Starter Note 2
    bio_content = (
        "Cellular respiration is a metabolic pathway that breaks down glucose and produces adenosine triphosphate (ATP). "
        "The complete process comprises three major stages: glycolysis, the citric acid cycle (Krebs cycle), and oxidative phosphorylation. "
        "Glycolysis occurs in the cytoplasm and breaks one glucose molecule into two molecules of pyruvate, generating a net gain of two ATP molecules. "
        "The Krebs cycle takes place in the mitochondrial matrix, producing electron carriers NADH and FADH2 alongside carbon dioxide. "
        "Oxidative phosphorylation occurs along the inner mitochondrial membrane via the electron transport chain and ATP synthase. "
        "This terminal stage generates the majority of cellular energy, yielding approximately thirty to thirty-two ATP molecules per glucose."
    )
    cursor.execute("""
        INSERT INTO notes (title, subject, content, source_type, tags, word_count, reading_time_min, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "Cellular Respiration and ATP Synthesis",
        "Biology",
        bio_content,
        "manual",
        "Bioenergetics, Mitochondria, Metabolism",
        len(bio_content.split()),
        round(len(bio_content.split()) / 200, 1),
        (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    ))

    # Starter Summary
    cursor.execute("""
        INSERT INTO summaries (note_id, title, original_text, summary_text, key_points, compression_ratio, method, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        note_id_1,
        "Summary: Artificial Neural Networks",
        nn_content,
        "Neural networks are computational models inspired by biological neural structures. "
        "Each perceptron computes a weighted sum of inputs and applies a non-linear activation function like ReLU. "
        "Training utilizes forward propagation and backpropagation with gradient descent to minimize model loss.",
        json.dumps([
            "Perceptron is the core unit applying weights, bias, and non-linear activation functions.",
            "ReLU, Sigmoid, and Tanh enable networks to model non-linear boundaries.",
            "Backpropagation combined with gradient descent optimizes weight parameters."
        ]),
        58.5,
        "Extractive TF-IDF",
        (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    ))

    # Starter Tasks
    today = date.today()
    tasks_data = [
        ("Review Neural Network Backpropagation math", "Computer Science", "Work through calculus derivations for chain rule", "High", (today + timedelta(days=1)).strftime("%Y-%m-%d"), "In Progress", 2.0),
        ("Complete Cellular Respiration diagram quiz", "Biology", "Label electron transport chain components", "Medium", (today + timedelta(days=3)).strftime("%Y-%m-%d"), "Pending", 1.5),
        ("Read Cognitive Psychology Chapter 4", "Psychology", "Focus on working memory models by Baddeley", "Low", (today + timedelta(days=5)).strftime("%Y-%m-%d"), "Pending", 1.0),
        ("Submit Operating Systems Lab 2", "Computer Science", "Multi-threaded process synchronization implementation", "High", (today - timedelta(days=1)).strftime("%Y-%m-%d"), "Completed", 3.0),
        ("Review Flashcards for Biology Exam", "Biology", "Master Krebs cycle intermediate substrates", "Medium", (today - timedelta(days=2)).strftime("%Y-%m-%d"), "Completed", 1.0),
    ]

    for title, subj, desc, prio, dl, status, hours in tasks_data:
        comp_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S") if status == "Completed" else None
        cursor.execute("""
            INSERT INTO tasks (title, subject, description, priority, deadline, status, estimated_hours, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (title, subj, desc, prio, dl, status, hours, (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S"), comp_date))

    # Starter Flashcard Deck & Cards
    cursor.execute("""
        INSERT INTO flashcard_decks (title, subject, description, created_at)
        VALUES (?, ?, ?, ?);
    """, (
        "Deep Learning Fundamentals",
        "Computer Science",
        "Key definitions and architecture principles for neural networks.",
        (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    ))
    deck_id = cursor.lastrowid

    flashcards_sample = [
        ("What is an activation function?", "A mathematical equation that introduces non-linearity into a neuron's output, enabling neural networks to learn non-linear patterns.", 2, 3),
        ("What is Backpropagation?", "An algorithm that calculates the gradient of the loss function with respect to each weight by applying the calculus chain rule backward through layers.", 3, 4),
        ("What does ReLU stand for and what is its formula?", "Rectified Linear Unit. Its formula is f(x) = max(0, x), which mitigates vanishing gradients during training.", 1, 2),
        ("What is the role of the bias parameter in a perceptron?", "It shifts the activation function curve to the left or right, allowing the neuron to fit patterns that do not pass through the origin.", 2, 2)
    ]

    for front, back, mastery, rev_cnt in flashcards_sample:
        cursor.execute("""
            INSERT INTO flashcards (deck_id, subject, front, back, mastery_level, review_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (deck_id, "Computer Science", front, back, mastery, rev_cnt, (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")))

    # Starter Quizzes & Attempts
    sample_questions = [
        {
            "id": 1,
            "question": "What is the primary function of an activation function in a neural network?",
            "options": [
                "A) To introduce non-linearity into the network output",
                "B) To calculate the learning rate automatically",
                "C) To increase the number of input dimensions",
                "D) To reset the neuron weights to zero"
            ],
            "correct_option": "A",
            "explanation": "Activation functions introduce non-linearity, which allows neural networks to approximate complex non-linear functions."
        },
        {
            "id": 2,
            "question": "Which algorithm is utilized to compute the error gradients with respect to weights?",
            "options": [
                "A) Forward Propagation",
                "B) Backpropagation",
                "C) Singular Value Decomposition",
                "D) K-Means Clustering"
            ],
            "correct_option": "B",
            "explanation": "Backpropagation computes the gradient of the loss function with respect to the network weights using the chain rule."
        },
        {
            "id": 3,
            "question": "Which of the following is the mathematical definition of the ReLU activation function?",
            "options": [
                "A) f(x) = 1 / (1 + e^-x)",
                "B) f(x) = max(0, x)",
                "C) f(x) = tanh(x)",
                "D) f(x) = x^2"
            ],
            "correct_option": "B",
            "explanation": "ReLU returns 0 for negative values and the input value x for positive values: max(0, x)."
        }
    ]

    cursor.execute("""
        INSERT INTO quizzes (title, subject, note_id, total_questions, questions_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (
        "Neural Networks Architecture Check",
        "Computer Science",
        note_id_1,
        len(sample_questions),
        json.dumps(sample_questions),
        (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    ))
    quiz_id = cursor.lastrowid

    # Starter Quiz Attempts
    cursor.execute("""
        INSERT INTO quiz_attempts (quiz_id, quiz_title, subject, score, total_questions, percentage, time_taken_sec, user_answers_json, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        quiz_id,
        "Neural Networks Architecture Check",
        "Computer Science",
        3,
        3,
        100.0,
        74,
        json.dumps({"1": "A", "2": "B", "3": "B"}),
        (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    ))

    cursor.execute("""
        INSERT INTO quiz_attempts (quiz_id, quiz_title, subject, score, total_questions, percentage, time_taken_sec, user_answers_json, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        quiz_id,
        "Cellular Biology Quick Check",
        "Biology",
        4,
        5,
        80.0,
        110,
        json.dumps({"1": "A", "2": "C", "3": "A", "4": "B", "5": "D"}),
        (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    ))

    # Starter Study Sessions
    sessions = [
        ("Computer Science", "Deep Learning Backpropagation", 45, "Reading", (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")),
        ("Biology", "Cellular Respiration Stages", 30, "Reading", (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")),
        ("Computer Science", "Quiz Practice: Neural Networks", 20, "Quiz", (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")),
        ("Biology", "Flashcards Mastery", 25, "Flashcards", (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")),
        ("Psychology", "Working Memory Chapter", 40, "Reading", (datetime.now() - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")),
    ]
    for subj, topic, dur, stype, ts in sessions:
        cursor.execute("""
            INSERT INTO study_sessions (subject, topic, duration_minutes, session_type, created_at)
            VALUES (?, ?, ?, ?, ?);
        """, (subj, topic, dur, stype, ts))

    cursor.execute("""
        INSERT OR REPLACE INTO user_preferences (pref_key, pref_value)
        VALUES ('theme', 'dark');
    """)


# =========================================================================
# CRUD Operations: Notes
# =========================================================================

def create_note(title: str, subject: str, content: str, source_type: str = 'manual',
                file_name: Optional[str] = None, tags: str = '', db_path: Optional[str] = None) -> int:
    """
    Creates a new study note with parameterized query.
    Validates input parameters before insertion.
    """
    if not title or not title.strip():
        raise ValidationError("Note title cannot be empty.")
    if not content or not content.strip():
        raise ValidationError("Note content cannot be empty.")
    if not subject or not subject.strip():
        subject = "General Study"

    clean_t = title.strip()
    clean_s = subject.strip()
    clean_c = content.strip()
    word_count = len(clean_c.split())
    reading_time = round(word_count / 200, 1)

    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            INSERT INTO notes (title, subject, content, source_type, file_name, tags, word_count, reading_time_min, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
        """, (clean_t, clean_s, clean_c, source_type, file_name, tags.strip(), word_count, reading_time))
        return cursor.lastrowid


def get_all_notes(search_query: str = '', subject_filter: str = '',
                  sort_by: str = 'recent_updated', db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves notes with optional keyword search, subject filtering, and customizable sorting."""
    with get_db_cursor(db_path) as cursor:
        query = "SELECT * FROM notes WHERE 1=1"
        params: List[Any] = []

        if search_query and search_query.strip():
            query += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ? OR subject LIKE ? OR file_name LIKE ?)"
            pattern = f"%{search_query.strip()}%"
            params.extend([pattern, pattern, pattern, pattern, pattern])

        if subject_filter and subject_filter != "All":
            query += " AND subject = ?"
            params.append(subject_filter.strip())

        if sort_by == 'recent_created':
            query += " ORDER BY created_at DESC, id DESC;"
        elif sort_by == 'title_asc':
            query += " ORDER BY title ASC, id ASC;"
        elif sort_by == 'title_desc':
            query += " ORDER BY title DESC, id DESC;"
        else:  # default 'recent_updated'
            query += " ORDER BY updated_at DESC, id DESC;"

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_note_by_id(note_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single note by ID."""
    if not isinstance(note_id, int) or note_id <= 0:
        return None
    with get_db_cursor(db_path) as cursor:
        cursor.execute("SELECT * FROM notes WHERE id = ?;", (note_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def search_notes(query: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Convenience search function across notes title, content, and tags."""
    return get_all_notes(search_query=query, db_path=db_path)


def update_note(note_id: int, title: str, subject: str, content: str,
                tags: str = '', db_path: Optional[str] = None) -> bool:
    """Updates an existing note after validation."""
    if not isinstance(note_id, int) or note_id <= 0:
        raise ValidationError("Invalid note ID.")
    if not title or not title.strip():
        raise ValidationError("Note title cannot be empty.")
    if not content or not content.strip():
        raise ValidationError("Note content cannot be empty.")

    clean_t = title.strip()
    clean_s = subject.strip() if subject and subject.strip() else "General Study"
    clean_c = content.strip()
    word_count = len(clean_c.split())
    reading_time = round(word_count / 200, 1)

    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            UPDATE notes
            SET title = ?, subject = ?, content = ?, tags = ?, word_count = ?, reading_time_min = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """, (clean_t, clean_s, clean_c, tags.strip(), word_count, reading_time, note_id))
        return cursor.rowcount > 0


def delete_note(note_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a note by ID."""
    if not isinstance(note_id, int) or note_id <= 0:
        return False
    with get_db_cursor(db_path) as cursor:
        cursor.execute("DELETE FROM notes WHERE id = ?;", (note_id,))
        return cursor.rowcount > 0


# ==========================================
# CRUD Operations: Summaries
# ==========================================

def save_summary(title: str, original_text: str, summary_text: str,
                 key_points: Optional[List[str]] = None, compression_ratio: float = 0.0,
                 method: str = 'Extractive NLP', note_id: Optional[int] = None,
                 db_path: Optional[str] = None) -> int:
    """Validates and saves a generated summary."""
    if not title or not title.strip():
        raise ValidationError("Summary title cannot be empty.")
    if not summary_text or not summary_text.strip():
        raise ValidationError("Summary text cannot be empty.")

    points_json = json.dumps(key_points if key_points is not None else [])
    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            INSERT INTO summaries (note_id, title, original_text, summary_text, key_points, compression_ratio, method)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (note_id, title.strip(), original_text, summary_text.strip(), points_json, compression_ratio, method))
        return cursor.lastrowid


def get_all_summaries(search_query: str = '', subject_filter: str = '',
                      sort_by: str = 'recent_created', db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all saved summaries with parsed key_points and linked note metadata."""
    with get_db_cursor(db_path) as cursor:
        query = """
            SELECT s.*, 
                   n.title AS source_note_title, 
                   COALESCE(n.subject, 'General Study') AS subject
            FROM summaries s
            LEFT JOIN notes n ON s.note_id = n.id
            WHERE 1=1
        """
        params: List[Any] = []
        if search_query and search_query.strip():
            query += " AND (s.title LIKE ? OR s.summary_text LIKE ? OR s.original_text LIKE ?)"
            p = f"%{search_query.strip()}%"
            params.extend([p, p, p])

        if subject_filter and subject_filter != "All":
            query += " AND (n.subject = ? OR (n.subject IS NULL AND ? = 'General Study'))"
            params.extend([subject_filter.strip(), subject_filter.strip()])

        if sort_by == 'title_asc':
            query += " ORDER BY s.title ASC, s.id ASC;"
        elif sort_by == 'title_desc':
            query += " ORDER BY s.title DESC, s.id DESC;"
        elif sort_by == 'recent_updated':
            query += " ORDER BY s.created_at DESC, s.id DESC;"
        else:  # default 'recent_created'
            query += " ORDER BY s.created_at DESC, s.id DESC;"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d['key_points'] = json.loads(d.get('key_points') or '[]')
            except Exception:
                d['key_points'] = []
            result.append(d)
        return result


def get_summary_by_id(summary_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single summary by ID with joined source note information."""
    if not isinstance(summary_id, int) or summary_id <= 0:
        return None
    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            SELECT s.*, n.title AS source_note_title, COALESCE(n.subject, 'General Study') AS subject
            FROM summaries s
            LEFT JOIN notes n ON s.note_id = n.id
            WHERE s.id = ?;
        """, (summary_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d['key_points'] = json.loads(d.get('key_points') or '[]')
        except Exception:
            d['key_points'] = []
        return d


def delete_summary(summary_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a summary by ID."""
    if not isinstance(summary_id, int) or summary_id <= 0:
        return False
    with get_db_cursor(db_path) as cursor:
        cursor.execute("DELETE FROM summaries WHERE id = ?;", (summary_id,))
        return cursor.rowcount > 0


# ==========================================
# CRUD Operations: Flashcards & Decks
# ==========================================

def create_flashcard_deck(title: str, subject: str, description: str = '',
                          note_id: Optional[int] = None, db_path: Optional[str] = None) -> int:
    """Creates a new flashcard deck with optional reference to a source note."""
    if not title or not title.strip():
        raise ValidationError("Deck title cannot be empty.")
    clean_s = subject.strip() if subject and subject.strip() else "General Study"
    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            INSERT INTO flashcard_decks (title, subject, description, note_id)
            VALUES (?, ?, ?, ?);
        """, (title.strip(), clean_s, description.strip(), note_id))
        return cursor.lastrowid


def get_all_decks(search_query: str = '', subject_filter: str = '',
                  sort_by: str = 'recent_created', db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all flashcard decks with card counts, mastery stats, and linked note metadata."""
    with get_db_cursor(db_path) as cursor:
        query = """
            SELECT d.*, 
                   n.title AS source_note_title,
                   COUNT(DISTINCT f.id) as card_count,
                   COALESCE(SUM(CASE WHEN f.mastery_level >= 3 THEN 1 ELSE 0 END), 0) as mastered_count
            FROM flashcard_decks d
            LEFT JOIN notes n ON d.note_id = n.id
            LEFT JOIN flashcards f ON d.id = f.deck_id
            WHERE 1=1
        """
        params: List[Any] = []
        if search_query and search_query.strip():
            query += " AND (d.title LIKE ? OR d.description LIKE ? OR d.subject LIKE ? OR f.front LIKE ? OR f.back LIKE ?)"
            p = f"%{search_query.strip()}%"
            params.extend([p, p, p, p, p])

        if subject_filter and subject_filter != "All":
            query += " AND d.subject = ?"
            params.append(subject_filter.strip())

        query += " GROUP BY d.id"

        if sort_by == 'title_asc':
            query += " ORDER BY d.title ASC, d.id ASC;"
        elif sort_by == 'title_desc':
            query += " ORDER BY d.title DESC, d.id DESC;"
        elif sort_by == 'recent_updated':
            query += " ORDER BY d.created_at DESC, d.id DESC;"
        else:  # default 'recent_created'
            query += " ORDER BY d.created_at DESC, d.id DESC;"

        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_deck_by_id(deck_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single flashcard deck by ID with source note information."""
    if not isinstance(deck_id, int) or deck_id <= 0:
        return None
    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            SELECT d.*, n.title AS source_note_title
            FROM flashcard_decks d
            LEFT JOIN notes n ON d.note_id = n.id
            WHERE d.id = ?;
        """, (deck_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_flashcard(front: str, back: str, deck_id: Optional[int] = None,
                     subject: Optional[str] = None, mastery_level: int = 0,
                     db_path: Optional[str] = None) -> int:
    """Creates a single flashcard (optionally linked to a deck)."""
    if not front or not front.strip():
        raise ValidationError("Flashcard front cannot be empty.")
    if not back or not back.strip():
        raise ValidationError("Flashcard back cannot be empty.")

    clamped_m = max(0, min(3, int(mastery_level)))
    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            INSERT INTO flashcards (deck_id, subject, front, back, mastery_level, review_count)
            VALUES (?, ?, ?, ?, ?, 0);
        """, (deck_id, subject, front.strip(), back.strip(), clamped_m))
        return cursor.lastrowid


def get_all_flashcards(deck_id: Optional[int] = None, search_query: str = '', db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves flashcards with optional deck filter and search query."""
    with get_db_cursor(db_path) as cursor:
        query = "SELECT * FROM flashcards WHERE 1=1"
        params: List[Any] = []
        if deck_id is not None:
            query += " AND deck_id = ?"
            params.append(deck_id)
        if search_query and search_query.strip():
            query += " AND (front LIKE ? OR back LIKE ?)"
            p = f"%{search_query.strip()}%"
            params.extend([p, p])
        query += " ORDER BY id ASC;"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_flashcards_by_deck(deck_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all flashcards in a specific deck."""
    return get_all_flashcards(deck_id=deck_id, db_path=db_path)


def get_flashcard_by_id(card_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single flashcard by ID."""
    if not isinstance(card_id, int) or card_id <= 0:
        return None
    with get_db_cursor(db_path) as cursor:
        cursor.execute("SELECT * FROM flashcards WHERE id = ?;", (card_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def save_flashcards_batch(deck_id: int, cards: List[Dict[str, str]], db_path: Optional[str] = None) -> int:
    """Saves multiple flashcards to a deck atomically."""
    if not cards:
        return 0
    with get_db_cursor(db_path) as cursor:
        inserted = 0
        for card in cards:
            front = card.get('front', '').strip()
            back = card.get('back', '').strip()
            if front and back:
                cursor.execute("""
                    INSERT INTO flashcards (deck_id, front, back)
                    VALUES (?, ?, ?);
                """, (deck_id, front, back))
                inserted += 1
        return inserted


def update_flashcard(card_id: int, front: str, back: str,
                     mastery_level: Optional[int] = None, db_path: Optional[str] = None) -> bool:
    """Updates the content and optional mastery of a flashcard."""
    if not isinstance(card_id, int) or card_id <= 0:
        raise ValidationError("Invalid card ID.")
    if not front or not front.strip():
        raise ValidationError("Front of flashcard cannot be empty.")
    if not back or not back.strip():
        raise ValidationError("Back of flashcard cannot be empty.")

    with get_db_cursor(db_path) as cursor:
        if mastery_level is not None:
            clamped_m = max(0, min(3, int(mastery_level)))
            cursor.execute("""
                UPDATE flashcards
                SET front = ?, back = ?, mastery_level = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (front.strip(), back.strip(), clamped_m, card_id))
        else:
            cursor.execute("""
                UPDATE flashcards
                SET front = ?, back = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (front.strip(), back.strip(), card_id))
        return cursor.rowcount > 0


def update_flashcard_mastery(card_id: int, mastery_level: int, db_path: Optional[str] = None) -> bool:
    """Updates mastery level (0-3) and increments review count."""
    if not isinstance(card_id, int) or card_id <= 0:
        return False
    clamped_m = max(0, min(3, int(mastery_level)))
    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            UPDATE flashcards
            SET mastery_level = ?, review_count = review_count + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """, (clamped_m, card_id))
        return cursor.rowcount > 0


def delete_deck(deck_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a deck and cascades deletion of its flashcards."""
    if not isinstance(deck_id, int) or deck_id <= 0:
        return False
    with get_db_cursor(db_path) as cursor:
        cursor.execute("DELETE FROM flashcard_decks WHERE id = ?;", (deck_id,))
        return cursor.rowcount > 0


def delete_flashcard(card_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a single flashcard."""
    if not isinstance(card_id, int) or card_id <= 0:
        return False
    with get_db_cursor(db_path) as cursor:
        cursor.execute("DELETE FROM flashcards WHERE id = ?;", (card_id,))
        return cursor.rowcount > 0


# ==========================================
# CRUD Operations: Tasks
# ==========================================

VALID_PRIORITIES = {'High', 'Medium', 'Low'}
VALID_STATUSES = {'Pending', 'In Progress', 'Completed'}


def create_task(title: str, subject: str, description: str = '',
                priority: str = 'Medium', deadline: Optional[str] = None,
                estimated_hours: float = 1.0, status: str = 'Pending',
                db_path: Optional[str] = None) -> int:
    """Creates a new academic task after validating inputs."""
    if not title or not title.strip():
        raise ValidationError("Task title cannot be empty.")
    if priority not in VALID_PRIORITIES:
        raise ValidationError(f"Invalid priority '{priority}'. Must be one of: {VALID_PRIORITIES}")
    if status not in VALID_STATUSES:
        raise ValidationError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")
    if estimated_hours <= 0:
        raise ValidationError("Estimated hours must be greater than zero.")

    clean_s = subject.strip() if subject and subject.strip() else "General Study"
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == 'Completed' else None

    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            INSERT INTO tasks (title, subject, description, priority, deadline, status, estimated_hours, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (title.strip(), clean_s, description.strip(), priority, deadline, status, float(estimated_hours), completed_at))
        return cursor.lastrowid


def get_upcoming_tasks(days: int = 7, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves non-completed tasks with deadlines within the upcoming N days (including today)."""
    with get_db_cursor(db_path) as cursor:
        cursor.execute(f"""
            SELECT * FROM tasks
            WHERE status != 'Completed'
              AND deadline IS NOT NULL
              AND deadline != ''
              AND deadline >= date('now', 'localtime')
              AND deadline <= date('now', 'localtime', '+{int(days)} days')
            ORDER BY deadline ASC, CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END;
        """)
        return [dict(r) for r in cursor.fetchall()]


def get_all_tasks(status_filter: str = 'All', priority_filter: str = 'All',
                  subject_filter: str = 'All', sort_by: str = 'deadline_asc',
                  search_query: str = '', db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves tasks with status, priority, subject, overdue, and search filtering with customizable sorting."""
    with get_db_cursor(db_path) as cursor:
        query = "SELECT * FROM tasks WHERE 1=1"
        params: List[Any] = []

        if status_filter == 'Overdue':
            query += " AND status != 'Completed' AND deadline IS NOT NULL AND deadline != '' AND deadline < date('now', 'localtime')"
        elif status_filter != 'All':
            query += " AND status = ?"
            params.append(status_filter)

        if priority_filter != 'All':
            query += " AND priority = ?"
            params.append(priority_filter)

        if subject_filter != 'All':
            query += " AND subject = ?"
            params.append(subject_filter)

        if search_query and search_query.strip():
            query += " AND (title LIKE ? OR description LIKE ? OR subject LIKE ?)"
            p = f"%{search_query.strip()}%"
            params.extend([p, p, p])

        if sort_by == 'deadline_asc':
            query += " ORDER BY (deadline IS NULL OR deadline = ''), deadline ASC, id ASC;"
        elif sort_by == 'deadline_desc':
            query += " ORDER BY (deadline IS NULL OR deadline = ''), deadline DESC, id DESC;"
        elif sort_by == 'priority_high_first':
            query += " ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END, (deadline IS NULL OR deadline = ''), deadline ASC;"
        elif sort_by == 'priority_low_first':
            query += " ORDER BY CASE priority WHEN 'Low' THEN 1 WHEN 'Medium' THEN 2 WHEN 'High' THEN 3 ELSE 4 END, (deadline IS NULL OR deadline = ''), deadline ASC;"
        elif sort_by == 'title_asc':
            query += " ORDER BY title ASC, id ASC;"
        elif sort_by == 'recently_created':
            query += " ORDER BY created_at DESC, id DESC;"
        else:
            query += " ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END, (deadline IS NULL OR deadline = ''), deadline ASC;"

        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_task_by_id(task_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single task by ID."""
    if not isinstance(task_id, int) or task_id <= 0:
        return None
    with get_db_cursor(db_path) as cursor:
        cursor.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_task_status(task_id: int, new_status: str, db_path: Optional[str] = None) -> bool:
    """Updates a task's status and automatically timestamps completion."""
    if new_status not in VALID_STATUSES:
        raise ValidationError(f"Invalid status '{new_status}'. Must be one of: {VALID_STATUSES}")
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == 'Completed' else None

    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            UPDATE tasks
            SET status = ?, completed_at = ?
            WHERE id = ?;
        """, (new_status, completed_at, task_id))
        return cursor.rowcount > 0


def complete_task(task_id: int, db_path: Optional[str] = None) -> bool:
    """Convenience function to mark a task as completed."""
    return update_task_status(task_id, 'Completed', db_path=db_path)


def update_task(task_id: int, title: str, subject: str, description: str,
                priority: str, deadline: Optional[str], status: str,
                estimated_hours: float, db_path: Optional[str] = None) -> bool:
    """Updates all details of an academic task."""
    if not title or not title.strip():
        raise ValidationError("Task title cannot be empty.")
    if priority not in VALID_PRIORITIES:
        raise ValidationError(f"Invalid priority '{priority}'.")
    if status not in VALID_STATUSES:
        raise ValidationError(f"Invalid status '{status}'.")
    if estimated_hours <= 0:
        raise ValidationError("Estimated hours must be greater than zero.")

    clean_s = subject.strip() if subject and subject.strip() else "General Study"
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == 'Completed' else None

    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            UPDATE tasks
            SET title = ?, subject = ?, description = ?, priority = ?, deadline = ?, status = ?, estimated_hours = ?, completed_at = ?
            WHERE id = ?;
        """, (title.strip(), clean_s, description.strip(), priority, deadline, status, float(estimated_hours), completed_at, task_id))
        return cursor.rowcount > 0


def delete_task(task_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a task by ID."""
    if not isinstance(task_id, int) or task_id <= 0:
        return False
    with get_db_cursor(db_path) as cursor:
        cursor.execute("DELETE FROM tasks WHERE id = ?;", (task_id,))
        return cursor.rowcount > 0


def get_task_stats(start_date: Optional[str] = None, end_date: Optional[str] = None,
                   db_path: Optional[str] = None) -> Dict[str, Any]:
    """Calculates statistics on task completion, velocity, and deadline tracking with optional date filtering."""
    with get_db_cursor(db_path) as cursor:
        where_clause = " WHERE 1=1"
        params: List[Any] = []
        if start_date:
            where_clause += " AND created_at >= ?"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            where_clause += " AND created_at <= ?"
            params.append(f"{end_date} 23:59:59")

        cursor.execute(f"SELECT status, COUNT(*) as cnt FROM tasks{where_clause} GROUP BY status;", params)
        counts = {row['status']: row['cnt'] for row in cursor.fetchall()}
        total = sum(counts.values())
        completed = counts.get('Completed', 0)
        pending = counts.get('Pending', 0)
        in_progress = counts.get('In Progress', 0)
        rate = round((completed / total * 100), 1) if total > 0 else 0.0

        cursor.execute(f"""
            SELECT COUNT(*) FROM tasks 
            {where_clause}
              AND status != 'Completed' 
              AND deadline IS NOT NULL 
              AND deadline != '' 
              AND deadline < date('now', 'localtime');
        """, params)
        overdue_cnt = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT COUNT(*) FROM tasks 
            {where_clause}
              AND status != 'Completed' 
              AND deadline IS NOT NULL 
              AND deadline != '' 
              AND deadline >= date('now', 'localtime')
              AND deadline <= date('now', 'localtime', '+7 days');
        """, params)
        due_soon_cnt = cursor.fetchone()[0]

        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "in_progress": in_progress,
            "overdue": overdue_cnt,
            "due_soon": due_soon_cnt,
            "completion_rate": rate
        }


def get_notes_stats(start_date: Optional[str] = None, end_date: Optional[str] = None,
                    db_path: Optional[str] = None) -> Dict[str, Any]:
    """Calculates summary statistics on notes created with optional date range filter."""
    with get_db_cursor(db_path) as cursor:
        where_clause = " WHERE 1=1"
        params: List[Any] = []
        if start_date:
            where_clause += " AND created_at >= ?"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            where_clause += " AND created_at <= ?"
            params.append(f"{end_date} 23:59:59")

        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_notes,
                COALESCE(SUM(word_count), 0) as total_words,
                COALESCE(AVG(word_count), 0.0) as avg_words
            FROM notes{where_clause};
        """, params)
        row = cursor.fetchone()
        return {
            "total_notes": row["total_notes"],
            "total_words": row["total_words"],
            "avg_words": round(row["avg_words"], 1)
        }


# ==========================================
# CRUD Operations: Quizzes & Attempts
# ==========================================

def save_quiz(title: str, subject: str, questions: List[Dict[str, Any]],
              note_id: Optional[int] = None, db_path: Optional[str] = None) -> int:
    """Saves a quiz with formulated questions into the database."""
    if not title or not title.strip():
        raise ValidationError("Quiz title cannot be empty.")
    if not questions:
        raise ValidationError("Quiz must contain at least one question.")

    clean_s = subject.strip() if subject and subject.strip() else "General Study"
    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            INSERT INTO quizzes (title, subject, note_id, total_questions, questions_json)
            VALUES (?, ?, ?, ?, ?);
        """, (title.strip(), clean_s, note_id, len(questions), json.dumps(questions)))
        return cursor.lastrowid


def get_all_quizzes(search_query: str = '', subject_filter: str = '',
                    sort_by: str = 'recent_created', db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all generated quizzes with parsed questions and linked note metadata."""
    with get_db_cursor(db_path) as cursor:
        query = """
            SELECT q.*, n.title AS source_note_title
            FROM quizzes q
            LEFT JOIN notes n ON q.note_id = n.id
            WHERE 1=1
        """
        params: List[Any] = []
        if search_query and search_query.strip():
            query += " AND (q.title LIKE ? OR q.questions_json LIKE ?)"
            p = f"%{search_query.strip()}%"
            params.extend([p, p])

        if subject_filter and subject_filter != "All":
            query += " AND q.subject = ?"
            params.append(subject_filter.strip())

        if sort_by == 'title_asc':
            query += " ORDER BY q.title ASC, q.id ASC;"
        elif sort_by == 'title_desc':
            query += " ORDER BY q.title DESC, q.id DESC;"
        elif sort_by == 'recent_updated':
            query += " ORDER BY q.created_at DESC, q.id DESC;"
        else:  # default 'recent_created'
            query += " ORDER BY q.created_at DESC, q.id DESC;"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d['questions'] = json.loads(d['questions_json'])
            except Exception:
                d['questions'] = []
            result.append(d)
        return result


def get_quiz_by_id(quiz_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single quiz by ID with source note information."""
    if not isinstance(quiz_id, int) or quiz_id <= 0:
        return None
    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            SELECT q.*, n.title AS source_note_title
            FROM quizzes q
            LEFT JOIN notes n ON q.note_id = n.id
            WHERE q.id = ?;
        """, (quiz_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d['questions'] = json.loads(d['questions_json'])
        except Exception:
            d['questions'] = []
        return d


def delete_quiz(quiz_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a quiz by ID."""
    if not isinstance(quiz_id, int) or quiz_id <= 0:
        return False
    with get_db_cursor(db_path) as cursor:
        cursor.execute("DELETE FROM quizzes WHERE id = ?;", (quiz_id,))
        return cursor.rowcount > 0


def save_quiz_attempt(quiz_id: int, quiz_title: str, subject: str,
                      score: int, total_questions: int, time_taken_sec: int = 0,
                      user_answers: Optional[Dict[str, str]] = None,
                      db_path: Optional[str] = None) -> int:
    """Records a completed quiz attempt with score validation."""
    if total_questions <= 0:
        raise ValidationError("Total questions must be greater than zero.")
    if score < 0 or score > total_questions:
        raise ValidationError(f"Score ({score}) cannot be negative or exceed total questions ({total_questions}).")

    percentage = round((score / total_questions * 100), 1)
    clean_s = subject.strip() if subject and subject.strip() else "General Study"
    clean_t = quiz_title.strip() if quiz_title and quiz_title.strip() else "Practice Quiz"

    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            INSERT INTO quiz_attempts (quiz_id, quiz_title, subject, score, total_questions, percentage, time_taken_sec, user_answers_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (quiz_id if quiz_id and quiz_id > 0 else None, clean_t, clean_s, score, total_questions, percentage, max(0, time_taken_sec), json.dumps(user_answers or {})))
        return cursor.lastrowid


def get_all_quiz_attempts(start_date: Optional[str] = None, end_date: Optional[str] = None,
                          db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves recorded quiz attempts with optional date range filter."""
    with get_db_cursor(db_path) as cursor:
        query = "SELECT * FROM quiz_attempts WHERE 1=1"
        params: List[Any] = []
        if start_date:
            query += " AND completed_at >= ?"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            query += " AND completed_at <= ?"
            params.append(f"{end_date} 23:59:59")
        query += " ORDER BY completed_at DESC;"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_quiz_attempt_by_id(attempt_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single quiz attempt by ID."""
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        return None
    with get_db_cursor(db_path) as cursor:
        cursor.execute("SELECT * FROM quiz_attempts WHERE id = ?;", (attempt_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_quiz_attempt(attempt_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a quiz attempt record."""
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        return False
    with get_db_cursor(db_path) as cursor:
        cursor.execute("DELETE FROM quiz_attempts WHERE id = ?;", (attempt_id,))
        return cursor.rowcount > 0


def get_quiz_stats(start_date: Optional[str] = None, end_date: Optional[str] = None,
                   db_path: Optional[str] = None) -> Dict[str, Any]:
    """Computes summary statistics for quiz attempts with optional date filtering."""
    with get_db_cursor(db_path) as cursor:
        query = """
            SELECT 
                COUNT(*) as attempts_count,
                COALESCE(AVG(percentage), 0.0) as avg_score,
                COALESCE(MAX(percentage), 0.0) as highest_score,
                COALESCE(MIN(percentage), 0.0) as lowest_score,
                COALESCE(SUM(total_questions), 0) as total_questions_answered
            FROM quiz_attempts
            WHERE 1=1
        """
        params: List[Any] = []
        if start_date:
            query += " AND completed_at >= ?"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            query += " AND completed_at <= ?"
            params.append(f"{end_date} 23:59:59")

        cursor.execute(query, params)
        row = cursor.fetchone()
        return {
            "attempts_count": row["attempts_count"],
            "avg_score": round(row["avg_score"], 1),
            "highest_score": round(row["highest_score"], 1),
            "lowest_score": round(row["lowest_score"], 1),
            "total_questions_answered": row["total_questions_answered"]
        }


def get_subject_quiz_performance(start_date: Optional[str] = None, end_date: Optional[str] = None,
                                 db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Calculates average and best quiz score grouped by subject with optional date filtering."""
    with get_db_cursor(db_path) as cursor:
        query = """
            SELECT 
                subject,
                COUNT(*) as attempts_count,
                ROUND(AVG(percentage), 1) as avg_score,
                ROUND(MAX(percentage), 1) as best_score,
                ROUND(MIN(percentage), 1) as lowest_score,
                SUM(score) as total_correct,
                SUM(total_questions) as total_questions
            FROM quiz_attempts
            WHERE 1=1
        """
        params: List[Any] = []
        if start_date:
            query += " AND completed_at >= ?"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            query += " AND completed_at <= ?"
            params.append(f"{end_date} 23:59:59")

        query += " GROUP BY subject ORDER BY avg_score DESC;"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


# ==========================================
# CRUD Operations: Study Sessions
# ==========================================

def log_study_session(subject: str, duration_minutes: int, topic: str = '',
                      session_type: str = 'Reading', notes: str = '',
                      db_path: Optional[str] = None) -> int:
    """Logs a completed study session with duration validation."""
    if duration_minutes <= 0:
        raise ValidationError("Study session duration must be greater than zero minutes.")
    clean_s = subject.strip() if subject and subject.strip() else "General Study"

    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            INSERT INTO study_sessions (subject, topic, duration_minutes, session_type, notes)
            VALUES (?, ?, ?, ?, ?);
        """, (clean_s, topic.strip(), int(duration_minutes), session_type.strip(), notes.strip()))
        return cursor.lastrowid


def get_study_sessions(subject_filter: str = 'All', start_date: Optional[str] = None,
                       end_date: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves logged study sessions with optional subject and date filters."""
    with get_db_cursor(db_path) as cursor:
        query = "SELECT * FROM study_sessions WHERE 1=1"
        params: List[Any] = []
        if subject_filter != 'All':
            query += " AND subject = ?"
            params.append(subject_filter)
        if start_date:
            query += " AND created_at >= ?"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            query += " AND created_at <= ?"
            params.append(f"{end_date} 23:59:59")
        query += " ORDER BY created_at DESC;"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_study_session_by_id(session_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single study session by ID."""
    if not isinstance(session_id, int) or session_id <= 0:
        return None
    with get_db_cursor(db_path) as cursor:
        cursor.execute("SELECT * FROM study_sessions WHERE id = ?;", (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_study_session(session_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a study session log."""
    if not isinstance(session_id, int) or session_id <= 0:
        return False
    with get_db_cursor(db_path) as cursor:
        cursor.execute("DELETE FROM study_sessions WHERE id = ?;", (session_id,))
        return cursor.rowcount > 0


def get_study_session_stats(start_date: Optional[str] = None, end_date: Optional[str] = None,
                            db_path: Optional[str] = None) -> Dict[str, Any]:
    """Calculates study session totals and averages with optional date filtering."""
    with get_db_cursor(db_path) as cursor:
        query = """
            SELECT 
                COUNT(*) as total_sessions,
                COALESCE(SUM(duration_minutes), 0) as total_minutes,
                COALESCE(AVG(duration_minutes), 0.0) as avg_duration
            FROM study_sessions
            WHERE 1=1
        """
        params: List[Any] = []
        if start_date:
            query += " AND created_at >= ?"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            query += " AND created_at <= ?"
            params.append(f"{end_date} 23:59:59")

        cursor.execute(query, params)
        row = cursor.fetchone()
        mins = row["total_minutes"]
        return {
            "total_sessions": row["total_sessions"],
            "total_minutes": mins,
            "total_hours": round(mins / 60, 1),
            "avg_duration_minutes": round(row["avg_duration"], 1)
        }


# ==========================================
# User Preferences (Theme, etc.)
# ==========================================

def get_preference(key: str, default_value: str = 'dark', db_path: Optional[str] = None) -> str:
    """Fetches user preference from database."""
    with get_db_cursor(db_path) as cursor:
        cursor.execute("SELECT pref_value FROM user_preferences WHERE pref_key = ?;", (key,))
        row = cursor.fetchone()
        return row['pref_value'] if row else default_value


def set_preference(key: str, value: str, db_path: Optional[str] = None) -> None:
    """Persists user preference to database."""
    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            INSERT INTO user_preferences (pref_key, pref_value)
            VALUES (?, ?)
            ON CONFLICT(pref_key) DO UPDATE SET pref_value = excluded.pref_value;
        """, (key, value))


# ==========================================
# Dashboard Aggregation
# ==========================================

def get_dashboard_metrics(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculates all key metrics needed for the main overview dashboard.
    Fully resilient on empty databases, returning zeroed metrics without division errors.
    """
    with get_db_cursor(db_path) as cursor:
        # Notes count
        cursor.execute("SELECT COUNT(*) FROM notes;")
        total_notes = cursor.fetchone()[0]

        # Summaries count
        cursor.execute("SELECT COUNT(*) FROM summaries;")
        total_summaries = cursor.fetchone()[0]

        # Task counts
        cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status;")
        task_dict = dict(cursor.fetchall())
        completed_tasks = task_dict.get('Completed', 0)
        pending_tasks = task_dict.get('Pending', 0)
        in_progress_tasks = task_dict.get('In Progress', 0)
        total_tasks = sum(task_dict.values())
        task_completion_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0

        # Quiz attempts and avg score
        cursor.execute("SELECT COUNT(*), COALESCE(AVG(percentage), 0.0) FROM quiz_attempts;")
        q_row = cursor.fetchone()
        quizzes_attempted = q_row[0]
        avg_quiz_score = round(q_row[1], 1)

        # Flashcards total & mastered
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(CASE WHEN mastery_level >= 3 THEN 1 ELSE 0 END), 0) FROM flashcards;")
        f_row = cursor.fetchone()
        total_flashcards = f_row[0]
        mastered_flashcards = f_row[1]

        # Total study hours logged
        cursor.execute("SELECT COALESCE(SUM(duration_minutes), 0) FROM study_sessions;")
        total_study_minutes = cursor.fetchone()[0]
        total_study_hours = round(total_study_minutes / 60, 1)

        # Distinct subjects across all materials
        cursor.execute("""
            SELECT DISTINCT subject FROM (
                SELECT subject FROM notes
                UNION
                SELECT subject FROM tasks
                UNION
                SELECT subject FROM quiz_attempts
                UNION
                SELECT subject FROM study_sessions
            ) WHERE subject IS NOT NULL AND subject != '';
        """)
        subjects = [row[0] for row in cursor.fetchall()]

        return {
            "total_notes": total_notes,
            "total_summaries": total_summaries,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "in_progress_tasks": in_progress_tasks,
            "total_tasks": total_tasks,
            "task_completion_rate": task_completion_rate,
            "quizzes_attempted": quizzes_attempted,
            "avg_quiz_score": avg_quiz_score,
            "total_flashcards": total_flashcards,
            "mastered_flashcards": mastered_flashcards,
            "total_study_hours": total_study_hours,
            "subjects": subjects
        }


# ==========================================
# Central Study Library Aggregation
# ==========================================

def get_distinct_subjects(db_path: Optional[str] = None) -> List[str]:
    """Retrieves all distinct subject areas across all study entities in the database."""
    with get_db_cursor(db_path) as cursor:
        cursor.execute("""
            SELECT DISTINCT subject FROM (
                SELECT subject FROM notes WHERE subject IS NOT NULL AND TRIM(subject) != ''
                UNION
                SELECT subject FROM flashcard_decks WHERE subject IS NOT NULL AND TRIM(subject) != ''
                UNION
                SELECT subject FROM quizzes WHERE subject IS NOT NULL AND TRIM(subject) != ''
                UNION
                SELECT subject FROM tasks WHERE subject IS NOT NULL AND TRIM(subject) != ''
                UNION
                SELECT subject FROM study_sessions WHERE subject IS NOT NULL AND TRIM(subject) != ''
            ) ORDER BY subject ASC;
        """)
        return [row[0] for row in cursor.fetchall() if row[0]]


def get_unified_library_items(search_query: str = '', material_type: str = 'All',
                              subject_filter: str = 'All', sort_by: str = 'recent_updated',
                              db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves and aggregates all study materials across notes, summaries, flashcard decks,
    and quizzes into a unified, normalized list for the Central Study Library.
    """
    items: List[Dict[str, Any]] = []

    # 1. Notes
    if material_type in ("All", "All Materials", "Saved Notes", "Notes", "notes", "note"):
        notes = get_all_notes(search_query=search_query, subject_filter=subject_filter, sort_by=sort_by, db_path=db_path)
        for n in notes:
            items.append({
                "id": n["id"],
                "material_type": "note",
                "type_label": "Saved Note",
                "icon": "📝",
                "title": n["title"],
                "subject": n["subject"],
                "preview": (n["content"][:240] + "...") if len(n["content"]) > 240 else n["content"],
                "created_at": n.get("created_at") or "",
                "updated_at": n.get("updated_at") or n.get("created_at") or "",
                "source_note_id": None,
                "source_note_title": None,
                "stats": {
                    "word_count": n.get("word_count", 0),
                    "reading_time_min": n.get("reading_time_min", 0.0),
                    "tags": n.get("tags", ""),
                    "source_type": n.get("source_type", "manual"),
                    "file_name": n.get("file_name", "")
                },
                "raw_data": n
            })

    # 2. Summaries
    if material_type in ("All", "All Materials", "Extractive Summaries", "Summaries", "summaries", "summary"):
        summaries = get_all_summaries(search_query=search_query, subject_filter=subject_filter, sort_by=sort_by, db_path=db_path)
        for s in summaries:
            items.append({
                "id": s["id"],
                "material_type": "summary",
                "type_label": "AI Summary",
                "icon": "⚡",
                "title": s["title"],
                "subject": s.get("subject") or "General Study",
                "preview": (s["summary_text"][:240] + "...") if len(s["summary_text"]) > 240 else s["summary_text"],
                "created_at": s.get("created_at") or "",
                "updated_at": s.get("created_at") or "",
                "source_note_id": s.get("note_id"),
                "source_note_title": s.get("source_note_title"),
                "stats": {
                    "compression_ratio": s.get("compression_ratio", 0.0),
                    "method": s.get("method", "Extractive NLP"),
                    "key_points_count": len(s.get("key_points") or [])
                },
                "raw_data": s
            })

    # 3. Flashcard Decks
    if material_type in ("All", "All Materials", "Flashcard Decks", "Flashcards", "decks", "flashcards", "deck"):
        decks = get_all_decks(search_query=search_query, subject_filter=subject_filter, sort_by=sort_by, db_path=db_path)
        for d in decks:
            desc = d.get("description") or f"Flashcard study deck with {d.get('card_count', 0)} cards."
            items.append({
                "id": d["id"],
                "material_type": "deck",
                "type_label": "Flashcard Deck",
                "icon": "🗂️",
                "title": d["title"],
                "subject": d.get("subject") or "General Study",
                "preview": desc,
                "created_at": d.get("created_at") or "",
                "updated_at": d.get("created_at") or "",
                "source_note_id": d.get("note_id"),
                "source_note_title": d.get("source_note_title"),
                "stats": {
                    "card_count": d.get("card_count", 0),
                    "mastered_count": d.get("mastered_count", 0)
                },
                "raw_data": d
            })

    # 4. Quizzes
    if material_type in ("All", "All Materials", "Practice Quizzes", "Quizzes", "quizzes", "quiz"):
        quizzes = get_all_quizzes(search_query=search_query, subject_filter=subject_filter, sort_by=sort_by, db_path=db_path)
        for q in quizzes:
            q_list = q.get("questions") or []
            first_q = q_list[0]["question"] if q_list else "Practice multiple-choice questions."
            items.append({
                "id": q["id"],
                "material_type": "quiz",
                "type_label": "Practice Quiz",
                "icon": "🎯",
                "title": q["title"],
                "subject": q.get("subject") or "General Study",
                "preview": f"Q1: {first_q}",
                "created_at": q.get("created_at") or "",
                "updated_at": q.get("created_at") or "",
                "source_note_id": q.get("note_id"),
                "source_note_title": q.get("source_note_title"),
                "stats": {
                    "total_questions": q.get("total_questions", len(q_list))
                },
                "raw_data": q
            })

    # Unified sorting across types
    if sort_by == 'title_asc':
        items.sort(key=lambda x: x["title"].lower())
    elif sort_by == 'title_desc':
        items.sort(key=lambda x: x["title"].lower(), reverse=True)
    elif sort_by == 'recent_created':
        items.sort(key=lambda x: (x["created_at"] or ""), reverse=True)
    else:  # default recent_updated
        items.sort(key=lambda x: (x["updated_at"] or x["created_at"] or ""), reverse=True)

    return items
