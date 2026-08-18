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

    # 2. Start Telegram Bot
    print("[*] Launching Telegram Bot (bot.py)...")
    bot_proc = subprocess.Popen(
        [python_executable, "bot.py"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    processes.append(bot_proc)

    # 3. Start Streamlit App
    print("[*] Launching Streamlit Web App (app.py)...")
    streamlit_proc = subprocess.Popen(
        [python_executable, "-m", "streamlit", "run", "app.py"],
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
