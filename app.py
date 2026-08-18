# pyrefly: ignore [missing-import]
import streamlit as st
import datetime
from pathlib import Path
from core_engine import (
    get_available_courses,
    generate_daily_recap,
    query_exam_syllabus,
    SUPPORTED_MODELS,
    DEFAULT_MODEL
)
from ingest_audio import process_file

st.set_page_config(page_title="Academic Lecture & Notes Hub", page_icon="🎓", layout="wide")
st.title("🎓 Graduate Lecture, Notes & Exam Hub")

with st.sidebar:
    st.header("⚙️ Model Settings")
    default_idx = SUPPORTED_MODELS.index(DEFAULT_MODEL) if DEFAULT_MODEL in SUPPORTED_MODELS else 0
    selected_model = st.selectbox(
        "Active Gemini Model",
        SUPPORTED_MODELS,
        index=default_idx,
        help="Select the Gemini Flash model to use."
    )
    st.markdown("---")
    st.markdown("### 📂 Supported Ingestion Formats")
    st.markdown("- **Audio:** `.m4a`, `.mp3`, `.wav`, `.aac`, `.ogg`, `.flac`")
    st.markdown("- **Documents:** `.pdf`, `.docx`, `.doc`, `.txt`, `.md`, `.pptx`")

tab_upload, tab_recap, tab_exam = st.tabs(["📤 Upload Lecture / Document", "📅 Daily Recap", "🎯 Exam Prep & Doubts"])

with tab_upload:
    st.subheader("Direct File Ingestion (Audio, PDF, Slides & Docs)")
    c1, c2 = st.columns(2)
    with c1:
        up_course = st.text_input("Course Name", placeholder="e.g. Machine Learning")
    with c2:
        up_topic = st.text_input("Topic Name", placeholder="e.g. Convex Optimization & Duals")
    
    up_date = st.date_input("Lecture / Material Date", datetime.date.today())
    
    uploaded_file = st.file_uploader(
        "Upload Audio Recording or Academic Document",
        type=["m4a", "mp3", "wav", "aac", "ogg", "flac", "pdf", "docx", "doc", "txt", "md", "pptx", "ppt"]
    )

    if st.button("Process & Generate Structured Notes", type="primary", disabled=(uploaded_file is None or not up_course or not up_topic)):
        with st.spinner(f"Analyzing content with Gemini ({selected_model})..."):
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
                    model=selected_model
                )
                st.success(f"✅ Notes successfully generated and saved to `{out_path.name}`!")
                st.markdown(out_path.read_text(encoding="utf-8"))
            except Exception as e:
                st.error(f"Error processing file: {e}")

with tab_recap:
    st.subheader("Daily Multi-Subject Executive Summary")
    selected_date = st.date_input("Select Lecture Date for Recap", datetime.date.today())
    if st.button("Generate Daily Briefing", type="primary"):
        with st.spinner(f"Analyzing all lectures for {selected_date} using {selected_model}..."):
            recap_md = generate_daily_recap(selected_date, model=selected_model)
            st.markdown(recap_md)

with tab_exam:
    st.subheader("Date-Filtered Syllabus & Exam Tutor")
    courses = get_available_courses()
    
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
                with st.spinner(f"Analyzing lecture syllabus using {selected_model}..."):
                    reply = query_exam_syllabus(course, start_date, end_date, user_prompt, model=selected_model)
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
