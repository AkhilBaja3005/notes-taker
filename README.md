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
[![Google Gemini](https://img.shields.io/badge/Google%20GenAI-Gemini%203.7%20Flash-orange?logo=google&logoColor=white)](https://ai.google.dev/)
[![React](https://img.shields.io/badge/Web%20UI-React%20SPA%20%2B%20Vite-blue?logo=react&logoColor=white)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-emerald?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Telegram](https://img.shields.io/badge/Chat%20Bot-Telegram-blue?logo=telegram&logoColor=white)](https://telegram.org/)
[![Obsidian](https://img.shields.io/badge/Vault-Obsidian%20Sync-purple?logo=obsidian&logoColor=white)](https://obsidian.md/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## 📌 System Architecture & Data Flow

The **Autonomous Academic Lecture Assistant** provides an end-to-end multi-cloud pipeline that automates lecture ingestion, SOTA AI synthesis, KaTeX mathematical derivation, 3D Anki flashcards, vector search, and bidirectional Obsidian vault synchronization:

```text
                                  📱 USER TOUCHPOINTS
                ┌───────────────────────────┴───────────────────────────┐
                ▼                                                       ▼
      [ Telegram App Mobile ]                                  [ React + Vite SPA Web Hub ]
     (@abaja_note_taker_bot)                                   (abaja-notes-taker.hf.space)
                │                                                       │
                │ 1. Voice Note / PDF / /recap                          │ 2. Direct Ingestion / Chat
                ▼                                                       ▼
   ┌───────────────────────────────┐                       ┌───────────────────────────────┐
   │ ⚡ RENDER STREAMING PROXY     │                       │ 🐳 HUGGING FACE CENTRAL HUB   │
   │ (proxy_server.py on port 10k) │───[ Binary Stream ]──▶│ (main.py + server:app on 7860)│
   └───────────────────────────────┘                       └───────────────┬───────────────┘
                                                                           │
                                              ┌────────────────────────────┼────────────────────────────┐
                                              ▼                            ▼                            ▼
                                  ┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
                                  │ 🧠 SOTA Gemini 3.7    │   │ 🗄️ SQLite Database    │   │ 🧠 ChromaDB Vector DB │
                                  │ Flash Ingestion Engine│   │ (metadata.db @ /data) │   │ (Semantic RAG Search) │
                                  └───────────┬───────────┘   └───────────────────────┘   └───────────────────────┘
                                              │
                                              ▼
                                  ┌───────────────────────┐
                                  │ 📚 Obsidian Markdown  │
                                  │ (LaTeX + Mermaid MOC) │
                                  └───────────┬───────────┘
                                              │
                                              ▼
                                  ┌───────────────────────┐
                                  │ 🐙 Obsidian Git Sync  │──▶ [ GitHub Repository: my-obsidian-notes ]
                                  │ (git_sync.py engine)  │
                                  └───────────────────────┘
```

---

## ✨ Key Features & Capabilities

- **🎙️ Multi-Format Ingestion**:
  - Ingests `.mp3`, `.m4a`, `.wav`, `.aac`, `.ogg`, `.flac`, `.pdf`, `.docx`, `.pptx`, `.txt`, and `.md`.
  - **In-Browser Audio Recording**: Features a live microphone recorder with audio playback, scrubbing, waveform inspection, and direct `.wav` download prior to AI processing.
- **🧠 SOTA Gemini 3.7 Flash Reasoning**:
  - Automatically structures messy recordings into rigorous Markdown with full KaTeX math derivations (`\begin{aligned} ... \end{aligned}`), Mermaid DAG mind maps, and `> [!WARNING]` professor exam pitfall callouts.
  - Multi-tier automatic fallback across active Flash models (`gemini-3.7-flash` $\rightarrow$ `gemini-3.6-flash` $\rightarrow$ `gemini-3.5-flash` $\rightarrow$ `gemini-3.1-flash-lite`).
- **📅 Academic Intelligence Briefing**:
  - **3-Way Scope Switch**:
    - 📅 **By Date**: Daily multi-subject executive summaries connecting themes across all classes.
    - 📚 **By Course**: Semester-wide progression milestones and governing formula tables.
    - 🎯 **By Topic**: Exhaustive topic deep dives with failure modes and 5-question active recall tests.
  - **🌙 Automated Evening Telegram Push**: Background scheduler daemon pushes daily study briefings to your Telegram bot at your customized local time (synced across browser timezones).
- **📇 3D Interactive Flashcards & Anki Deck Compiler**:
  - Review conceptual check questions with smooth 3D flip card animations in the browser.
  - Export native `.apkg` decks on-demand via the web hub or via `/anki <Course>` on Telegram.
- **💬 Exam Tutor & Chat with Chronological History**:
  - Multi-turn conversational study copilot with date-range filters and full context grounding.
  - Past sessions grouped by thread with search and resume capability.
- **⚡ Full-Duplex Render Streaming Proxy**:
  - Render acts as an unrestricted 24/7 binary streaming gateway (`proxy_server.py`), streaming Telegram updates and large files to Hugging Face with zero disk footprint.
- **🔒 API Key Protection (`INGEST_API_KEY`)**:
  - Smart origin detection allows friction-free web uploads while securing programmatic `curl` and Python API calls with `X-API-Key`.

---

## 📁 Repository Structure

```text
.
├── .github/workflows/
│   └── deploy-render.yml      # Automated Render deployment webhook on git push
├── frontend/                  # React 18 + Vite + Tailwind CSS + Lucide Web SPA
│   ├── src/
│   │   ├── App.tsx            # Main Web Hub SPA (Ingestion, Chat, Search, Anki, Briefing)
│   │   └── main.tsx           # React entrypoint
│   └── package.json           # Frontend dependencies & build scripts
├── anki_exporter.py           # Native Anki .apkg flashcard deck compiler
├── audio_optimizer.py         # 32kbps mono AAC audio compressor
├── bot.py                     # Telegram Bot poller with Markdown & LaTeX rendering
├── cheatsheet_generator.py    # Master formula reference sheet generator
├── core_engine.py             # Multi-scope briefings, syllabus RAG & Gemini 3.7 router
├── git_sync.py                # Obsidian GitHub repository auto-sync engine
├── ingest_audio.py            # Universal multi-modal audio & document ingestion pipeline
├── main.py                    # Process supervisor, keepalive daemon & evening scheduler
├── metadata_db.py             # SQLite WAL-mode metadata, chat history & settings store
├── proxy_server.py            # High-performance FastAPI Telegram streaming proxy (Render)
├── render.yaml                # Infrastructure-as-code specification for Render
├── server.py                  # High-performance FastAPI REST API & static file hub
├── vector_store.py            # ChromaDB vector database & semantic similarity search
├── requirements.txt           # Pinned Python dependencies
└── Dockerfile                 # Hugging Face Spaces production Docker container
```

---

## 📱 iOS Shortcuts & Mobile Ecosystem (Voice Memos + Outlook)

The system includes native integration with **Apple Voice Memos** and **iOS Shortcuts** for zero-friction mobile capture:

1. **🎙️ Background Voice Memo Ingestion**:
   - Record in Apple's native **Voice Memos** app with your phone screen locked or in your pocket for 2+ hours.
   - Run the shortcut when class ends $\rightarrow$ reads your **Outlook / School Calendar** to auto-detect the current course name $\rightarrow$ uploads to `/api/upload` in **< 1 second**!
2. **📄 Share Sheet Ingest**:
   - Tap the iOS **Share (📤)** button on any PDF or slide deck in **Files**, **Safari**, or **Canvas** to ingest directly.
3. **🐙 Obsidian Auto-Pull on PC / Mac**:
   - Uses the **`Obsidian Git`** community plugin set to auto-pull every 2 minutes for zero-command bidirectional sync between iPhone $\leftrightarrow$ Cloud Hub $\leftrightarrow$ Desktop Vault.

---

## 🛠️ Direct API Ingestion Usage

You can upload lecture files directly to your cloud hub via `cURL`, Python, or iOS Shortcuts:

```bash
curl -X POST "https://abaja-notes-taker.hf.space/api/upload" \
  -H "X-API-Key: acad_UXLwTKdM3IaDGCeHYiu7dA5nuduOrpWdEsNQnwDXIp4" \
  -F "file=@/path/to/lecture.m4a" \
  -F "course_name=Machine Learning" \
  -F "topic_name=Backpropagation" \
  -F "lecture_date=2026-08-19" \
  -F "model=gemini-3.7-flash" \
  -F "is_dense_math=true"
```

---

## 🤖 Telegram Bot Commands (`@abaja_note_taker_bot`)

| Command | Description |
| :--- | :--- |
| **`/start`** | Welcome directory and system capabilities overview. |
| **`/menu`** | Interactive control panel with quick action buttons. |
| **`/help`** | Complete command syntax reference guide. |
| **`/recap`** | Generate today's multi-subject briefing (or `/recap <Course>` / `/recap <Topic>`). |
| **`/cheatsheet <Course>`** | Synthesize 1-page master formula reference sheet. |
| **`/anki <Course>`** | Compile and download spaced repetition `.apkg` flashcard deck. |
| **`/search <Query>`** | Semester-wide semantic vector search across all notes. |
| **`/latex <Equation>`** | Render mathematical formulas as crisp high-resolution dark-mode images. |
| **`/status`** | System health, indexed courses, active model, and Obsidian sync state. |

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

