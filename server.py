import os
import io
import json
import time
import asyncio
import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from core_engine import (
    get_available_courses,
    generate_daily_recap,
    query_exam_syllabus,
    generate_with_fallback,
    SUPPORTED_MODELS,
    DEFAULT_MODEL
)
from ingest_audio import process_file
from anki_exporter import generate_anki_deck_for_course, parse_flashcards_from_markdown
from vector_store import semantic_search_notes
from metadata_db import (
    query_courses,
    get_all_saved_chats,
    save_chat_message,
    clear_user_chat_history,
    query_lectures_by_date
)
from cheatsheet_generator import generate_course_cheatsheet
from bot import process_telegram_webhook

load_dotenv()

app = FastAPI(title="Academic Notes & AI Assistant API", version="2.0.0")

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LECTURES_DIR = Path(os.environ.get("LECTURES_DIR", "./lectures")).resolve()
INCOMING_DIR = Path(os.environ.get("WATCH_DIR", "./incoming_audio")).resolve()
INCOMING_DIR.mkdir(parents=True, exist_ok=True)

# ----------------- Models -----------------
class ChatRequest(BaseModel):
    user_id: int = 8327334588
    course: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    prompt: str
    model: Optional[str] = DEFAULT_MODEL

class CheatsheetRequest(BaseModel):
    course: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    model: Optional[str] = DEFAULT_MODEL

class RecapRequest(BaseModel):
    date: Optional[str] = None
    model: Optional[str] = DEFAULT_MODEL

class SaveChatPayload(BaseModel):
    user_id: int = 8327334588
    prompt: Optional[str] = ""
    response: Optional[str] = ""

# ----------------- Health & Status -----------------
@app.get("/healthz")
@app.get("/health")
@app.get("/ping")
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}

@app.get("/api/system_status")
def system_status():
    courses = query_courses() or get_available_courses()
    return {
        "active_model": DEFAULT_MODEL,
        "supported_models": SUPPORTED_MODELS,
        "total_courses": len(courses),
        "courses": courses,
        "persistent_storage": Path("/data").exists(),
        "vault_path": str(LECTURES_DIR)
    }

# ----------------- Courses & Lectures -----------------
@app.get("/api/courses")
def get_courses():
    courses = query_courses() or get_available_courses()
    return {"courses": courses}

@app.get("/api/lectures")
def list_lectures(course: Optional[str] = None, date: Optional[str] = None):
    results = []
    if date:
        try:
            d = datetime.date.fromisoformat(date)
            results = query_lectures_by_date(d)
        except ValueError:
            pass
    
    if not results:
        # Scan filesystem lectures
        if LECTURES_DIR.exists():
            for f in sorted(LECTURES_DIR.glob("*.md"), reverse=True):
                if f.name.endswith("_MOC.md"):
                    continue
                results.append({
                    "filename": f.name,
                    "title": f.stem.replace("_", " "),
                    "modified": datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                })
    return {"lectures": results}

@app.get("/api/lecture_content")
def get_lecture_content(filename: str):
    target = LECTURES_DIR / filename
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Lecture note file not found.")
    return {
        "filename": filename,
        "content": target.read_text(encoding="utf-8", errors="ignore")
    }

# ----------------- Vector Semantic Search -----------------
@app.get("/api/search")
def search_knowledge_base(q: str = Query(..., min_length=2), course: Optional[str] = None, n_results: int = 5):
    course_filter = None if (not course or course == "All Courses") else course
    matches = semantic_search_notes(q, n_results=n_results, course_filter=course_filter)
    return {"query": q, "count": len(matches), "results": matches}

