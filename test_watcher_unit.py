import time
import shutil
from pathlib import Path
from watcher import FileDropHandler

# Simulate file drop event directly with FileDropHandler
incoming = Path("./incoming_audio")
sample = Path("./test_samples/Optimization_KKT-Conditions_2026-10-15.m4a")
target = incoming / "Optimization_KKT-WatcherTest_2026-10-15.m4a"

shutil.copy(sample, target)
print(f"[+] Dropped file: {target.name} into {incoming}")

class FakeEvent:
    is_directory = False
    src_path = str(target)

handler = FileDropHandler()
print("[*] Simulating Watcher detection...")
handler.on_created(FakeEvent())

# Clean up simulated file
if target.exists():
    target.unlink()
print("[+] Watcher simulation completed successfully")
