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

    def do_POST(self):
        if self.path in ["/telegram_webhook", "/api/telegram_webhook"]:
            import json
            import asyncio
            from bot import process_telegram_webhook
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                update_dict = json.loads(body.decode("utf-8"))
                
                # Execute full Python bot pipeline asynchronously
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                loop.run_until_complete(process_telegram_webhook(update_dict))

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            except Exception as e:
                print(f"[!] Webhook error: {e}")
                self.send_response(200)  # Always 200 to prevent Telegram retry spam
                self.end_headers()
                self.wfile.write(b'{"status": "handled"}')
        elif self.path == "/api/save_chat":
            import json
            from metadata_db import save_chat_message
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = json.loads(body.decode("utf-8"))
                user_id = data.get("user_id", 8327334588)
                prompt = data.get("prompt", "")
                response = data.get("response", "")
                
                if prompt:
                    save_chat_message(user_id, role="user", message=prompt)
                if response:
                    save_chat_message(user_id, role="assistant", message=response)

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "saved"}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
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
    Mutual Keepalive Daemon on Hugging Face:
    Periodically sends lightweight HTTP GET requests to both Hugging Face Space AND Render Web Service
    to ensure neither service sleeps or idles out.
    """
    time.sleep(30)  # Initial grace period on boot
    
    # 1. Target Hugging Face URL
    hf_host = os.environ.get("SPACE_HOST")
    hf_target = f"https://{hf_host}/healthz" if hf_host else f"http://127.0.0.1:{os.environ.get('STREAMLIT_SERVER_PORT', '7860')}/healthz"

    # 2. Target Render Service URL
    render_target = os.environ.get("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if render_target:
        render_target = f"{render_target}/health"

    print(f"[*] Mutual Keepalive Daemon active. Monitoring HF: {hf_target} | Render: {render_target or 'N/A'} (every {interval_seconds}s)")
    while True:
        # Ping Hugging Face
        try:
            req = urllib.request.Request(
                hf_target,
                headers={"User-Agent": "Academic-Assistant-Keepalive/2.0", "Connection": "close"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                pass
        except Exception:
            pass

        # Ping Render
        if render_target:
            try:
                req_render = urllib.request.Request(
                    render_target,
                    headers={"User-Agent": "HF-To-Render-Keepalive/2.0", "Connection": "close"}
                )
                with urllib.request.urlopen(req_render, timeout=15) as resp_r:
                    pass
            except Exception:
                pass

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
    time.sleep(15)  # Allow container network namespace & services to warm up
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    allowed_ids = [uid.strip() for uid in os.environ.get("ALLOWED_TELEGRAM_USER_IDS", "").split(",") if uid.strip().isdigit()]
    target_users = allowed_ids if allowed_ids else ["8327334588"]

    if not token or not target_users:
        return

    import urllib.request
    import json

    proxy_base_url = os.environ.get("TELEGRAM_API_BASE_URL", "").strip().rstrip("/")
    if not proxy_base_url:
        proxy_base_url = "https://summer-band-ce5a.akhilkumarbaja.workers.dev"

    api_url = f"{proxy_base_url}/bot{token}/sendMessage"

    boot_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg_text = (
        f"🚀 *New Deployment Detected & Online!*\n\n"
        f"• **Status**: `All Services Operational`\n"
        f"• **Boot Time**: `{boot_time}`\n"
        f"• **Active Engine**: `{os.environ.get('GEMINI_MODEL', 'gemini-3.6-flash')}`\n"
        f"• **Webhook Gateway**: `Active via Cloudflare Worker`\n"
        f"• **Dashboard**: [abaja-notes-taker.hf.space](https://abaja-notes-taker.hf.space)\n\n"
        f"💬 Send `/menu` or ask any question to begin!"
    )

    for uid in target_users:
        payload = json.dumps({
            "chat_id": int(uid),
            "text": msg_text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }).encode("utf-8")

        for attempt in range(1, 5):
            try:
                req = urllib.request.Request(
                    api_url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Connection": "close"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status == 200:
                        print(f"[+] Startup deployment notification sent to Telegram user {uid}!")
                        break
            except Exception as e:
                print(f"[!] Deployment notification attempt {attempt} for {uid}: {e}")
                time.sleep(5 * attempt)

def start_service(name: str, cmd: list) -> subprocess.Popen:
    """Spawns a managed process with explicit environment inheritance and registers it for self-healing supervision."""
    env_vars = os.environ.copy()
    try:
        proc = subprocess.Popen(cmd, env=env_vars)
    except Exception as e:
        print(f"[!] Error launching {name}: {e}")
        proc = subprocess.Popen(cmd, env=env_vars, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    # 5. Start High-Performance FastAPI + React Web Server (Port 7860 on HF Spaces / 8501 local)
    port = int(os.environ.get("STREAMLIT_SERVER_PORT", "7860"))
    print(f"[*] Launching FastAPI + React Web Hub on port {port}...")
    start_service("FastAPI_Hub", [
        python_executable, "-u", "-m", "uvicorn", "server:app",
        "--host", "0.0.0.0",
        "--port", str(port)
    ])

    # 6. Dispatch Proactive Startup Deployment Notification to Telegram
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
                    new_proc = start_service(name, cmd)
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
