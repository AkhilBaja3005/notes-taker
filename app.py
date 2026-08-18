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
from anki_exporter import generate_anki_deck_for_course, generate_anki_deck_from_file
from vector_store import semantic_search_notes
from metadata_db import query_courses

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
        "• **Typed PDFs & Slides**: `gemini-3.1-flash-lite` (350+ tokens/sec, low latency)"
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

tab_upload, tab_recap, tab_exam, tab_search, tab_anki = st.tabs([
    "📤 Ingestion & Live Mic", 
    "📅 Daily Recap", 
    "🎯 Exam Prep", 
    "🔍 Semester Search", 
    "📇 Anki Decks"
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
            with st.spinner("Processing live lecture recording..."):
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
                    st.success(f"✅ Notes successfully generated from live mic!")
                    st.markdown(out_path.read_text(encoding="utf-8"))
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()
    st.markdown("##### 📁 Option B: Upload Audio Recording or Academic Document")
    uploaded_file = st.file_uploader(
        "Select File",
        type=["m4a", "mp3", "wav", "aac", "ogg", "flac", "pdf", "docx", "doc", "txt", "md", "pptx", "ppt"]
    )

    if st.button("Process & Generate Structured Notes", type="primary", disabled=(uploaded_file is None or not up_course or not up_topic)):
        with st.spinner(f"Analyzing material with optimal Gemini tier..."):
            incoming_dir = Path("./incoming_audio")
            incoming_dir.mkdir(parents=True, exist_ok=True)
            save_path = incoming_dir / uploaded_file.name
            
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            try:
                out_path = process_file(
                    file_path_str=str(save_path),
                    course_name=up_course,
                    topic_name=up_topic,
                    lecture_date=up_date.isoformat(),
                    model=active_model,
                    is_dense_math=is_dense_math
                )
                st.success(f"✅ Notes successfully generated, synced to Obsidian, and indexed in Vector DB!")
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
                with st.spinner("Analyzing lecture syllabus..."):
                    try:
                        reply = query_exam_syllabus(course, start_date, end_date, user_prompt, model=active_model)
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    except Exception as e:
                        st.error(f"Error during query: {e}")

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
    st.subheader("📇 Spaced Repetition Anki Decks (.apkg)")
    available_courses = query_courses() or get_available_courses()
    
    if not available_courses:
        st.info("No courses available to generate Anki decks yet.")
    else:
        sel_course = st.selectbox("Select Course for Complete Deck", available_courses, key="anki_sel")
        if st.button("Generate Complete Course Anki Deck (.apkg)", type="primary"):
            with st.spinner(f"Compiling flashcards for {sel_course}..."):
                deck_path = generate_anki_deck_for_course(Path("./lectures"), sel_course)
                if deck_path and deck_path.exists():
                    st.success(f"✅ Anki deck `{deck_path.name}` generated!")
                    with open(deck_path, "rb") as f:
                        st.download_button(
                            label=f"⬇️ Download {sel_course} Anki Deck (.apkg)",
                            data=f,
                            file_name=deck_path.name,
                            mime="application/octet-stream"
                        )
                else:
                    st.warning("No flashcards found for this course.")
