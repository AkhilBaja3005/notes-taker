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

- **Multi-Format Ingestion**: Supports `.m4a`, `.mp3`, `.wav`, `.aac`, `.ogg`, `.flac`, `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.txt`, `.md`.
- **Obsidian Native Integration**: Automatically attaches YAML frontmatter, `[[Wikilinks]]`, `#course/...` and `#topic/...` tags, and `> [!WARNING]` callouts.
- **Automated Git Sync Engine**: Commits and pushes notes to your remote GitHub vault automatically.
- **Streamlit Web Dashboard**:
  - Live Gemini Flash model selector.
  - Multi-subject daily briefings.
  - Date-filtered syllabus exam doubt solver & mock exam generator.
- **Asynchronous Telegram Bot**:
  - Send audio/PDFs on-the-go.
  - Interactive `/menu` button interface.
  - High-res LaTeX math image rendering via `/latex`.
  - Smart paragraph chunking & full `.md` file attachments.
- **Fault-Tolerant AI Engine**: Automatic multi-model fallback chain across `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-flash-latest`, and `gemini-3.1-flash-lite`.

---

## 📁 Repository Structure

```text
.
├── .env.example               # Environment variables configuration template
├── .gitignore                 # Standard Python, Obsidian, and IDE ignore rules
├── Dockerfile                 # Container image specification
├── LICENSE                    # MIT License
├── README.md                  # Project documentation
├── app.py                     # Streamlit web dashboard
├── bot.py                     # Telegram bot service
├── core_engine.py             # Shared reasoning, date filtering, and LaTeX repair
├── docker-compose.yml         # Container orchestration configuration
├── git_sync.py                # Automated Git synchronization engine
├── incoming_audio/            # Watched folder for recordings/documents
├── ingest_audio.py            # Universal audio and document ingestion pipeline
├── lectures/                  # Generated structured Markdown study notes
├── main.py                    # Unified multi-service launcher
├── requirements.txt           # Pinned project dependencies
└── watcher.py                 # File system watcher daemon
```

---

## 🛠️ Quick Start

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
GEMINI_MODEL=gemini-3.6-flash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_TELEGRAM_USER_IDS=
WATCH_DIR=./incoming_audio
LECTURES_DIR=./lectures

# Obsidian Git Sync Configuration
ENABLE_GIT_SYNC=true
GIT_VAULT_REPO_URL=https://<GITHUB_PAT>@github.com/yourusername/my-obsidian-notes.git
GIT_BRANCH=main
```

### 3. Launch All Services

```bash
python main.py
```

---

## 🐳 Docker Deployment

To run the entire assistant suite in Docker:

```bash
docker-compose up -d --build
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
