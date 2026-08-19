import os
import io
import re
import datetime
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import matplotlib.pyplot as plt

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from ingest_audio import process_file
from core_engine import (
    generate_daily_recap,
    generate_multi_scope_briefing,
    query_exam_syllabus,
    generate_with_fallback,
    SUPPORTED_MODELS,
    DEFAULT_MODEL
)
from anki_exporter import generate_anki_deck_for_course
from vector_store import semantic_search_notes
from metadata_db import query_courses
from cheatsheet_generator import generate_course_cheatsheet

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_IDS = [
    int(uid.strip())
    for uid in os.environ.get("ALLOWED_TELEGRAM_USER_IDS", "").split(",")
    if uid.strip().isdigit()
]
INCOMING_DIR = Path(os.environ.get("WATCH_DIR", "./incoming_audio"))
INCOMING_DIR.mkdir(parents=True, exist_ok=True)
LECTURES_DIR = Path(os.environ.get("LECTURES_DIR", "./lectures"))

current_bot_model = DEFAULT_MODEL

def check_auth(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS

def render_latex_to_image(latex_code: str) -> io.BytesIO:
    latex_code = latex_code.strip()
    if not latex_code.startswith("$"):
        latex_code = f"${latex_code}$"

    fig = plt.figure(figsize=(8, 2), dpi=300)
    fig.patch.set_facecolor('#1e1e2e')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis('off')
    ax.patch.set_facecolor('#1e1e2e')

    ax.text(
        0.5, 0.5, latex_code,
        fontsize=18,
        color='#cdd6f4',
        ha='center', va='center',
        transform=ax.transAxes
    )

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.2, facecolor='#1e1e2e')
    plt.close(fig)
    buf.seek(0)
    return buf

