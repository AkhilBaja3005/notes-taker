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

def init_db():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
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
    conn.commit()
    conn.close()

def save_chat_message(user_id: int, role: str, message: str, session_id: str = "default"):
    init_db()
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chat_history (user_id, session_id, role, message)
        VALUES (?, ?, ?, ?)
    """, (user_id, session_id, role, message))
    conn.commit()
    conn.close()

def get_recent_chat_history(user_id: int, session_id: str = None, limit: int = 8) -> list[dict]:
    init_db()
    conn = sqlite3.connect(get_db_path())
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
    conn = sqlite3.connect(get_db_path())
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
    conn = sqlite3.connect(get_db_path())
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

        conn = sqlite3.connect(get_db_path())
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
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Warning: metadata index error for {file_path.name}: {e}")

def index_all_lectures(lectures_dir: Path):
    init_db()
    for f in lectures_dir.glob("*.md"):
        index_lecture_file(f)

def query_courses() -> list[str]:
    init_db()
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT course FROM lecture_metadata ORDER BY course ASC")
    rows = [r[0] for r in cursor.fetchall() if r[0]]
    conn.close()
    return rows

if __name__ == "__main__":
    index_all_lectures(Path("./lectures"))
    courses = query_courses()
    print(f"[+] SQLite Metadata Indexer active. Indexed courses: {courses}")
