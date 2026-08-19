import os
import io
import re
import datetime
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import matplotlib.pyplot as plt

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    if len(text) <= max_chunk:
        try:
            await update.message.reply_text(text, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(text)
        return

    paragraphs = text.split("\n\n")
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
    clear_user_chat_history(uid)
    await update.message.reply_text(
        "🧹 *New study conversation started!*\n"
        "Previous chat history cleared and reset in database. Ask any question to begin a fresh thread.",
        parse_mode="Markdown"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized access.")
        return

    msg = (
        "🎓 *Autonomous Academic Lecture Assistant*\n\n"
        "Send audio notes, slides, or documents with caption:\n"
        "`Course Name | Topic Name | YYYY-MM-DD`\n\n"
        "💬 *Interactive Academic Chat:*\n"
        "• Simply type any doubt or follow-up question directly in the chat!\n"
        "• `/newchat` - Start a fresh conversation session\n\n"
        "⚡ *Commands:*\n"
        "• `/search <query>` - Semantic Vector Search across all notes\n"
        "• `/cheatsheet <Course>` - Master Exam Formula Sheet\n"
        "• `/anki <course>` - Export complete Anki Flashcard deck (.apkg)\n"
        "• `/recap [YYYY-MM-DD]` - Daily Multi-Subject briefing\n"
        "• `/exam Course | StartDate | EndDate | Question` - Exam Doubt Tutor\n"
        "• `/latex <formula>` - Render LaTeX math to image\n"
        "• `/menu` - Interactive Control Panel"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

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
    if context.args:
        try:
            target_date = datetime.date.fromisoformat(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid date format. Use YYYY-MM-DD.")
            return
    else:
        target_date = datetime.date.today()

    await update.message.reply_text(f"⏳ Generating daily recap for {target_date}...")
    try:
        recap = generate_daily_recap(target_date, model=current_bot_model)
        await send_smart_message(update, recap)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

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
    history_turns = get_recent_chat_history(uid, limit=8)

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

    prompt = f"""
    You are an expert STEM professor and academic study tutor.
    Answer the student's question accurately using standard Markdown and LaTeX math ($...$ for inline, $$\\begin{{aligned}}...\\end{{aligned}}$$ for display math).

    {rag_context}

    Conversation History:
    {history_snippet}
    Student: {text}
    """

    status_msg = await update.message.reply_text("🤔 Thinking & referencing lecture notes...")
    try:
        reply = generate_with_fallback(prompt=prompt, requested_model=current_bot_model)
        
        # Save both user prompt and assistant response to SQLite database
        save_chat_message(uid, role="user", message=text)
        save_chat_message(uid, role="assistant", message=reply)

        await status_msg.delete()
        await send_smart_message(update, reply)
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")

def main():
    if not TELEGRAM_TOKEN:
        print("[!] TELEGRAM_BOT_TOKEN not configured.")
        return

    from telegram.request import HTTPXRequest

    request_client = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=60.0
    )

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).request(request_client).build()
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

    print("[*] Academic Assistant Telegram Bot polling started!")
    try:
        app.run_polling(
            drop_pending_updates=False,
            bootstrap_retries=-1,
            timeout=30,
            poll_interval=1.0
        )
    except Exception as e:
        print(f"[!] Critical Telegram Polling Error: {e}")
        raise e

if __name__ == "__main__":
    main()
