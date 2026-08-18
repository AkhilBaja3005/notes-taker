import sys
import subprocess
import signal
import time
import os

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

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    python_executable = sys.executable

    print("=" * 60)
    print("🎓 Starting Autonomous Academic Lecture Assistant Services")
    print("=" * 60)

    # 1. Start Watcher Daemon
    print("[*] Launching Watcher Daemon (watcher.py)...")
    watcher_proc = subprocess.Popen(
        [python_executable, "watcher.py"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    processes.append(watcher_proc)

    # 2. Start Telegram Bot (if token provided)
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

    # 3. Start Streamlit App (Port 7860 on HF Spaces / 8501 local)
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

    # Monitor running processes
    try:
        while True:
            for p in processes:
                exit_code = p.poll()
                if exit_code is not None:
                    print(f"[!] Process PID {p.pid} exited with code {exit_code}.")
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()
