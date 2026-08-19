import os
import io
import json
import time
import asyncio
import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException, Request, Header, Depends
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

AUTH_API_KEY = os.environ.get("INGEST_API_KEY", "").strip()

def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None)
):
    """
    Validates API Key if INGEST_API_KEY is configured.
    Allows same-origin browser UI requests seamlessly, while enforcing the API Key
    for external curl / python / automated programmatic calls.
    """
    if not AUTH_API_KEY:
        return True
    
    # If request originates from the same hosted UI (Hugging Face / localhost), allow seamlessly
    referer = request.headers.get("referer", "")
    sec_fetch_site = request.headers.get("sec-fetch-site", "")
    if sec_fetch_site in ("same-origin", "same-site") or "hf.space" in referer or "localhost" in referer or "127.0.0.1" in referer:
        return True

    provided_key = x_api_key
    if not provided_key and authorization:
        if authorization.startswith("Bearer "):
            provided_key = authorization.replace("Bearer ", "").strip()
        else:
            provided_key = authorization.strip()

    if provided_key != AUTH_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing API Key. Pass 'X-API-Key: <key>' or 'Authorization: Bearer <key>'."
        )
    return True

def notify_telegram_upload_complete(file_name: str, course_name: str, topic_name: str, note_path: str, model_used: str):
    """Dispatches a formatted confirmation message to the owner's Telegram bot whenever a file is ingested."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    
    allowed_ids = [int(uid.strip()) for uid in os.environ.get("ALLOWED_TELEGRAM_USER_IDS", "").split(",") if uid.strip().isdigit()]
    target_users = allowed_ids if allowed_ids else [8327334588]
    
    proxy_base_url = os.environ.get("TELEGRAM_API_BASE_URL", "").strip().rstrip("/")
    if not proxy_base_url:
        proxy_base_url = "https://notes-taker-uq8f.onrender.com"

    api_url = f"{proxy_base_url}/bot{token}/sendMessage"
    
    text = (
        f"✅ *Lecture Ingestion Complete!*\n\n"
        f"• 📚 *Course*: `{course_name}`\n"
        f"• 🎯 *Topic*: `{topic_name}`\n"
        f"• 📁 *Source*: `{file_name}`\n"
        f"• 🧠 *Model*: `{model_used}`\n"
        f"• 📝 *Obsidian Note*: `{Path(note_path).name}`\n\n"
        f"🔗 Synced to GitHub & Indexed in Vector Store."
    )
    
    import urllib.request
    for uid in target_users:
        try:
            payload = json.dumps({
                "chat_id": uid,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }).encode("utf-8")
            req = urllib.request.Request(
                api_url,
                data=payload,
                headers={"Content-Type": "application/json", "Connection": "close"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                pass
        except Exception as e:
            print(f"[!] Telegram upload notification error: {e}")

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
    query_topics,
    get_all_saved_chats,
    save_chat_message,
    get_setting,
    set_setting,
    clear_user_chat_history,
    query_lectures_by_date
)
from cheatsheet_generator import generate_course_cheatsheet
from bot import process_telegram_webhook

load_dotenv()

app = FastAPI(title="Academic Notes & AI Assistant API", version="2.0.0")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import WebSocket, WebSocketDisconnect

@app.get("/_stcore/health")
@app.get("/_stcore/host-config")
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "fastapi_react_hub"}

@app.websocket("/{full_path:path}")
async def catch_all_websocket(websocket: WebSocket, full_path: str):
    """
    Safely accept and drop any residual or legacy WebSocket probes (e.g. from previous Streamlit sessions)
    so Starlette's StaticFiles handler never encounters an unexpected WebSocket scope.
    """
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass

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
    scope: Optional[str] = "date"  # "date", "course", "topic"
    date: Optional[str] = None
    course: Optional[str] = None
    topic: Optional[str] = None
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
@app.post("/api/upload", dependencies=[Depends(verify_api_key)])
async def upload_lecture_material(
    request: Request,
    course_name: Optional[str] = Query(None),
    topic_name: Optional[str] = Query(None),
    lecture_date: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    is_dense_math: Optional[bool] = Query(None)
):
    content_type = request.headers.get("content-type", "")
    filename = None
    content = b""
    c_name = course_name
    t_name = topic_name
    l_date = lecture_date
    m_model = model or DEFAULT_MODEL
    dense_math = is_dense_math or False

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        
        # Extract metadata from form fields if present
        if not c_name and "course_name" in form:
            c_name = str(form.get("course_name") or "")
        if not t_name and "topic_name" in form:
            t_name = str(form.get("topic_name") or "")
        if not l_date and "lecture_date" in form:
            l_date = str(form.get("lecture_date") or "")
        if not model and "model" in form:
            m_model = str(form.get("model") or DEFAULT_MODEL)
        if is_dense_math is None and "is_dense_math" in form:
            dense_math = str(form.get("is_dense_math", "")).lower() in ("true", "1", "yes")

        # Extract file payload
        file_obj = form.get("file")
        if file_obj is not None:
            if hasattr(file_obj, "filename") and file_obj.filename:
                filename = file_obj.filename
                content = await file_obj.read()
            elif hasattr(file_obj, "read"):
                filename = f"ios_upload_{int(time.time())}.m4a"
                content = await file_obj.read()
            elif isinstance(file_obj, bytes):
                filename = f"ios_upload_{int(time.time())}.m4a"
                content = file_obj
            elif isinstance(file_obj, str):
                filename = f"ios_upload_{int(time.time())}.txt"
                content = file_obj.encode("utf-8")
        else:
            # Check any other uploaded form file
            for k, v in form.items():
                if hasattr(v, "filename") and v.filename:
                    filename = v.filename
                    content = await v.read()
                    break
    else:
        # Direct raw binary body (e.g. Content-Type: audio/m4a, application/pdf, etc.)
        content = await request.body()
        ext = ".m4a" if "audio" in content_type else (".pdf" if "pdf" in content_type else ".bin")
        filename = f"ios_upload_{int(time.time())}{ext}"

    if not content or len(content) == 0:
        raise HTTPException(status_code=422, detail="No file content or audio stream received.")

    if not filename:
        filename = f"ios_upload_{int(time.time())}.m4a"

    stem = Path(filename).stem
    c_name = c_name.strip() if (c_name and c_name.strip()) else "General"
    t_name = t_name.strip() if (t_name and t_name.strip()) else stem
    l_date = l_date.strip() if (l_date and l_date.strip()) else datetime.date.today().isoformat()

    save_path = INCOMING_DIR / filename
    with open(save_path, "wb") as buffer:
        buffer.write(content)

    try:
        out_note = process_file(
            file_path_str=str(save_path),
            course_name=c_name,
            topic_name=t_name,
            lecture_date=l_date,
            model=m_model,
            is_dense_math=dense_math
        )
        # Asynchronously dispatch proactive Telegram confirmation
        asyncio.create_task(
            asyncio.to_thread(
                notify_telegram_upload_complete,
                file_name=filename,
                course_name=c_name,
                topic_name=t_name,
                note_path=str(out_note),
                model_used=model
            )
        )
        return {
            "status": "success",
            "message": f"Successfully ingested {filename}",
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

@app.get("/api/topics")
def get_topics(course: Optional[str] = None):
    topics = query_topics(course=course)
    return {"topics": topics}

@app.post("/api/recap")
def get_multi_scope_recap(req: RecapRequest):
    scope = req.scope or "date"
    if scope == "course":
        target = req.course or "General"
    elif scope == "topic":
        target = req.topic or "Backpropagation"
    else:
        target = req.date or datetime.date.today().isoformat()

    try:
        content = generate_multi_scope_briefing(
            scope=scope,
            target=target,
            course=req.course,
            model=req.model
        )
        return {
            "scope": scope,
            "target": target,
            "content": content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- Settings & Automation -----------------
class SettingPayload(BaseModel):
    key: str
    value: str

@app.get("/api/settings")
def read_settings():
    auto_send = get_setting("auto_send_telegram_briefing", "true")
    send_time = get_setting("briefing_scheduled_time", "21:00")
    user_tz = get_setting("user_timezone", "Asia/Kolkata")
    return {
        "auto_send_telegram_briefing": auto_send.lower() in ("true", "1", "yes"),
        "briefing_scheduled_time": send_time,
        "user_timezone": user_tz
    }

@app.post("/api/settings")
def update_setting(payload: SettingPayload):
    set_setting(payload.key, payload.value)
    return {"status": "updated", "key": payload.key, "value": payload.value}

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
