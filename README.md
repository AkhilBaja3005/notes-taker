# Autonomous Academic Lecture & Notes Assistant

A production-ready, local-first / cloud-deployable academic assistant for graduate-level STEM coursework. It processes audio recordings, PDFs, Word docs, lecture slides, and notes via Google Gemini Flash models (`gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.0-flash`), generates structured Markdown notes with LaTeX math, and seamlessly syncs to **Obsidian on your Mac via Git**.

---

## 🔄 Cloud-to-Mac Obsidian Git Sync Architecture

```text
📱 Phone / Web UI ───► ☁️ Cloud Assistant Server
                               │ (Generates Notes)
                               ▼
                       📂 ./lectures Repo
                               │
                               ▼ 1. Auto `git add`, `commit` & `push`
                       🐙 Private GitHub Repo (e.g. `my-obsidian-notes`)
                               │
                               ▼ 2. Auto-pull / Sync
                       💻 Your Mac (Obsidian Vault)
```

---

## 🛠️ Step-by-Step Obsidian Git Sync Setup

### Step 1: Create a Private GitHub Repository
1. Go to GitHub and create a new **Private Repository** (e.g. `my-obsidian-vault`).

### Step 2: Configure on your Cloud Server
In your cloud deployment's `.env` file, enable Git sync:
```env
ENABLE_GIT_SYNC=true
GIT_VAULT_REPO_URL=https://<GITHUB_TOKEN>@github.com/yourusername/my-obsidian-vault.git
GIT_BRANCH=main
```
*(Every time a lecture or document is processed on the cloud, it automatically commits and pushes the new `.md` note to your private GitHub repo).*

### Step 3: Configure Obsidian on your Mac
1. Open Obsidian on your Mac.
2. Clone your private repo into your preferred Obsidian directory:
   ```bash
   git clone git@github.com:yourusername/my-obsidian-vault.git ~/Documents/ObsidianVault
   ```
3. Open `~/Documents/ObsidianVault` as a vault in Obsidian.
4. (Optional & Recommended) In Obsidian:
   - Go to **Settings $\rightarrow$ Community Plugins $\rightarrow$ Browse**.
   - Install and enable **"Obsidian Git"**.
   - Set **"Vault backup interval"** to `5` minutes (it will automatically pull latest notes from GitHub in the background).

---

## 📁 Directory Structure

```text
.
├── .env.example
├── .env
├── .gitignore
├── requirements.txt
├── README.md
├── main.py                    # Unified runner for all services
├── git_sync.py                # Automated Git synchronization engine for Obsidian
├── incoming_audio/            # Watched folder for audio/documents
├── lectures/                  # Structured markdown notes vault (Git synced)
├── watcher.py                 # Multi-format file system watcher daemon
├── ingest_audio.py            # Universal audio/doc ingestion engine
├── core_engine.py             # Shared parsing, recap, and Q&A engine
├── app.py                     # Streamlit web app
└── bot.py                     # Telegram bot service
```

---

## 💡 Usage

### Start All Services

```bash
python main.py
```

### Ingestion Methods
1. **Telegram Bot**: Send audio/PDF/docx to [@abaja_note_taker_bot](https://t.me/abaja_note_taker_bot).
2. **Streamlit Web UI**: Upload via the web dashboard.
3. **Watcher Daemon**: Drop files into `./incoming_audio`.
