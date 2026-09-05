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

- **🎙️ Multi-Format Ingestion & Smart AI Auto-Titling**:
  - Ingests `.mp3`, `.m4a`, `.wav`, `.aac`, `.ogg`, `.flac`, `.pdf`, `.docx`, `.pptx`, `.txt`, and `.md`.
  - **Zero-Typing Auto-Titling**: If you leave the topic name blank or generic in iOS Shortcuts, Gemini automatically extracts the precise 2-to-6 word academic title (e.g. *Lagrangian Duality & KKT*, *Singular Value Decomposition*) from the lecture subject.
  - **In-Browser Audio Recording**: Features a live microphone recorder with audio playback, scrubbing, waveform inspection, and direct `.wav` download prior to AI processing.
- **🧠 SOTA Gemini 3.8 / 3.7 Flash Reasoning**:
  - Automatically structures messy recordings into rigorous Markdown with full KaTeX math derivations (`\begin{aligned} ... \end{aligned}`), Mermaid DAG mind maps, and `> [!WARNING]` professor exam pitfall callouts.
  - Multi-tier automatic fallback across active Flash models (`gemini-3.8-flash` $\rightarrow$ `gemini-3.7-flash` $\rightarrow$ `gemini-3.6-flash` $\rightarrow$ `gemini-3.5-flash` $\rightarrow$ `gemini-3.1-flash-lite`).
- **🌐 Real-Time Google Search Grounding with Verified Citations**:
  - Connects the assistant to live web knowledge for real-time external questions and new domain topics.
  - Returns clickable citations (`[Title](url)`) linking to source papers and reference websites.
  - Built-in quota fail-safe automatically pivots to Gemini's comprehensive internal knowledge base if free-tier search limits are encountered.
- **🔍 Hybrid Vector + SQLite FTS5 Full-Text Search**:
  - Combines ChromaDB dense vector embeddings (conceptual similarity) with SQLite FTS5 BM25 keyword matching (exact formulas, acronyms like `"KKT"`, `"SVD"`, `"ADMM"`, and theorems) via **Reciprocal Rank Fusion (RRF)**.
  - Visual badges in the Web Hub highlight whether a match was found via `⚡ Exact Match (FTS5)` or `🧠 Semantic Vector`.
- **📅 Academic Intelligence Briefing**:
  - **3-Way Scope Switch**:
    - 📅 **By Date**: Daily multi-subject executive summaries connecting themes across all classes.
    - 📚 **By Course**: Semester-wide progression milestones and governing formula tables.
    - 🎯 **By Topic**: Exhaustive topic deep dives with failure modes and 5-question active recall tests.
  - **🌙 Automated Evening Telegram Push**: Background scheduler daemon pushes daily study briefings to your Telegram bot at your customized local time (synced across browser timezones).
- **📋 Master Cheatsheet & 1-Click Printable PDF Export**:
  - Synthesize 1-page formula reference sheets across any date range.
  - Browser-native **Print / PDF Export** button formats equations and summaries into a clean, ready-to-study PDF document.
- **📇 3D Interactive Flashcards & Anki Deck Compiler**:
  - Review conceptual check questions with smooth 3D flip card animations in the browser.
  - Export native `.apkg` decks on-demand via the web hub or via `/anki <Course>` on Telegram.
- **💬 Exam Tutor & Chat with Chronological History**:
  - Multi-turn conversational study copilot with date-range filters and full context grounding.
  - Past sessions grouped by thread with search and resume capability.
- **⏱️ High-Frequency External Keepalive Daemon**:
  - Pings the public HTTPS Space URL (`/healthz`, `/api/system_status`) every 60 seconds with realistic headers to generate active public traffic and permanently prevent Hugging Face from pausing.
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
  -F "model=gemini-3.8-flash" \
  -F "is_dense_math=true"
```

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

## 🛠️ Engineering Challenges & Production Solutions

Building an end-to-end multi-cloud academic pipeline across mobile, containers, and LLM reasoning uncovered several non-trivial engineering challenges:

### 📱 1. Mobile iOS Background Constraints
- **Challenge**: iOS Shortcuts suspends active background recording (`Record Audio`) when the device auto-locks.
  - **Solution**: Leveraged Apple's privileged **Voice Memos** app for background recording, decoupling recording from network upload via a 1-tap post-class shortcut.
- **Challenge**: FastAPI/Starlette threw `422 Unprocessable Entity` (Stream Consumed) when reading files and form fields sequentially.
  - **Solution**: Implemented single-pass stream parsing in [`server.py`](server.py) that scans all incoming form fields (`file`, `audio`, `document`, `data`), automatically decoding raw binary, multipart files, and Base64 payloads.
- **Challenge**: iOS localized narrow no-break space (`\u202f`) in recording timestamps crashed HTTP clients with `'ascii' codec` errors.
  - **Solution**: Added automatic ASCII sanitization in [`ingest_audio.py`](ingest_audio.py) and stripped illegal filesystem characters (`:`, `/`, `\`, `*`, `?`) from calendar event titles.

### ⚡ 2. Cloud ASGI & Latency
- **Challenge**: Legacy Streamlit WebSocket reconnect attempts (`ws://.../_stcore/stream`) caused unhandled `AssertionError` crashes in Starlette's `StaticFiles`.
  - **Solution**: Implemented a universal WebSocket catch-all `@app.websocket("/{full_path:path}")` in [`server.py`](server.py) to safely absorb and disconnect unmapped WebSocket probes.
- **Challenge**: Mobile shortcuts hung for 15+ seconds while waiting for transcription, Git sync, and Anki compilation.
  - **Solution**: Converted `/api/upload` into an **asynchronous background worker** (`asyncio.to_thread`) that returns `200 OK` in **< 1 second** and dispatches a Telegram push notification when ready.

### 🧠 3. Gemini 3.7 Flash Reasoning & Grounding
- **Challenge**: Temporary Google API `503 UNAVAILABLE: Model experiencing high demand` spikes.
  - **Solution**: Created a self-healing **Multi-Tier Fallback Pool** (`gemini-3.8-flash` $\rightarrow$ `gemini-3.7-flash` $\rightarrow$ `gemini-3.6-flash` $\rightarrow$ `gemini-3.5-flash` $\rightarrow$ `gemini-3.1-flash-lite`) with dynamic thinking tokens (4096).
- **Challenge**: LLM hallucinating theoretical notes on silent recordings or background noise.
  - **Solution**: Injected strict silence & noise grounding rules into the prompt to emit concise diagnostic alerts instead of fabricated lectures.
- **Challenge**: Malformed LaTeX syntax from LLMs (broken `\begin{aligned}` delimiters, unescaped slashes).
  - **Solution**: Built `clean_and_repair_latex()` in [`core_engine.py`](core_engine.py), a deterministic regex engine that guarantees 100% rendering in Obsidian MathJax and KaTeX.

### 🐙 4. Storage & Obsidian Git Sync
- **Challenge**: Ephemeral container root filesystems wiping ChromaDB embeddings on reboot.
  - **Solution**: Pointed ChromaDB directly to `/data/vector_db` (Hugging Face Persistent Storage Bucket mount).
- **Challenge**: Accidental database locks (`metadata.db`) or audio files leaking into the Obsidian Git vault.
  - **Solution**: Implemented automated vault-level `.gitignore` generation in [`git_sync.py`](git_sync.py) to isolate notes from runtime binaries.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

