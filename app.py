import os
import streamlit as st
import datetime
from pathlib import Path
from audio_recorder_streamlit import audio_recorder
from core_engine import (
    get_available_courses,
    generate_daily_recap,
    query_exam_syllabus,
    SUPPORTED_MODELS,
    DEFAULT_MODEL
)
from ingest_audio import process_file
from anki_exporter import generate_anki_deck_for_course, parse_flashcards_from_markdown
from vector_store import semantic_search_notes
from metadata_db import query_courses, get_all_saved_chats, clear_user_chat_history
from cheatsheet_generator import generate_course_cheatsheet
import frontmatter

st.set_page_config(page_title="Academic Lecture & Notes Hub", page_icon="🎓", layout="wide")

# --- Security Gate for Public Deployments ---
AUTH_PASSWORD = os.environ.get("STREAMLIT_PASSWORD")
if AUTH_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 Academic Lecture Assistant Portal")
        entered_pwd = st.text_input("Enter Access Password", type="password")
        if st.button("Unlock Dashboard", type="primary"):
            if entered_pwd == AUTH_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Incorrect Password.")
        st.stop()

st.title("🎓 Graduate Lecture, Notes & Exam Hub")

with st.sidebar:
    st.header("⚙️ Model Architecture")
    st.info(
        "🧠 **Intelligent Tiered Routing:**\n"
        "• **Audio / Dense Math**: `gemini-3.6-flash` (Acoustic & proof reasoning)\n"
        "• **Typed PDFs & Slides**: `gemini-3.1-flash-lite` (350+ tokens/sec, low latency)\n"
        "• **Global Knowledge**: Google Search Grounding enabled"
    )
    
    st.markdown("---")
    st.subheader("Manual Model Override")
    ALL_AVAILABLE_MODELS = [
        "Auto (Workload-Aware)",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-flash-latest"
    ]
    selected_model_choice = st.selectbox(
        "Active Generation Model",
        ALL_AVAILABLE_MODELS,
        index=0,
        help="Select Auto for optimal cost and performance routing, or override manually."
    )
    active_model = None if selected_model_choice == "Auto (Workload-Aware)" else selected_model_choice

tab_upload, tab_recap, tab_exam, tab_cheatsheet, tab_search, tab_anki, tab_history = st.tabs([
    "📤 Ingestion & Mic", 
    "📅 Daily Recap", 
    "🎯 Exam Prep", 
    "📋 Cheatsheet Generator",
    "🔍 Semester Search", 
    "📇 Flashcards & Anki",
    "💬 Saved Chat History"
])