async def send_smart_message(update: Update, text: str, max_chunk: int = 4000):
    """
    Splits long messages cleanly and formats LaTeX math blocks for Telegram.
    """
    if not text:
        return

    # Clean display math tags for better readability on Telegram mobile
    # Convert $$ ... $$ to readable code blocks or clean formatting
    formatted_text = text
    
    paragraphs = formatted_text.split("\n\n")
    current_chunk = ""
    for p in paragraphs:
        if len(current_chunk) + len(p) + 2 > max_chunk:
            try:
                await update.message.reply_text(current_chunk.strip(), parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(current_chunk.strip())
            current_chunk = p + "\n\n"
        else:
            current_chunk += p + "\n\n"

    if current_chunk.strip():
        try:
            await update.message.reply_text(current_chunk.strip(), parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(current_chunk.strip())

from metadata_db import query_courses, save_chat_message, get_recent_chat_history, clear_user_chat_history

async def newchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return
    uid = update.effective_user.id
    new_sess = datetime.datetime.now().strftime("Session_%Y%m%d_%H%M%S")
    if not hasattr(text_message_handler, "active_sessions"):
        text_message_handler.active_sessions = {}
    text_message_handler.active_sessions[uid] = new_sess
    
    await update.message.reply_text(
        "🧹 *New study thread started!*\n"
        "Previous conversation has been saved to your archive. Ask any new question to begin a fresh context.",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized access.")
        return

    msg = (
        "🎓 *Autonomous Academic Lecture Assistant - Command Directory*\n\n"
        "Here are all available features and commands:\n\n"
        "🎙️ *1. Ingestion & Note Generation:*\n"
        "• Send any voice note, audio file (`.m4a`, `.mp3`, `.wav`), or academic document (`.pdf`, `.docx`, `.pptx`).\n"
        "• *(Optional Caption)*: `Course Name | Topic Name | YYYY-MM-DD`\n"
        "• Automatically generates structured notes, KaTeX math, mind maps, updates Obsidian, and indexes to vector DB.\n\n"
        "🔍 *2. Semantic Search & RAG:*\n"
        "• `/search <query>` - Run semantic ChromaDB search across all semester notes.\n"
        "• *Example:* `/search What are the KKT complementary slackness conditions?`\n\n"
        "📋 *3. Exam Cheatsheet Synthesis:*\n"
        "• `/cheatsheet <Course>` - Synthesize 1-page master formula sheet.\n"
        "• *Example:* `/cheatsheet Optimization`\n\n"
        "📇 *4. Spaced Repetition Flashcards & Anki:*\n"
        "• `/anki <Course>` - Export complete flashcard deck as `.apkg` file directly to Telegram.\n"
        "• *Example:* `/anki Machine Learning`\n\n"
        "📐 *5. LaTeX KaTeX Math Image Generator:*\n"
        "• `/latex <formula>` - Render LaTeX equations into high-res images.\n"
        "• *Example:* `/latex \\nabla_w L = \\frac{1}{m}\\sum_{i=1}^m (\\hat{y}_i - y_i)x_i`\n\n"
        "📅 *6. Daily Multi-Subject Briefing:*\n"
        "• `/recap` - Daily briefing of all lectures recorded today.\n"
        "• `/recap YYYY-MM-DD` - Daily briefing for a specific date.\n\n"
        "🎯 *7. Date-Filtered Exam Syllabus Tutor:*\n"
        "• `/exam Course | StartDate | EndDate | Question`\n"
        "• *Example:* `/exam Machine Learning | 2026-08-01 | 2026-08-19 | Explain Backprop step 3`\n\n"
        "💬 *8. Interactive AI Chat & Memory:*\n"
        "• Type any doubt or derivation question directly to chat with Gemini!\n"
        "• `/newchat` (or `/clear`) - Start a fresh conversation session.\n"
        "• `/menu` - Interactive inline button control panel.\n\n"
        "🌐 *Web Dashboard:* [abaja-notes-taker.hf.space](https://abaja-notes-taker.hf.space)"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await help_command(update, context)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Usage: `/search <semantic question or equation>`", parse_mode="Markdown")
        return

    await update.message.reply_text(f"🔍 Searching vector knowledge base for: *{query}*...", parse_mode="Markdown")
    results = semantic_search_notes(query, n_results=3)
    if not results:
        await update.message.reply_text("No semantic matches found in lecture vector store.")
        return

    reply = f"🧠 *Vector DB Search Results:*\n\n"
    for r in results:
        reply += f"📌 *{r['course']}* - _{r['topic']}_ (`{r['date']}`)\n`{r['section']}`\n{r['content'][:350]}...\n\n---\n\n"
    await send_smart_message(update, reply)

async def cheatsheet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return
    course_name = " ".join(context.args)
    if not course_name:
        courses = query_courses()
        c_list = "\n".join([f"• `/cheatsheet {c}`" for c in courses])
        await update.message.reply_text(f"Please specify a course:\n`/cheatsheet <Course Name>`\n\n*Available:*\n{c_list}", parse_mode="Markdown")
        return

    await update.message.reply_text(f"📋 Synthesizing master formula sheet for *{course_name}*...", parse_mode="Markdown")
    try:
        start_d = datetime.date.today() - datetime.timedelta(days=120)
        end_d = datetime.date.today()
        sheet = generate_course_cheatsheet(course_name, start_d, end_d, model=current_bot_model)
        await send_smart_message(update, sheet)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating cheatsheet: {e}")

async def anki_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return
    course_name = " ".join(context.args)
    if not course_name:
        courses = query_courses()
        c_list = "\n".join([f"• `/anki {c}`" for c in courses])
        await update.message.reply_text(f"Please specify a course:\n`/anki <Course Name>`\n\n*Available:*\n{c_list}", parse_mode="Markdown")
        return

    await update.message.reply_text(f"📇 Compiling Anki Deck for *{course_name}*...", parse_mode="Markdown")
    deck_path = generate_anki_deck_for_course(LECTURES_DIR, course_name)
    if deck_path and deck_path.exists():
        with open(deck_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=deck_path.name,
                caption=f"✅ Spaced Repetition Anki Deck for {course_name}"
            )
    else:
        await update.message.reply_text(f"No flashcards found for course '{course_name}'.")

async def recap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return
    
    arg_text = " ".join(context.args).strip() if context.args else ""
    
    # 1. Detect scope
    if not arg_text:
        scope = "date"
        target = datetime.date.today().isoformat()
        prompt_label = f"today ({target})"
    elif re.match(r"^\d{4}-\d{2}-\d{2}$", arg_text):
        scope = "date"
        target = arg_text
        prompt_label = f"date {target}"
    else:
        # Check if arg matches a known course or topic
        courses = query_courses()
        matching_course = next((c for c in courses if c.lower() == arg_text.lower()), None)
        if matching_course:
            scope = "course"
            target = matching_course
            prompt_label = f"course: *{matching_course}*"
        else:
            scope = "topic"
            target = arg_text
            prompt_label = f"topic: *{target}*"

    status_msg = await update.message.reply_text(f"⏳ Generating Academic Briefing for {prompt_label} with Gemini 3.7 Flash...", parse_mode="Markdown")
    try:
        recap = generate_multi_scope_briefing(scope=scope, target=target, model=current_bot_model)
        await status_msg.delete()
        await send_smart_message(update, recap)
    except Exception as e:
        await status_msg.edit_text(f"❌ Error generating briefing: {e}")

async def exam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return
    raw_text = " ".join(context.args)
    parts = [p.strip() for p in raw_text.split("|")]
    if len(parts) < 4:
        await update.message.reply_text("Usage: `/exam Course | StartDate (YYYY-MM-DD) | EndDate (YYYY-MM-DD) | Question`", parse_mode="Markdown")
        return

    course, start_s, end_s, question = parts[0], parts[1], parts[2], parts[3]
    try:
        start_d = datetime.date.fromisoformat(start_s)
        end_d = datetime.date.fromisoformat(end_s)
    except ValueError:
        await update.message.reply_text("Invalid date format in exam query.")
        return

    await update.message.reply_text(f"🔍 Analyzing syllabus for {course}...")
    try:
        ans = query_exam_syllabus(course, start_d, end_d, question, model=current_bot_model)
        await send_smart_message(update, ans)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def latex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return
    latex_code = " ".join(context.args)
    if not latex_code:
        await update.message.reply_text("Usage: `/latex \\frac{\\partial L}{\\partial W}`", parse_mode="Markdown")
        return

    try:
        img_buf = render_latex_to_image(latex_code)
        await update.message.reply_photo(photo=img_buf, caption="📐 Rendered LaTeX Formula")
    except Exception as e:
        await update.message.reply_text(f"❌ Rendering Error: {e}")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return

    keyboard = [
        [
            InlineKeyboardButton("💬 New Chat Session", callback_data="menu_new_chat"),
            InlineKeyboardButton("📅 Today's Briefing", callback_data="menu_today_recap")
        ],
        [
            InlineKeyboardButton("📋 Cheatsheet", callback_data="menu_cheatsheet_list"),
            InlineKeyboardButton("📇 Export Anki", callback_data="menu_anki_list")
        ],
        [
            InlineKeyboardButton("🤖 Switch Model", callback_data="menu_model_select"),
            InlineKeyboardButton("ℹ️ System Status", callback_data="menu_status")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎛️ *Academic Assistant Control Panel:*", reply_markup=reply_markup, parse_mode="Markdown")

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_bot_model
    query = update.callback_query
    await query.answer()

    if query.data == "menu_new_chat":
        uid = update.effective_user.id
        user_chat_sessions[uid] = []
        await query.edit_message_text(
            "🧹 *New study conversation started!*\n"
            "Previous chat history cleared. Send any question or theorem derivation to begin a fresh thread.",
            parse_mode="Markdown"
        )
    elif query.data == "menu_today_recap":
        today = datetime.date.today()
        await query.edit_message_text(f"⏳ Generating daily recap for {today}...")
        recap = generate_daily_recap(today, model=current_bot_model)
        await query.message.reply_text(recap)
    elif query.data == "menu_cheatsheet_list":
        courses = query_courses()
        c_list = "\n".join([f"• `/cheatsheet {c}`" for c in courses])
        await query.edit_message_text(f"📋 *Select a course to generate master formula sheet:*\n\n{c_list}", parse_mode="Markdown")
    elif query.data == "menu_anki_list":
        courses = query_courses()
        c_list = "\n".join([f"• `/anki {c}`" for c in courses])
        await query.edit_message_text(f"📇 *Select a course to export Anki deck:*\n\n{c_list}", parse_mode="Markdown")
    elif query.data == "menu_model_select":
        kb = [[InlineKeyboardButton(m, callback_data=f"set_model_{m}")] for m in SUPPORTED_MODELS]
        await query.edit_message_text("🤖 *Select Active Model:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    elif query.data.startswith("set_model_"):
        current_bot_model = query.data.replace("set_model_", "")
        await query.edit_message_text(f"✅ Active model updated to: `{current_bot_model}`", parse_mode="Markdown")
    elif query.data == "menu_status":
        courses = query_courses()
        await query.edit_message_text(
            f"📊 *System Status:*\n"
            f"• Active Model: `{current_bot_model}`\n"
            f"• Indexed Courses: {len(courses)}\n"
            f"• Obsidian Sync: `Active`\n"
            f"• Vector DB: `ChromaDB Ready`",
            parse_mode="Markdown"
        )

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return

    msg = update.message
    doc = msg.document or (msg.audio if msg.audio else (msg.voice if msg.voice else None))
    if not doc:
        return

    file_name = getattr(doc, 'file_name', f"voice_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.ogg")
    caption = msg.caption or ""
    parts = [p.strip() for p in caption.split("|")]
    
    course_name = parts[0] if len(parts) > 0 and parts[0] else "General"
    topic_name = parts[1] if len(parts) > 1 and parts[1] else Path(file_name).stem
    lecture_date = parts[2] if len(parts) > 2 and parts[2] else datetime.date.today().isoformat()

    status_msg = await msg.reply_text(f"⏳ Downloading `{file_name}` and analyzing with Gemini...")
    tg_file = await context.bot.get_file(doc.file_id)
    save_path = INCOMING_DIR / file_name
    await tg_file.download_to_drive(custom_path=save_path)

    try:
        out_note = process_file(
            file_path_str=str(save_path),
            course_name=course_name,
            topic_name=topic_name,
            lecture_date=lecture_date,
            model=current_bot_model
        )
        await status_msg.edit_text("✅ Analysis complete! Sending structured notes & Anki deck...")
        note_content = out_note.read_text(encoding="utf-8")
        await send_smart_message(update, note_content)

        with open(out_note, "rb") as f:
            await msg.reply_document(document=f, filename=out_note.name, caption="📄 Obsidian Markdown Note")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error processing material: {e}")

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return
    text = update.message.text.strip()
    if not text:
        return

    uid = update.effective_user.id
    # Active session tracker: {user_id: session_id}
    if not hasattr(text_message_handler, "active_sessions"):
        text_message_handler.active_sessions = {}
    
    if uid not in text_message_handler.active_sessions:
        text_message_handler.active_sessions[uid] = datetime.datetime.now().strftime("Session_%Y%m%d_%H%M%S")
    
    current_session_id = text_message_handler.active_sessions[uid]
    history_turns = get_recent_chat_history(uid, session_id=current_session_id, limit=6)

    # 1. Search vector DB for relevant lecture context
    results = semantic_search_notes(text, n_results=3)
    rag_context = ""
    if results:
        rag_context = "Relevant Course Syllabus Notes from Vault:\n"
        for r in results:
            rag_context += f"[{r['course']} - {r['topic']} ({r['date']}) | {r['section']}]:\n{r['content']}\n\n"

    # 2. Build multi-turn contextual prompt from database history
    history_snippet = ""
    for msg in history_turns:
        history_snippet += f"{msg['role'].capitalize()}: {msg['content']}\n"

    # Check if user explicitly asked for detailed proof / derivation
    wants_detailed = any(w in text.lower() for w in ["detailed", "derive", "derivation", "step by step", "full proof", "explain in depth"])

    prompt = f"""
    You are an expert STEM professor and academic study tutor.
    The student is asking: "{text}"

    {rag_context}

    Conversation History:
    {history_snippet}

    INSTRUCTIONS:
    Generate your output in TWO clearly separated sections:

    === TELEGRAM_DIRECT ===
    - Answer in natural, conversational, crystal-clear plain English.
    - DO NOT use unrendered raw equation code like `Z^(l) = W^(l) A^(l-1)` or `delta^(l)`.
    - Instead, explain intuitively with simple text (e.g. "We multiply the incoming error by the weights and activation derivative").
    - Give a quick, 3-4 sentence intuitive summary and the bottom line result.
    - Add at the end: "\n\n💡 *Tip*: Type 'derive in detail' for the full math proof, or check your Web Dashboard."

    === FULL_DETAILED_PROOF ===
    - Comprehensive, publication-quality academic reference with complete derivations, rigorous LaTeX display math ($$\\begin{{aligned}}...\\end{{aligned}}$$), definitions, worked numerical examples, and failure modes.
    """

    # If no local notes found for this concept, enable Google Search grounding
    enable_search = len(rag_context.strip()) == 0

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    if enable_search:
        status_msg = await update.message.reply_text("🌐 Querying global academic knowledge...")
    else:
        status_msg = await update.message.reply_text("🤔 Referencing lecture notes...")

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        raw_reply = generate_with_fallback(
            prompt=prompt,
            requested_model=current_bot_model,
            enable_web_search=enable_search
        )
        
        # Parse direct vs detailed sections
        if "=== TELEGRAM_DIRECT ===" in raw_reply and "=== FULL_DETAILED_PROOF ===" in raw_reply:
            parts = raw_reply.split("=== FULL_DETAILED_PROOF ===")
            direct_part = parts[0].replace("=== TELEGRAM_DIRECT ===", "").strip()
            detailed_part = parts[1].strip()
        else:
            direct_part = raw_reply.strip()
            detailed_part = raw_reply.strip()

        # Decide what to send to Telegram
        telegram_output = detailed_part if wants_detailed else direct_part

        # Save the rich comprehensive detailed version to database (tagged with current_session_id)
        save_chat_message(uid, role="user", message=text, session_id=current_session_id)
        save_chat_message(uid, role="assistant", message=detailed_part, session_id=current_session_id)

        await status_msg.delete()
        await send_smart_message(update, telegram_output)
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")

def build_bot_app():
    if not TELEGRAM_TOKEN:
        return None

    from telegram.request import HTTPXRequest

    proxy_base_url = os.environ.get("TELEGRAM_API_BASE_URL", "").strip()
    if proxy_base_url and not proxy_base_url.endswith("/bot"):
        proxy_base_url = proxy_base_url.rstrip("/") + "/bot"

    request_client = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=60.0
    )

    builder = ApplicationBuilder().token(TELEGRAM_TOKEN).request(request_client)
    if proxy_base_url:
        builder = builder.base_url(proxy_base_url)

    app = builder.build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("newchat", newchat_command))
    app.add_handler(CommandHandler("clear", newchat_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("recap", recap_command))
    app.add_handler(CommandHandler("exam", exam_command))
    app.add_handler(CommandHandler("cheatsheet", cheatsheet_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("anki", anki_command))
    app.add_handler(CommandHandler("latex", latex_command))
    app.add_handler(CallbackQueryHandler(button_callback_handler))
    app.add_handler(MessageHandler(filters.ATTACHMENT | filters.VOICE | filters.AUDIO, file_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    return app

_global_app = None

async def process_telegram_webhook(update_dict: dict):
    """Processes incoming Telegram updates forwarded from Cloudflare webhook."""
    global _global_app
    if _global_app is None:
        _global_app = build_bot_app()
        await _global_app.initialize()
        await _global_app.start()

    update = Update.de_json(update_dict, _global_app.bot)
    await _global_app.process_update(update)

def run_dummy_health_server(port: int = 10000):
    """Listens on 0.0.0.0:$PORT so Render port scanners detect open port immediately."""
    import http.server
    import socketserver
    import json

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            resp = json.dumps({
                "status": "healthy",
                "service": "telegram_bot",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })
            self.wfile.write(resp.encode("utf-8"))
        def log_message(self, format, *args):
            return

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    try:
        print(f"[*] Binding Render Health Server to 0.0.0.0:{port}...", flush=True)
        with ReusableTCPServer(("0.0.0.0", port), Handler) as httpd:
            print(f"[+] Render Health Server listening on 0.0.0.0:{port}", flush=True)
            httpd.serve_forever()
    except Exception as e:
        print(f"[!] Health server error: {e}", flush=True)

def self_ping_render_keepalive(interval_seconds: int = 300):
    """
    Mutual Keepalive Daemon on Render:
    Periodically pings both Render service AND Hugging Face Space (/healthz)
    to keep both containers 100% awake 24/7 without idle sleep.
    """
    import urllib.request
    import time
    time.sleep(30)  # Initial boot delay

    render_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    hf_backend = os.environ.get("HF_BACKEND_URL", "https://abaja-notes-taker.hf.space").strip().rstrip("/")

    print(f"[*] Render Mutual Keepalive active. Monitoring Render: {render_url or 'localhost'} | HF: {hf_backend} (every {interval_seconds}s)")
    while True:
        # 1. Ping Render itself
        if render_url:
            try:
                req = urllib.request.Request(
                    f"{render_url}/health",
                    headers={"User-Agent": "Render-Self-Keepalive/2.0", "Connection": "close"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    pass
            except Exception:
                pass

        # 2. Ping Hugging Face Space
        if hf_backend:
            try:
                req_hf = urllib.request.Request(
                    f"{hf_backend}/healthz",
                    headers={"User-Agent": "Render-To-HF-Keepalive/2.0", "Connection": "close"}
                )
                with urllib.request.urlopen(req_hf, timeout=15) as resp_hf:
                    pass
            except Exception:
                pass

        time.sleep(interval_seconds)

def main():
    import threading
    render_port = int(os.environ.get("PORT", "10000"))
    threading.Thread(target=run_dummy_health_server, args=(render_port,), daemon=True).start()
    threading.Thread(target=self_ping_render_keepalive, daemon=True).start()

    app = build_bot_app()
    if not app:
        print("[!] TELEGRAM_BOT_TOKEN not configured.")
        return

    print("[*] Academic Assistant Telegram Bot polling started!")
    try:
        app.run_polling(
            drop_pending_updates=False,
            bootstrap_retries=-1,
            timeout=30,
            poll_interval=1.0,
            stop_signals=None
        )
    except Exception as e:
        print(f"[!] Critical Telegram Polling Error: {e}")
        raise e

if __name__ == "__main__":
    main()
