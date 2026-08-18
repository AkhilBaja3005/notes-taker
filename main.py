import sys
import subprocess
import signal
import time
import os
from pathlib import Path
from git_sync import sync_notes_to_git
from metadata_db import index_all_lectures
from vector_store import index_all_lectures_vector_db
from obsidian_moc import update_all_course_mocs

processes = []

def signal_handler(sig, frame):
    print("\n[!] Shutting down all services...")
    for p in processes:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
    sys.exit(0)

def startup_vault_hydration():
    """
    On container startup (e.g. Hugging Face Spaces cold boot):
    1. Pulls latest notes from my-obsidian-notes git repository.
    2. Builds/updates all Obsidian Maps of Content (MOCs).
    3. Re-indexes notes in local SQLite metadata DB and ChromaDB vector store.
    """
    lectures_dir = Path("./lectures")
    lectures_dir.mkdir(parents=True, exist_ok=True)
    
    repo_url = os.environ.get("GIT_VAULT_REPO_URL")
    if repo_url:
        print("[*] Hydrating notes from Obsidian remote repository...")
        try:
            sync_notes_to_git("Initial container sync")
            print("[+] Successfully synced remote notes to container.")
        except Exception as e:
            print(f"[!] Initial Git sync notice: {e}")

    try:
        print("[*] Updating Obsidian MOCs and local indices...")
        update_all_course_mocs(lectures_dir)
        index_all_lectures(lectures_dir)
        index_all_lectures_vector_db(lectures_dir)
        print("[+] Vault hydration and indexing complete!")
    except Exception as e:
        print(f"[!] Indexing notice: {e}")

def cleanup_old_temp_files(hours_threshold: int = 48):
    """Garbage collector: cleans up raw temp audio older than hours_threshold."""
    now = time.time()
    cutoff = now - (hours_threshold * 3600)
    cleaned = 0

    temp_dirs = [Path("./incoming_audio"), Path("./test_samples/optimized_audio"), Path("./optimized_audio")]
    for d in temp_dirs:
        if not d.exists():
            continue
        for f in d.glob("*"):
            if f.is_file() and not f.name.startswith("."):
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                        cleaned += 1
                except Exception:
                    pass
    if cleaned > 0:
        print(f"[+] Garbage Collector: Cleaned {cleaned} temporary files older than {hours_threshold}h.")

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    python_executable = sys.executable

    print("=" * 60)
    print("🎓 Starting Autonomous Academic Lecture Assistant Services")
    print("=" * 60)

    # 1. Startup Vault Hydration
    startup_vault_hydration()
    cleanup_old_temp_files()

    # 2. Start Watcher Daemon
    print("[*] Launching Watcher Daemon (watcher.py)...")
    watcher_proc = subprocess.Popen(
        [python_executable, "watcher.py"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    processes.append(watcher_proc)

    # 3. Start Telegram Bot (if token provided)
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("[*] Launching Telegram Bot (bot.py)...")
        bot_proc = subprocess.Popen(
            [python_executable, "bot.py"],
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        processes.append(bot_proc)
    else:
        print("[!] TELEGRAM_BOT_TOKEN not configured - running Web UI & Watcher only.")

    # 4. Start Streamlit App (Port 7860 on HF Spaces / 8501 local)
    port = os.environ.get("STREAMLIT_SERVER_PORT", "8501")
    print(f"[*] Launching Streamlit Web App on port {port}...")
    streamlit_proc = subprocess.Popen(
        [
            python_executable, "-m", "streamlit", "run", "app.py",
            "--server.port", str(port),
            "--server.address", "0.0.0.0",
            "--server.headless", "true"
        ],
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    processes.append(streamlit_proc)

    print("\n[+] All services started successfully!")
    print("[+] Press Ctrl+C at any time to gracefully terminate all services.\n")

    # Monitor running processes and periodically run cleanup
    last_cleanup = time.time()
    try:
        while True:
            for p in processes:
                exit_code = p.poll()
                if exit_code is not None:
                    print(f"[!] Process PID {p.pid} exited with code {exit_code}.")
            
            # Periodic cleanup every 12 hours
            if time.time() - last_cleanup > 43200:
                cleanup_old_temp_files()
                last_cleanup = time.time()

            time.sleep(2)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()
