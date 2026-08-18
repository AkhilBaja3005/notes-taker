import os
import time
from pathlib import Path
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from watchdog.observers import Observer
# pyrefly: ignore [missing-import]
from watchdog.events import FileSystemEventHandler
from ingest_audio import process_file, SUPPORTED_EXTS

load_dotenv()
WATCH_DIR = Path(os.environ.get("WATCH_DIR", "./incoming_audio"))

class FileDropHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix.lower() in SUPPORTED_EXTS:
            print(f"[*] Detected incoming file: {file_path.name}")
            
            # Allow file sync/write to finish completely by monitoring size stability
            initial_size = -1
            while True:
                time.sleep(3)
                try:
                    current_size = file_path.stat().st_size
                except FileNotFoundError:
                    return
                if current_size == initial_size and current_size > 0:
                    break
                initial_size = current_size

            # Expected naming scheme: Course_Topic_YYYY-MM-DD.ext
            parts = file_path.stem.split("_")
            if len(parts) >= 3:
                course = parts[0].replace("-", " ")
                topic = " ".join(parts[1:-1]).replace("-", " ")
                date = parts[-1]
            else:
                course = "General"
                topic = file_path.stem.replace("-", " ")
                date = None

            print(f"[*] Auto-triggering ingestion for: Course='{course}', Topic='{topic}'")
            try:
                process_file(str(file_path), course, topic, date)
            except Exception as e:
                print(f"[!] Error processing {file_path.name}: {e}")

if __name__ == "__main__":
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    event_handler = FileDropHandler()
    observer = Observer()
    observer.schedule(event_handler, str(WATCH_DIR), recursive=False)
    observer.start()
    print(f"[+] Multi-Format Watcher active. Monitoring folder: {WATCH_DIR.resolve()}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
