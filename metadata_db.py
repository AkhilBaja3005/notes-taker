import os
import sqlite3
import datetime
from pathlib import Path
import frontmatter

def get_db_path() -> Path:
    """Returns /data/metadata.db if HF Persistent Bucket is mounted, otherwise ./metadata.db."""
    if Path("/data").exists() and os.access(Path("/data"), os.W_OK):
        return Path("/data/metadata.db")
    return Path(os.environ.get("METADATA_DB_PATH", "./metadata.db"))

def get_db_connection() -> sqlite3.Connection:
    """
    Returns an optimized SQLite connection with Write-Ahead Logging (WAL) mode
    and a 5000ms busy timeout to guarantee zero database locking under concurrent multi-process access.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lecture_metadata (
            file_name TEXT PRIMARY KEY,
            course TEXT,
            topic TEXT,
            lecture_date TEXT,
            model_used TEXT,
            source_file TEXT,
            tags TEXT,
            has_flashcards INTEGER,
            has_theorems INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_course ON lecture_metadata (course)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON lecture_metadata (lecture_date)")

    # Persistent Chat History Schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT,
            role TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_chat ON chat_history (user_id, session_id)")
    # Persistent Settings Schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # FTS5 Full-Text Search Virtual Table for Keyword & Exact Math/Acronym Search
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS lecture_fts USING fts5(
            file_name UNINDEXED,
            course,
            topic,
            content,
            tokenize='unicode61'
        )
    """)
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = None) -> str:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value=excluded.value,
            updated_at=CURRENT_TIMESTAMP
    """, (key, value))
    conn.commit()
    conn.close()

def save_chat_message(user_id: int, role: str, message: str, session_id: str = "default"):
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chat_history (user_id, session_id, role, message)
        VALUES (?, ?, ?, ?)
    """, (user_id, session_id, role, message))
    conn.commit()
    conn.close()

def get_recent_chat_history(user_id: int, session_id: str = None, limit: int = 8) -> list[dict]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    if session_id:
        cursor.execute("""
            SELECT role, message, created_at FROM chat_history
            WHERE user_id = ? AND session_id = ?
            ORDER BY id DESC LIMIT ?
        """, (user_id, session_id, limit))
    else:
        cursor.execute("""
            SELECT role, message, created_at FROM chat_history
            WHERE user_id = ?
            ORDER BY id DESC LIMIT ?
        """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in reversed(rows)]

def get_all_saved_chats(search_query: str = None, limit: int = 100) -> list[dict]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    if search_query and search_query.strip():
        q = f"%{search_query.strip()}%"
        cursor.execute("""
            SELECT user_id, session_id, role, message, created_at FROM chat_history
            WHERE message LIKE ?
            ORDER BY id DESC LIMIT ?
        """, (q, limit))
    else:
        cursor.execute("""
            SELECT user_id, session_id, role, message, created_at FROM chat_history
            ORDER BY id DESC LIMIT ?
        """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "session_id": r[1], "role": r[2], "content": r[3], "timestamp": r[4]} for r in rows]

