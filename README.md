---
title: Academic Notes Assistant
emoji: 🎓
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

<div align="center">

# 🎓 Autonomous Academic Lecture & Notes Assistant
**Production-ready, local-first & cloud-deployable AI study copilot for graduate-level STEM coursework.**

[![Python](https://img.shields.io/badge/Python-3.11%2B%20%7C%203.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20GenAI-Gemini%20Flash-orange?logo=google&logoColor=white)](https://ai.google.dev/)
[![Streamlit](https://img.shields.io/badge/Web%20UI-Streamlit-red?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Telegram](https://img.shields.io/badge/Chat%20Bot-Telegram-blue?logo=telegram&logoColor=white)](https://telegram.org/)
[![Obsidian](https://img.shields.io/badge/Vault-Obsidian%20Sync-purple?logo=obsidian&logoColor=white)](https://obsidian.md/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## 📌 Overview

The **Autonomous Academic Lecture Assistant** automates the entire lifecycle of lecture ingestion, transcription, structured academic synthesis, LaTeX mathematical derivation, exam preparation, and cross-device synchronization:

```text
               ┌──────────────────────────────────────────────┐
               │    Audio Recording / PDF / Slides / Word     │
               └──────────────────────┬───────────────────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ 📁 ./incoming_audio │    │ 🤖 Telegram Bot     │    │ 💻 Streamlit Web UI │
│ (Watcher Daemon)    │    │ (@note_taker_bot)   │    │ (Direct Upload)     │
└──────────┬──────────┘    └──────────┬──────────┘    └──────────┬──────────┘
           │                          │                          │
           └──────────────────────────┼──────────────────────────┘
                                      ▼
                      ┌──────────────────────────────┐
                      │    Gemini Flash Engine       │
                      │ (Auto-fallback Architecture) │
                      └──────────────┬───────────────┘
                                     │ Generates structured Markdown & LaTeX
                                     ▼
                      ┌──────────────────────────────┐
                      │   📚 Obsidian Vault Vault    │
                      │      (./lectures/*.md)       │
                      └──────────────┬───────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
┌─────────────────────────────┐             ┌─────────────────────────────────────┐
│    Obsidian on Your Mac     │             │        GitHub Vault Repository      │
│  (Auto-sync via Git Engine) │             │  (my-obsidian-notes.git)            │
└─────────────────────────────┘             └─────────────────────────────────────┘
```

---

## ✨ Key Features

- **Multi-Format Ingestion**: Supports `.m4a`, `.mp3`, `.wav`, `.aac`, `.ogg`, `.flac`, `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.txt`, `.md`, and **Live Browser Mic**.
- **Tiered Model Routing**: Routes audio and dense math proofs to `gemini-3.6-flash` and typed slides/docs to ultra-fast `gemini-3.1-flash-lite`.
- **Obsidian Native Integration**: Automatically attaches YAML frontmatter, `[[Wikilinks]]`, `#course/...` tags, and `> [!WARNING]` callouts.
- **Obsidian Maps of Content (MOC)**: Auto-compiles chronological syllabus tables, master theorem indexes, and exam pitfalls.
- **Anki Flashcard Deck Exporter**: Auto-compiles native `.apkg` flashcard decks for spaced repetition.
- **Semester-Wide ChromaDB Vector Search**: Semantic RAG queries across all past course notes and proofs.
- **Automated Git Sync Engine**: Commits and pushes notes to your remote GitHub vault automatically.
- **Streamlit Web Dashboard**:
  - Live in-browser microphone recording.
  - Multi-subject daily briefings.
  - Date-filtered syllabus exam tutor & semester semantic search.
- **Asynchronous Telegram Bot**:
  - Send audio/PDFs on-the-go.
  - Interactive `/menu` button interface.
  - Export Anki decks directly to mobile via `/anki`.
  - Semantic vector search via `/search`.
  - High-res LaTeX math image rendering via `/latex`.

---

## 📁 Repository Structure

```text
.
├── .github/workflows/         # CI/CD auto-sync workflow for Hugging Face Spaces
├── .env.example               # Environment variables configuration template
├── .gitignore                 # Standard Python, Obsidian, and IDE ignore rules
├── Dockerfile                 # Container image specification (UID 1000, Port 7860)
├── LICENSE                    # MIT License
├── README.md                  # Project documentation with HF Spaces metadata
├── anki_exporter.py           # Anki .apkg deck generation engine
├── app.py                     # Streamlit web dashboard with mic & password gate
├── audio_optimizer.py         # 32kbps mono AAC audio compressor
├── bot.py                     # Telegram bot service
├── core_engine.py             # Shared reasoning, date filtering, and LaTeX repair
├── docker-compose.yml         # Container orchestration configuration
├── git_sync.py                # Automated Git synchronization engine
├── incoming_audio/            # Watched folder for recordings/documents
├── ingest_audio.py            # Universal audio and document ingestion pipeline
├── lectures/                  # Generated structured Markdown study notes
├── main.py                    # Unified launcher with startup vault hydration & GC
├── metadata_db.py             # Offline SQLite metadata database
├── requirements.txt           # Pinned project dependencies
├── vector_store.py            # ChromaDB vector store & semantic search
└── watcher.py                 # File system watcher daemon
```

---

## 🛠️ Quick Start (Local Setup)

### 1. Clone & Setup Virtual Environment

```bash
git clone https://github.com/AkhilBaja3005/notes-taker.git
cd notes-taker

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure `.env`

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
GEMINI_API_KEY=your_gemini_api_key_here
AUDIO_MODEL=gemini-3.6-flash
DOC_MODEL=gemini-3.1-flash-lite
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_TELEGRAM_USER_IDS=
WATCH_DIR=./incoming_audio
LECTURES_DIR=./lectures

# Obsidian Git Sync Configuration
ENABLE_GIT_SYNC=true
GIT_VAULT_REPO_URL=https://<GITHUB_PAT>@github.com/yourusername/my-obsidian-notes.git
GIT_BRANCH=main
STREAMLIT_PASSWORD=
```

### 3. Launch All Services

```bash
python main.py
```

---

## 🤗 Hugging Face Spaces Deployment

Space URL: **[https://huggingface.co/spaces/abaja/notes-taker](https://huggingface.co/spaces/abaja/notes-taker)**

In your Hugging Face Space settings, add the following secrets:
- `GEMINI_API_KEY`: Your Gemini API Key
- `TELEGRAM_BOT_TOKEN`: `8477573311:AAEi1AHDpwd57me52c3r9yB3MWKDKTCIWOo`
- `GIT_VAULT_REPO_URL`: `https://<GITHUB_PAT>@github.com/AkhilBaja3005/my-obsidian-notes.git`
- `ENABLE_GIT_SYNC`: `true`
- `STREAMLIT_PASSWORD`: (Optional password gate)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