with tab_upload:
    st.subheader("Direct Lecture Ingestion (Audio, PDF, Slides & In-Browser Mic)")
    c1, c2 = st.columns(2)
    with c1:
        up_course = st.text_input("Course Name", placeholder="e.g. Machine Learning")
    with c2:
        up_topic = st.text_input("Topic Name", placeholder="e.g. Convex Optimization & Duals")
    
    c3, c4 = st.columns(2)
    with c3:
        up_date = st.date_input("Lecture / Material Date", datetime.date.today())
    with c4:
        is_dense_math = st.checkbox("Dense Math Paper / Hand-Annotated (Use Flash)", value=False)

    st.markdown("##### 🎙️ Option A: Live Microphone Recording")
    audio_bytes = audio_recorder(
        text="Click to record lecture voice note",
        recording_color="#e78284",
        neutral_color="#89b4fa",
        icon_size="2x"
    )

    if audio_bytes:
        st.audio(audio_bytes, format="audio/wav")
        if st.button("Process Live Recording", type="primary", disabled=(not up_course or not up_topic)):
            with st.spinner("Processing live lecture recording with Mermaid diagram synthesis..."):
                incoming_dir = Path("./incoming_audio")
                incoming_dir.mkdir(parents=True, exist_ok=True)
                rec_filename = f"live_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                save_path = incoming_dir / rec_filename
                
                save_path.write_bytes(audio_bytes)
                try:
                    out_path = process_file(
                        file_path_str=str(save_path),
                        course_name=up_course,
                        topic_name=up_topic,
                        lecture_date=up_date.isoformat(),
                        model=active_model,
                        is_dense_math=is_dense_math
                    )
                    st.success(f"✅ Notes & Mermaid diagram successfully generated from live mic!")
                    st.markdown(out_path.read_text(encoding="utf-8"))
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()
    st.markdown("##### 📁 Option B: Upload Audio Recording or Academic Document")
    uploaded_file = st.file_uploader(
        "Select File",
        type=["m4a", "mp3", "wav", "aac", "ogg", "flac", "pdf", "docx", "doc", "txt", "md", "pptx", "ppt"]
    )

    # Universal metadata auto-extraction across all audio, document, and slide formats
    auto_course = up_course.strip()
    auto_topic = up_topic.strip()
    auto_date = up_date

    if uploaded_file:
        stem = Path(uploaded_file.name).stem
        
        # 1. Check for ISO Date pattern anywhere in filename (YYYY-MM-DD or YYYYMMDD)
        date_match = re.search(r'(\d{4}[-_]\d{2}[-_]\d{2})', stem)
        clean_stem = stem
        if date_match:
            try:
                auto_date = datetime.date.fromisoformat(date_match.group(1).replace("_", "-"))
                clean_stem = stem.replace(date_match.group(0), "").strip("_- ")
            except ValueError:
                pass

        # 2. Extract Course and Topic based on common academic separators (|, --, _, -)
        if "|" in clean_stem:
            parts = [p.strip() for p in clean_stem.split("|") if p.strip()]
        elif "--" in clean_stem:
            parts = [p.strip() for p in clean_stem.split("--") if p.strip()]
        elif "_" in clean_stem:
            parts = [p.strip() for p in clean_stem.split("_") if p.strip()]
        elif "-" in clean_stem:
            parts = [p.strip() for p in clean_stem.split("-") if p.strip()]
        else:
            parts = [clean_stem]

        if not auto_course:
            auto_course = parts[0] if parts else "General"
        if not auto_topic:
            auto_topic = " ".join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else stem)

    is_btn_disabled = (uploaded_file is None)

    if st.button("Process & Generate Structured Notes", type="primary", disabled=is_btn_disabled):
        final_course = up_course.strip() if up_course.strip() else auto_course
        final_topic = up_topic.strip() if up_topic.strip() else auto_topic
        final_date = up_date if up_course.strip() else auto_date

        with st.spinner(f"Analyzing [{final_course}] {final_topic} with Gemini & generating notes..."):
            incoming_dir = Path("./incoming_audio")
            incoming_dir.mkdir(parents=True, exist_ok=True)
            save_path = incoming_dir / uploaded_file.name
            
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            try:
                out_path = process_file(
                    file_path_str=str(save_path),
                    course_name=final_course,
                    topic_name=final_topic,
                    lecture_date=final_date.isoformat(),
                    model=active_model,
                    is_dense_math=is_dense_math
                )
                st.success(f"✅ Notes successfully generated for '{final_course} - {final_topic}', synced to Obsidian, and indexed in Vector DB!")
                st.markdown(out_path.read_text(encoding="utf-8"))
            except Exception as e:
                st.error(f"Error processing file: {e}")

with tab_recap:
    st.subheader("Daily Multi-Subject Executive Summary")
    selected_date = st.date_input("Select Lecture Date for Recap", datetime.date.today())
    if st.button("Generate Daily Briefing", type="primary"):
        with st.spinner(f"Analyzing all lectures for {selected_date}..."):
            try:
                recap_md = generate_daily_recap(selected_date, model=active_model)
                st.markdown(recap_md)
            except Exception as e:
                st.error(f"Error generating briefing: {e}")