def clear_user_chat_history(user_id: int):
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def index_lecture_file(file_path: Path):
    if file_path.name.endswith("_MOC.md"):
        return

    try:
        post = frontmatter.load(file_path)
        course = str(post.get("course", "General")).replace("[[", "").replace("]]", "").strip()
        topic = str(post.get("topic", file_path.stem)).replace("[[", "").replace("]]", "").strip()
        date_str = str(post.get("date", ""))
        model_used = str(post.get("model_used", ""))
        source_file = str(post.get("source_file", ""))
        tags = ",".join(post.get("tags", [])) if isinstance(post.get("tags"), list) else str(post.get("tags", ""))
        
        content = post.content
        has_flashcards = 1 if "## 4. Key Concept Q&A Flashcards" in content else 0
        has_theorems = 1 if any(w in content.lower() for w in ["theorem", "proof", "derivation"]) else 0

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO lecture_metadata (file_name, course, topic, lecture_date, model_used, source_file, tags, has_flashcards, has_theorems)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_name) DO UPDATE SET
                course=excluded.course,
                topic=excluded.topic,
                lecture_date=excluded.lecture_date,
                model_used=excluded.model_used,
                source_file=excluded.source_file,
                tags=excluded.tags,
                has_flashcards=excluded.has_flashcards,
                has_theorems=excluded.has_theorems,
                updated_at=CURRENT_TIMESTAMP
        """, (file_path.name, course, topic, date_str, model_used, source_file, tags, has_flashcards, has_theorems))
        
        # Populate FTS5 table
        cursor.execute("DELETE FROM lecture_fts WHERE file_name = ?", (file_path.name,))
        cursor.execute("""
            INSERT INTO lecture_fts (file_name, course, topic, content)
            VALUES (?, ?, ?, ?)
        """, (file_path.name, course, topic, content))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Warning: metadata index error for {file_path.name}: {e}")

def index_all_lectures(lectures_dir: Path):
    init_db()
    for f in lectures_dir.glob("*.md"):
        index_lecture_file(f)

def search_lectures_fts(query: str, course_filter: str = None, limit: int = 10) -> list[dict]:
    """Performs SQLite FTS5 BM25 keyword matching for exact acronyms, theorems, and formulas."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Sanitize FTS5 query terms (wrap individual tokens in quotes to avoid syntax errors with special math chars)
    terms = [f'"{t.strip()}"' for t in query.split() if t.strip() and t.strip() not in ['AND', 'OR', 'NOT', '"', "'"]]
    if not terms:
        conn.close()
        return []
    
    match_expr = " OR ".join(terms)
    
    try:
        if course_filter and course_filter != "All Courses":
            cursor.execute("""
                SELECT f.file_name, f.course, f.topic, snippet(lecture_fts, 3, '<b>', '</b>', '...', 25), m.lecture_date
                FROM lecture_fts f
                LEFT JOIN lecture_metadata m ON f.file_name = m.file_name
                WHERE lecture_fts MATCH ? AND f.course = ?
                ORDER BY rank LIMIT ?
            """, (match_expr, course_filter.strip(), limit))
        else:
            cursor.execute("""
                SELECT f.file_name, f.course, f.topic, snippet(lecture_fts, 3, '<b>', '</b>', '...', 25), m.lecture_date
                FROM lecture_fts f
                LEFT JOIN lecture_metadata m ON f.file_name = m.file_name
                WHERE lecture_fts MATCH ?
                ORDER BY rank LIMIT ?
            """, (match_expr, limit))
        rows = cursor.fetchall()
    except Exception as e:
        print(f"[!] FTS5 search notice: {e}")
        rows = []
    finally:
        conn.close()

    return [
        {
            "file_name": r[0],
            "course": r[1],
            "topic": r[2],
            "content": r[3],
            "date": r[4] or "",
            "section": "Exact Match (FTS5)",
            "score_type": "keyword"
        }
        for r in rows
    ]

def query_courses() -> list[str]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT course FROM lecture_metadata ORDER BY course ASC")
    rows = [r[0] for r in cursor.fetchall() if r[0]]
    conn.close()
    return rows

def query_topics(course: str = None) -> list[str]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    if course and course.strip() and course != "All Courses":
        cursor.execute("SELECT DISTINCT topic FROM lecture_metadata WHERE course = ? ORDER BY topic ASC", (course.strip(),))
    else:
        cursor.execute("SELECT DISTINCT topic FROM lecture_metadata ORDER BY topic ASC")
    rows = [r[0] for r in cursor.fetchall() if r[0]]
    conn.close()
    return rows

def query_lectures_by_date(lecture_date: datetime.date) -> list[dict]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    date_str = lecture_date.isoformat()
    cursor.execute("""
        SELECT file_name, course, topic, lecture_date, model_used, tags
        FROM lecture_metadata
        WHERE lecture_date = ?
        ORDER BY course ASC, topic ASC
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "filename": r[0],
            "course": r[1],
            "topic": r[2],
            "date": r[3],
            "model_used": r[4],
            "tags": r[5]
        }
        for r in rows
    ]

if __name__ == "__main__":
    index_all_lectures(Path("./lectures"))
    courses = query_courses()
    print(f"[+] SQLite Metadata Indexer active. Indexed courses: {courses}")
