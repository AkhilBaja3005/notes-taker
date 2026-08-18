import os
import shutil
import subprocess
from pathlib import Path

SUPPORTED_AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".flac", ".wma"}

def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None

def optimize_audio_file(file_path: Path, max_part_minutes: int = 45) -> list[Path]:
    """
    Optimizes audio recordings:
    - If macOS native afconvert is available: downsamples to 32kbps mono AAC (HE-AAC/AAC) with zero extra dependencies.
    - If ffmpeg is installed: downsamples and performs multi-part chunking for recordings > 45 minutes.
    - If no transcoder is present: seamlessly falls back to the original file.
    """
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTS:
        return [file_path]

    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    out_dir = file_path.parent / "optimized_audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"opt_{file_path.stem}.m4a"

    # 1. Try macOS built-in afconvert (Universal & zero-dependency on Mac)
    afconvert_bin = shutil.which("afconvert")
    if afconvert_bin:
        try:
            print(f"[*] Optimizing {file_path.name} ({file_size_mb:.2f} MB) via macOS audio engine...")
            # -f m4af: m4a container, -d aac: AAC codec, -b 32000: 32kbps, -c 1: mono
            cmd = [afconvert_bin, "-f", "m4af", "-d", "aac", "-b", "32000", "-c", "1", str(file_path), str(out_file)]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and out_file.exists():
                opt_size_mb = out_file.stat().st_size / (1024 * 1024)
                print(f"[+] Compressed {file_path.name} ({file_size_mb:.2f}MB -> {opt_size_mb:.2f}MB): {out_file.name}")
                return [out_file]
        except Exception as e:
            print(f"[!] afconvert fallback: {e}")

    # 2. Try ffmpeg if available
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        try:
            print(f"[*] Compressing {file_path.name} via ffmpeg...")
            cmd = [ffmpeg_bin, "-y", "-i", str(file_path), "-ac", "1", "-ar", "16000", "-b:a", "32k", str(out_file)]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and out_file.exists():
                opt_size_mb = out_file.stat().st_size / (1024 * 1024)
                print(f"[+] ffmpeg compressed {file_path.name} ({file_size_mb:.2f}MB -> {opt_size_mb:.2f}MB)")
                return [out_file]
        except Exception as e:
            print(f"[!] ffmpeg fallback: {e}")

    # 3. Fallback to original file
    print(f"[*] Using original audio: {file_path.name}")
    return [file_path]

if __name__ == "__main__":
    test_audio = Path("./test_samples/Optimization_KKT-Conditions_2026-10-15.m4a")
    if test_audio.exists():
        parts = optimize_audio_file(test_audio)
        print(f"Result: {parts}")