# ----------------- Direct Ingestion Upload -----------------
@app.post("/api/upload")
async def upload_lecture_material(
    file: UploadFile = File(...),
    course_name: Optional[str] = Form(""),
    topic_name: Optional[str] = Form(""),
    lecture_date: Optional[str] = Form(""),
    model: Optional[str] = Form(DEFAULT_MODEL),
    is_dense_math: Optional[bool] = Form(False)
):
    stem = Path(file.filename).stem
    c_name = course_name.strip() if course_name else "General"
    t_name = topic_name.strip() if topic_name else stem
    l_date = lecture_date.strip() if lecture_date else datetime.date.today().isoformat()

    save_path = INCOMING_DIR / file.filename
    with open(save_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    try:
        out_note = process_file(
            file_path_str=str(save_path),
            course_name=c_name,
            topic_name=t_name,
            lecture_date=l_date,
            model=model,
            is_dense_math=is_dense_math
        )
        return {
            "status": "success",
            "message": f"Successfully ingested {file.filename}",
            "note_path": str(out_note),
            "note_content": out_note.read_text(encoding="utf-8")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- Exam Tutor & Chat -----------------
@app.post("/api/chat")
def chat_exam_tutor(req: ChatRequest):
    s_date = datetime.date.fromisoformat(req.start_date) if req.start_date else (datetime.date.today() - datetime.timedelta(days=30))
    e_date = datetime.date.fromisoformat(req.end_date) if req.end_date else datetime.date.today()

    try:
        save_chat_message(req.user_id, role="user", message=req.prompt)
        reply = query_exam_syllabus(req.course, s_date, e_date, req.prompt, model=req.model)
        save_chat_message(req.user_id, role="assistant", message=reply)
        return {"response": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/history")
def get_chat_history(search: Optional[str] = None):
    rows = get_all_saved_chats(search_query=search)
    sessions_map = {}
    for r in rows:
        sid = r.get("session_id") or "default"
        if sid not in sessions_map:
            sessions_map[sid] = {
                "session_id": sid,
                "first_message_time": r.get("timestamp") or datetime.datetime.now().isoformat(),
                "message_count": 0,
                "preview": r.get("content", "")[:60],
                "messages": []
            }
        sessions_map[sid]["messages"].append({
            "role": r.get("role", "user"),
            "message": r.get("content", ""),
            "created_at": r.get("timestamp", "")
        })
        sessions_map[sid]["message_count"] += 1

    threads = list(sessions_map.values())
    # Reverse messages inside each thread so they read chronologically (user prompt first, then assistant answer)
    for t in threads:
        t["messages"].reverse()

    return {"threads": threads}

@app.post("/api/save_chat")
def sync_chat(payload: SaveChatPayload):
    if payload.prompt:
        save_chat_message(payload.user_id, role="user", message=payload.prompt)
    if payload.response:
        save_chat_message(payload.user_id, role="assistant", message=payload.response)
    return {"status": "saved"}

# ----------------- Cheatsheet & Recap -----------------
@app.post("/api/cheatsheet")
def generate_cheatsheet(req: CheatsheetRequest):
    s_date = datetime.date.fromisoformat(req.start_date) if req.start_date else (datetime.date.today() - datetime.timedelta(days=90))
    e_date = datetime.date.fromisoformat(req.end_date) if req.end_date else datetime.date.today()
    try:
        content = generate_course_cheatsheet(req.course, s_date, e_date, model=req.model)
        return {"course": req.course, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recap")
def get_daily_recap(req: RecapRequest):
    target_d = datetime.date.fromisoformat(req.date) if req.date else datetime.date.today()
    try:
        content = generate_daily_recap(target_d, model=req.model)
        return {"date": target_d.isoformat(), "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- Flashcards & Anki Deck -----------------
@app.get("/api/flashcards")
def get_flashcards(course: Optional[str] = None):
    cards = []
    if LECTURES_DIR.exists():
        for f in LECTURES_DIR.glob("*.md"):
            if f.name.endswith("_MOC.md"):
                continue
            if course and course not in f.name:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            parsed = parse_flashcards_from_markdown(text)
            for q, a in parsed:
                cards.append({
                    "course": course or "General",
                    "file": f.name,
                    "question": q,
                    "answer": a
                })
    return {"count": len(cards), "flashcards": cards}

@app.get("/api/anki/download")
def download_anki_deck(course: str):
    deck_path = generate_anki_deck_for_course(LECTURES_DIR, course)
    if not deck_path or not deck_path.exists():
        raise HTTPException(status_code=404, detail="No flashcards found to compile Anki deck.")
    return FileResponse(
        path=str(deck_path),
        filename=deck_path.name,
        media_type="application/octet-stream"
    )

# ----------------- Telegram Webhook Gateway -----------------
@app.post("/telegram_webhook")
@app.post("/api/telegram_webhook")
async def telegram_webhook_handler(request: Request):
    try:
        update_dict = await request.json()
        asyncio.create_task(process_telegram_webhook(update_dict))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "handled", "error": str(e)}

# ----------------- Static SPA Frontend Mounting -----------------
DIST_DIR = Path("./frontend/dist").resolve()
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("STREAMLIT_SERVER_PORT", "7860"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
