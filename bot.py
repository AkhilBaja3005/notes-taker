import os
import re
import io
import datetime
from pathlib import Path
from dotenv import load_dotenv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from core_engine import (
    generate_daily_recap,
    query_exam_syllabus,
    get_available_courses,
    SUPPORTED_MODELS,
    DEFAULT_MODEL
)
from ingest_audio import process_file

load_dotenv()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
INCOMING_DIR = Path(os.environ.get("WATCH_DIR", "./incoming_audio"))
INCOMING_DIR.mkdir(parents=True, exist_ok=True)
LECTURES_DIR = Path(os.environ.get("LECTURES_DIR", "./lectures"))

raw_allowed = os.environ.get("ALLOWED_TELEGRAM_USER_IDS", "").strip()
ALLOWED_USERS = set(int(uid.strip()) for uid in raw_allowed.split(",") if uid.strip().isdigit())

current_bot_model = DEFAULT_MODEL

def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS

async def send_smart_message(update: Update, text: str, document_bytes: bytes = None, filename: str = "notes.md"):
    target = update.effective_message

    if document_bytes:
        doc_io = io.BytesIO(document_bytes)
        doc_io.name = filename
        await target.reply_document(
            document=doc_io,
            caption=f"📄 Full document attached: `{filename}`",
            parse_mode="Markdown"
        )

    max_chunk = 3800
    if len(text) <= max_chunk:
        try:
            await target.reply_markdown(text)
        except Exception:
            await target.reply_text(text)
        return

    paragraphs = text.split("\n\n")
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) + 2 > max_chunk:
            if current_chunk.strip():
                try:
                    await target.reply_markdown(current_chunk.strip())
                except Exception:
                    await target.reply_text(current_chunk.strip())
            current_chunk = p + "\n\n"
        else:
            current_chunk += p + "\n\n"

    if current_chunk.strip():
        try:
            await target.reply_markdown(current_chunk.strip())
        except Exception:
            await target.reply_text(current_chunk.strip())

