import sys
import subprocess
import signal
import time
import datetime
import os
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dotenv import load_dotenv
from git_sync import sync_notes_to_git
from metadata_db import index_all_lectures
from vector_store import index_all_lectures_vector_db
from obsidian_moc import update_all_course_mocs

load_dotenv()

# Process registry for self-healing supervisor: {name: (process_obj, command_list)}
process_registry = {}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ["/healthz", "/health", "/ping"]:
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            status_data = '{"status": "healthy", "timestamp": "%s"}' % time.strftime('%Y-%m-%dT%H:%M:%SZ')
            self.wfile.write(status_data.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress health check access log noise

def run_health_server(port: int = 8080):
    """Runs a lightweight internal health check server for container liveness probes."""
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        print(f"[!] Health server notice: {e}")

def self_ping_keepalive(interval_seconds: int = 300):
    """
    Self-ping keepalive daemon:
    Periodically sends lightweight HTTP GET requests to Hugging Face Spaces
    to ensure the instance stays awake and never idles out.
    """
    time.sleep(30)  # Initial grace period on boot
    
    # Target public URL or direct internal port
    target_url = os.environ.get("SPACE_HOST")
    if target_url:
        target_url = f"https://{target_url}/"
    else:
        target_url = f"http://127.0.0.1:{os.environ.get('STREAMLIT_SERVER_PORT', '7860')}/"

    print(f"[*] Self-ping Keepalive Daemon active. Monitoring: {target_url} (every {interval_seconds}s)")
    while True:
        try:
            req = urllib.request.Request(
                target_url,
                headers={"User-Agent": "Academic-Assistant-Keepalive/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                pass
        except Exception:
            pass  # Normal during cold boots
        time.sleep(interval_seconds)

def setup_persistent_hf_storage():
    """
    If running in Hugging Face with a Storage Bucket mounted at /data:
    Configures /data/lectures, /data/vector_db, and /data/incoming_audio as the primary storage paths
    so all notes, databases, and decks are written directly into the persistent storage bucket.
    """
    data_mount = Path("/data")
    if data_mount.exists() and os.access(data_mount, os.W_OK):
        print("[+] Hugging Face Persistent Storage Bucket detected at /data!")
        (data_mount / "lectures").mkdir(parents=True, exist_ok=True)
        (data_mount / "vector_db").mkdir(parents=True, exist_ok=True)
        (data_mount / "incoming_audio").mkdir(parents=True, exist_ok=True)

        os.environ["LECTURES_DIR"] = str(data_mount / "lectures")
        os.environ["WATCH_DIR"] = str(data_mount / "incoming_audio")
        print(f"[+] Active storage redirected directly to Persistent Bucket: {data_mount}")

def signal_handler(sig, frame):
    print("\n[!] Shutting down all services...")
    for name, (p, _) in list(process_registry.items()):
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
    sys.exit(0)

def startup_vault_hydration():
    """Hydrates notes from remote repo, compiles MOCs, and re-indexes SQLite/ChromaDB."""
    setup_persistent_hf_storage()
    
    lectures_dir = Path(os.environ.get("LECTURES_DIR", "./lectures"))
    lectures_dir.mkdir(parents=True, exist_ok=True)
    
    # If /data is mounted and empty, copy any existing local notes over
    local_sample_dir = Path("./lectures")
    if str(lectures_dir) != str(local_sample_dir) and local_sample_dir.exists():
        for f in local_sample_dir.glob("*.md"):
            dest = lectures_dir / f.name
            if not dest.exists():
                try:
                    dest.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception:
                    pass

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
        print(f"[+] Vault hydration and indexing complete on: {lectures_dir}")
    except Exception as e:
        print(f"[!] Indexing notice: {e}")

def cleanup_old_temp_files(hours_threshold: int = 48):
    """Purges raw temporary audio files older than hours_threshold."""
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

def send_startup_deployment_notification():
    """Sends a Telegram notification to the owner whenever a new deployment boots up (runs in background with retries)."""
    time.sleep(12)  # Allow container network & DNS to warm up
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    allowed_ids = [uid.strip() for uid in os.environ.get("ALLOWED_TELEGRAM_USER_IDS", "").split(",") if uid.strip().isdigit()]
    
    # Fallback to known owner ID if ALLOWED_TELEGRAM_USER_IDS is empty
    target_users = allowed_ids if allowed_ids else ["8327334588"]

    if not token or not target_users:
        return

    import httpx
    boot_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg_text = (
        f"🚀 *New Deployment Detected & Online!*\n\n"
        f"• **Status**: `All Services Operational`\n"
        f"• **Boot Time**: `{boot_time}`\n"
        f"• **Active Engine**: `{os.environ.get('GEMINI_MODEL', 'gemini-3.6-flash')}`\n"
        f"• **Storage**: `Persistent /data Bucket Active`\n"
        f"• **Dashboard**: [abaja-notes-taker.hf.space](https://abaja-notes-taker.hf.space)\n\n"
        f"💬 Send `/menu` or ask any question to begin!"
    )

    proxy_base_url = os.environ.get("TELEGRAM_API_BASE_URL", "").strip().rstrip("/")
    api_root = proxy_base_url if proxy_base_url else "https://api.telegram.org"

    client = httpx.Client(timeout=30.0)
    for uid in target_users:
        for attempt in range(1, 4):
            try:
                url = f"{api_root}/bot{token}/sendMessage"
                resp = client.post(
                    url,
                    json={
                        "chat_id": uid,
                        "text": msg_text,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True
                    }
                )
                if resp.status_code == 200:
                    print(f"[+] Startup deployment notification sent to Telegram user {uid}!")
                    break
                else:
                    print(f"[!] Notification response status {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[!] Deployment notification attempt {attempt} for {uid}: {e}")
                time.sleep(5)
    client.close()

def start_service(name: str, cmd: list) -> subprocess.Popen:
    """Spawns a managed process with explicit environment inheritance and registers it for self-healing supervision."""
    env_vars = os.environ.copy()
    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, env=env_vars)
    process_registry[name] = (proc, cmd)
    return proc

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    python_executable = sys.executable

    print("=" * 60)
    print("🎓 Starting Autonomous Academic Lecture Assistant Services")
    print("=" * 60)

    # 1. Startup Vault Hydration & Cleanup
    startup_vault_hydration()
    cleanup_old_temp_files()

    # 2. Launch Health Check & Keepalive Daemons in background threads
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=self_ping_keepalive, daemon=True).start()

    # 3. Start Watcher Daemon
    print("[*] Launching Watcher Daemon (watcher.py)...")
    start_service("Watcher", [python_executable, "-u", "watcher.py"])

    # 4. Start Telegram Bot (if configured)
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("[*] Launching Telegram Bot (bot.py)...")
        start_service("TelegramBot", [python_executable, "-u", "bot.py"])
    else:
        print("[!] TELEGRAM_BOT_TOKEN not configured - running Web UI & Watcher only.")

    # 5. Start Streamlit App (Port 7860 on HF Spaces / 8501 local)
    port = os.environ.get("STREAMLIT_SERVER_PORT", "8501")
    print(f"[*] Launching Streamlit Web App on port {port}...")
    start_service("Streamlit", [
        python_executable, "-u", "-m", "streamlit", "run", "app.py",
        "--server.port", str(port),
        "--server.address", "0.0.0.0",
        "--server.headless", "true"
    ])

    # 6. Send Proactive Telegram Deployment Notification (in background thread with retries)
    threading.Thread(target=send_startup_deployment_notification, daemon=True).start()

    print("\n[+] All services started successfully with Self-Healing Supervisor active!")
    print("[+] Press Ctrl+C at any time to gracefully terminate all services.\n")

    # 6. Self-Healing Process Supervisor Loop
    last_cleanup = time.time()
    try:
        while True:
            for name, (proc, cmd) in list(process_registry.items()):
                exit_code = proc.poll()
                if exit_code is not None:
                    print(f"[!] Warning: Service '{name}' (PID {proc.pid}) exited with code {exit_code}. Auto-restarting in 3s...")
                    time.sleep(3)
                    new_proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, env=os.environ.copy())
                    process_registry[name] = (new_proc, cmd)
                    print(f"[+] Service '{name}' successfully restarted with new PID {new_proc.pid}!")

            # Periodic cleanup every 12 hours
            if time.time() - last_cleanup > 43200:
                cleanup_old_temp_files()
                last_cleanup = time.time()

            time.sleep(2)
    except KeyboardInterrupt:
        signal_handler(None, None)
    except Exception as e:
        print(f"[!] Critical main supervisor error: {e}")
        import traceback
        traceback.print_exc()
        signal_handler(None, None)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[!] Fatal entrypoint error: {e}")
        import traceback
        traceback.print_exc()