with tab_exam:
    st.subheader("Date-Filtered Syllabus & Exam Tutor")
    courses = query_courses() or get_available_courses()
    
    if not courses:
        st.info("No lecture notes found in `./lectures`. Upload files in the 'Upload' tab or via Telegram.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            course = st.selectbox("Select Course", courses)
        with c2:
            start_date = st.date_input("Syllabus Start Date", datetime.date.today() - datetime.timedelta(days=30))
        with c3:
            end_date = st.date_input("Syllabus End Date", datetime.date.today())

        st.divider()

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_prompt := st.chat_input("Ask a doubt, generate mock exams, or summarize derivations..."):
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing lecture syllabus with Gemini context caching..."):
                    try:
                        reply = query_exam_syllabus(course, start_date, end_date, user_prompt, model=active_model)
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    except Exception as e:
                        st.error(f"Error during query: {e}")

with tab_cheatsheet:
    st.subheader("📋 1-Click Master Exam Cheatsheet & Formula Reference")
    courses = query_courses() or get_available_courses()
    if not courses:
        st.info("No courses available.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            cs_course = st.selectbox("Select Course for Cheatsheet", courses, key="cs_course")
        with c2:
            cs_start = st.date_input("Start Date", datetime.date.today() - datetime.timedelta(days=90), key="cs_start")
        with c3:
            cs_end = st.date_input("End Date", datetime.date.today(), key="cs_end")

        if st.button("Generate Master Exam Cheatsheet", type="primary"):
            with st.spinner(f"Synthesizing high-yield formula sheet for {cs_course}..."):
                try:
                    sheet_md = generate_course_cheatsheet(cs_course, cs_start, cs_end, model=active_model)
                    st.markdown(sheet_md)
                    st.download_button(
                        label=f"⬇️ Download {cs_course} Cheatsheet (.md)",
                        data=sheet_md,
                        file_name=f"{cs_course.replace(' ', '_')}_Exam_Cheatsheet.md",
                        mime="text/markdown"
                    )
                except Exception as e:
                    st.error(f"Error generating cheatsheet: {e}")

with tab_search:
    st.subheader("🧠 Semester-Wide Semantic Vector Search (Hybrid RAG)")
    search_query = st.text_input("Enter Semantic Concept, Equation or Question", placeholder="e.g. Find all proofs where Jensen's inequality or complementary slackness was used")
    c_filter = st.selectbox("Filter by Course (Optional)", ["All Courses"] + (query_courses() or []))
    
    if st.button("Search Knowledge Base", type="primary", disabled=not search_query):
        course_arg = None if c_filter == "All Courses" else c_filter
        with st.spinner("Searching ChromaDB vector store..."):
            results = semantic_search_notes(search_query, n_results=5, course_filter=course_arg)
            if not results:
                st.info("No matching semantic chunks found in vector database.")
            else:
                for idx, r in enumerate(results):
                    with st.expander(f"📌 [{r['course']}] {r['topic']} ({r['date']}) - {r['section']}", expanded=(idx==0)):
                        st.markdown(r["content"])

with tab_anki:
    st.subheader("📇 Interactive Flashcard Flip Reviewer & Anki Exporter")
    available_courses = query_courses() or get_available_courses()
    
    if not available_courses:
        st.info("No courses available.")
    else:
        sel_course = st.selectbox("Select Course", available_courses, key="anki_sel")
        
        # Collect all flashcards for this course
        course_cards = []
        lectures_dir = Path("./lectures")
        for file_path in sorted(lectures_dir.glob("*.md")):
            if file_path.name.endswith("_MOC.md"):
                continue
            try:
                post = frontmatter.load(file_path)
                c_name = str(post.get("course", "")).replace("[[", "").replace("]]", "").strip()
                if c_name.lower() == sel_course.lower():
                    t_name = str(post.get("topic", "")).replace("[[", "").replace("]]", "").strip()
                    d_str = str(post.get("date", ""))
                    pairs = parse_flashcards_from_markdown(post.content)
                    for q, a in pairs:
                        course_cards.append({"question": q, "answer": a, "topic": t_name, "date": d_str})
            except Exception:
                continue

        st.markdown(f"**Total Available Flashcards for {sel_course}:** `{len(course_cards)}`")
        
        if course_cards:
            st.divider()
            st.markdown("#### 🔄 In-Browser Card Reviewer")
            
            if "card_idx" not in st.session_state:
                st.session_state.card_idx = 0
            if "show_answer" not in st.session_state:
                st.session_state.show_answer = False

            # Ensure index within bounds
            if st.session_state.card_idx >= len(course_cards):
                st.session_state.card_idx = 0

            cur_card = course_cards[st.session_state.card_idx]

            # Render Question Box
            st.markdown(
                f"""
                <div style="background-color: #1e1e2e; border: 2px solid #89b4fa; border-radius: 12px; padding: 25px; margin-bottom: 15px;">
                    <div style="color: #89b4fa; font-size: 13px; text-transform: uppercase; font-weight: 600;">
                        Card {st.session_state.card_idx + 1} of {len(course_cards)} &nbsp;•&nbsp; 🏷️ {cur_card['topic']} ({cur_card['date']})
                    </div>
                    <div style="color: #f5e0dc; font-size: 20px; font-weight: 600; margin-top: 10px;">
                        {cur_card['question']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            col_flip, col_next, col_prev = st.columns([2, 1, 1])
            with col_flip:
                if st.button("💡 " + ("Hide Answer" if st.session_state.show_answer else "Flip Card (Reveal Answer)"), type="primary"):
                    st.session_state.show_answer = not st.session_state.show_answer
                    st.rerun()
            with col_prev:
                if st.button("⬅️ Previous"):
                    st.session_state.card_idx = max(0, st.session_state.card_idx - 1)
                    st.session_state.show_answer = False
                    st.rerun()
            with col_next:
                if st.button("Next ➡️"):
                    st.session_state.card_idx = (st.session_state.card_idx + 1) % len(course_cards)
                    st.session_state.show_answer = False
                    st.rerun()

            if st.session_state.show_answer:
                st.markdown(
                    f"""
                    <div style="background-color: #181825; border: 2px solid #a6e3a1; border-radius: 12px; padding: 25px; margin-top: 15px;">
                        <div style="color: #a6e3a1; font-size: 14px; font-weight: bold; margin-bottom: 8px;">💡 Answer & Derivation:</div>
                        <div style="color: #cdd6f4; font-size: 17px; line-height: 1.6;">
                            {cur_card['answer']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            st.divider()
            st.markdown("#### ⬇️ Export to Anki Mobile / Desktop")
            if st.button("Generate Complete Course Anki Deck (.apkg)"):
                with st.spinner(f"Compiling flashcards for {sel_course}..."):
                    deck_path = generate_anki_deck_for_course(Path("./lectures"), sel_course)
                    if deck_path and deck_path.exists():
                        with open(deck_path, "rb") as f:
                            st.download_button(
                                label=f"⬇️ Download {sel_course} Anki Deck (.apkg)",
                                data=f,
                                file_name=deck_path.name,
                                mime="application/octet-stream"
                            )

with tab_history:
    st.subheader("💬 Study Chat History & Mobile Telegram Sessions")
    st.markdown("All questions, answers, and theorem derivations from your **Telegram Mobile Bot** and Web sessions are archived here on persistent disk.")

    c_search, c_filter = st.columns([3, 1])
    with c_search:
        search_kw = st.text_input("🔍 Search Past Chats & Derivations", placeholder="e.g. Bayes, Backprop, KKT, Gradient")
    
    all_chats = get_all_saved_chats(search_query=search_kw, limit=100)
    
    if not all_chats:
        st.info("No conversations found matching your search. Start asking questions in Telegram or Web!")
    else:
        # Group chats by session_id
        sessions = {}
        for c in all_chats:
            s_id = c.get("session_id", "Default Session") or "Default Session"
            if s_id not in sessions:
                sessions[s_id] = []
            sessions[s_id].append(c)

        st.markdown(f"**Total Archived Interactions:** `{len(all_chats)}` across `{len(sessions)}` study threads")
        st.divider()

        for s_id, msgs in sessions.items():
            first_user_q = next((m["content"] for m in msgs if m["role"] == "user"), "Study Session")
            exp_label = f"📁 Thread: {first_user_q[:60]}... (`{s_id}` - {len(msgs)} messages)"
            
            with st.expander(exp_label, expanded=True):
                for m in msgs:
                    role = m["role"]
                    ts = m.get("timestamp", "")
                    if role == "user":
                        with st.chat_message("user"):
                            st.markdown(f"**🧑 You** `[{ts}]`")
                            st.markdown(m["content"])
                    else:
                        with st.chat_message("assistant"):
                            st.markdown(f"**🎓 Comprehensive Academic Derivation** `[{ts}]`")
                            st.markdown(m["content"])