def render_latex_image(latex_expr: str) -> io.BytesIO:
    clean_latex = latex_expr.strip().strip("$")
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.patch.set_facecolor('#1e1e1e')
    
    t = plt.text(
        0.5, 0.5, f"${clean_latex}$",
        fontsize=18,
        color='white',
        ha='center',
        va='center',
        usetex=False
    )
    
    plt.axis('off')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.2, dpi=200, facecolor=fig.get_facecolor(), transparent=False)
    plt.close(fig)
    buf.seek(0)
    return buf

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(f"⛔ Unauthorized. Your Telegram User ID is: `{user_id}`.\nAdd this ID to `ALLOWED_TELEGRAM_USER_IDS` in `.env` to access this bot.", parse_mode="Markdown")
        return

    help_text = (
        "🎓 *Autonomous Academic Lecture Assistant*\n\n"
        f"🤖 *Active Model:* `{current_bot_model}`\n"
        f"👤 *Your User ID:* `{user_id}`\n\n"
        "*✨ Supported Features:*\n"
        "• **Direct Ingestion**: Send audio, voice notes, PDFs, docx, or slides.\n"
        "• **Interactive Menus**: Tap `/menu` for one-tap course & date selection.\n"
        "• **LaTeX Rendering**: Use `/latex <equation>` to render math images.\n"
        "• **Smart Chunking**: Full markdown files automatically attached for large notes.\n\n"
        "*Quick Commands:*\n"
        "• `/menu` - Interactive buttons for courses, recaps & exam prep\n"
        "• `/recap [YYYY-MM-DD]` - Daily briefing across all classes\n"
        "• `/exam <Course> | <Start> | <End> | <Question>` - Syllabus Exam prep\n"
        "• `/latex <formula>` - Render LaTeX equation to image\n"
        "• `/model [name]` - Switch Gemini Flash models\n"
    )
    await update.message.reply_markdown(help_text)

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    courses = get_available_courses()
    keyboard = [
        [InlineKeyboardButton("📅 Today's Daily Recap", callback_data="recap_today")],
        [InlineKeyboardButton("⚙️ Change Gemini Model", callback_data="show_models")]
    ]
    
    if courses:
        course_buttons = [InlineKeyboardButton(f"📚 {c}", callback_data=f"select_course_{c}") for c in courses[:6]]
        for i in range(0, len(course_buttons), 2):
            keyboard.append(course_buttons[i:i+2])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎓 *Academic Dashboard Menu*\nChoose an action or course below:", reply_markup=reply_markup, parse_mode="Markdown")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_bot_model
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "recap_today":
        today = datetime.date.today()
        await query.edit_message_text(f"⏳ Generating daily briefing for {today}...")
        try:
            recap = generate_daily_recap(today, model=current_bot_model)
            await send_smart_message(update, recap)
        except Exception as e:
            await query.edit_message_text(f"❌ Error generating briefing: {e}")
        
    elif data == "show_models":
        buttons = [[InlineKeyboardButton(f"{'✅ ' if m == current_bot_model else ''}{m}", callback_data=f"set_model_{m}")] for m in SUPPORTED_MODELS]
        await query.edit_message_text("🤖 *Select Active Gemini Model:*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    elif data.startswith("set_model_"):
        new_model = data.replace("set_model_", "")
        current_bot_model = new_model
        await query.edit_message_text(f"✅ Active model updated to `{current_bot_model}`", parse_mode="Markdown")

    elif data.startswith("select_course_"):
        selected_course = data.replace("select_course_", "")
        today = datetime.date.today()
        start = today - datetime.timedelta(days=30)
        await query.edit_message_text(
            f"📚 *Selected Course:* {selected_course}\n\n"
            f"To ask a doubt or generate a mock exam for this course, send:\n"
            f"`/exam {selected_course} | {start} | {today} | Your Question`",
            parse_mode="Markdown"
        )

async def latex_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
        
    raw_latex = " ".join(context.args).strip()
    if not raw_latex:
        await update.message.reply_text("Usage: `/latex \\frac{\\partial L}{\\partial W} = \\delta A^T`", parse_mode="Markdown")
        return

    try:
        img_buf = render_latex_image(raw_latex)
        await update.message.reply_photo(photo=img_buf, caption=f"LaTeX: `{raw_latex}`", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error rendering LaTeX: `{e}`")

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_bot_model
    if not is_authorized(update.effective_user.id):
        return

    if context.args:
        requested = context.args[0].strip()
        if requested in SUPPORTED_MODELS:
            current_bot_model = requested
            await update.message.reply_text(f"✅ Active model updated to `{current_bot_model}`", parse_mode="Markdown")
        else:
            supported = ", ".join([f"`{m}`" for m in SUPPORTED_MODELS])
            await update.message.reply_text(f"❌ Unsupported model. Supported models are:\n{supported}", parse_mode="Markdown")
    else:
        supported = "\n".join([f"• `{m}`" + (" *(active)*" if m == current_bot_model else "") for m in SUPPORTED_MODELS])
        await update.message.reply_text(f"🤖 *Active Model:* `{current_bot_model}`\n\n*Available Models:*\n{supported}\n\nTo switch: `/model <model_name>`", parse_mode="Markdown")

async def recap_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    target_date = datetime.date.today()
    if context.args:
        try:
            target_date = datetime.date.fromisoformat(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Please use YYYY-MM-DD.")
            return

    await update.message.reply_text(f"⏳ Generating daily briefing for {target_date} using `{current_bot_model}`...", parse_mode="Markdown")
    try:
        recap = generate_daily_recap(target_date, model=current_bot_model)
        await send_smart_message(update, recap, document_bytes=recap.encode("utf-8"), filename=f"Recap_{target_date}.md")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def exam_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    raw_query = " ".join(context.args)
    if "|" not in raw_query:
        await update.message.reply_text("❌ Format: `/exam Course | YYYY-MM-DD | YYYY-MM-DD | Question`")
        return

    parts = [p.strip() for p in raw_query.split("|")]
    if len(parts) != 4:
        await update.message.reply_text("❌ Missing parameters. Provide: `Course | Start Date | End Date | Question`")
        return

    course, start_s, end_s, question = parts
    try:
        start_d = datetime.date.fromisoformat(start_s)
        end_d = datetime.date.fromisoformat(end_s)
    except ValueError:
        await update.message.reply_text("❌ Invalid dates. Use YYYY-MM-DD format.")
        return

    await update.message.reply_text(f"🔍 Searching notes for *{course}* ({start_d} to {end_d}) using `{current_bot_model}`...", parse_mode="Markdown")
    try:
        answer = query_exam_syllabus(course, start_d, end_d, question, model=current_bot_model)
        await send_smart_message(update, answer, document_bytes=answer.encode("utf-8"), filename=f"Exam_QnA_{course.replace(' ', '_')}.md")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_media_or_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized user.")
        return

    message = update.message
    file_obj = message.audio or message.voice or message.document

    if not file_obj:
        return

    file_size_mb = getattr(file_obj, "file_size", 0) / (1024 * 1024)
    if file_size_mb > 20:
        await message.reply_text(f"⚠️ *File Size Limit Warning:* File is {file_size_mb:.1f} MB. Standard Telegram Bot API caps downloads at 20MB. If download fails, please upload via the Streamlit web dashboard or compress the audio.", parse_mode="Markdown")

    file_id = file_obj.file_id
    file_name = getattr(file_obj, "file_name", None) or f"recording_{int(datetime.datetime.now().timestamp())}.m4a"
    
    caption = (message.caption or "").strip()
    course = "General"
    topic = Path(file_name).stem.replace("_", " ")
    lecture_date = datetime.date.today().isoformat()

    if caption:
        if "|" in caption:
            parts = [p.strip() for p in caption.split("|")]
            if len(parts) >= 1 and parts[0]:
                course = parts[0]
            if len(parts) >= 2 and parts[1]:
                topic = parts[1]
            if len(parts) >= 3 and parts[2]:
                try:
                    datetime.date.fromisoformat(parts[2])
                    lecture_date = parts[2]
                except ValueError:
                    pass
        else:
            topic = caption

    status_msg = await message.reply_text(f"📥 Receiving file: `{file_name}`\n• Course: *{course}*\n• Topic: *{topic}*\n• Date: *{lecture_date}*", parse_mode="Markdown")

    local_path = INCOMING_DIR / f"{lecture_date}_{course.replace(' ', '_')}_{topic.replace(' ', '_')}_{file_name}"
    
    try:
        telegram_file = await context.bot.get_file(file_id)
        await telegram_file.download_to_drive(str(local_path))
        
        await status_msg.edit_text(f"⚙️ Processing with Gemini `{current_bot_model}`...\nExtracting LaTeX proofs, exam notes & flashcards.", parse_mode="Markdown")
        
        output_file = process_file(
            file_path_str=str(local_path),
            course_name=course,
            topic_name=topic,
            lecture_date=lecture_date,
            model=current_bot_model
        )
        
        notes_content = output_file.read_text(encoding="utf-8")
        
        await status_msg.edit_text(
            f"✅ *Structured Notes Generated Successfully!*\n\n"
            f"• *Course:* {course}\n"
            f"• *Topic:* {topic}\n"
            f"• *Date:* {lecture_date}\n\n"
            f"Sending complete notes & markdown file below:",
            parse_mode="Markdown"
        )
        await send_smart_message(update, notes_content, document_bytes=notes_content.encode("utf-8"), filename=output_file.name)

    except Exception as e:
        await status_msg.edit_text(f"❌ Error processing file: `{e}`\n\n_Note: If file exceeded 20MB, please upload via the Streamlit web dashboard._", parse_mode="Markdown")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set.")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("recap", recap_cmd))
    app.add_handler(CommandHandler("exam", exam_cmd))
    app.add_handler(CommandHandler("latex", latex_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.Document.ALL, handle_media_or_doc))
    print(f"[+] Telegram Bot service running with default model: {current_bot_model}")
    app.run_polling()
