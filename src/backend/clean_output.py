#!/usr/bin/env python3
import shutil
from pathlib import Path
from config.paths import VIDEO_OUTPUT_DIR, AUDIO_OUTPUT_DIR, SCRIPT_OUTPUT_DIR, CODE_OUTPUT_DIR

# Define directories to clean
dirs_to_clean = [
    VIDEO_OUTPUT_DIR,
    AUDIO_OUTPUT_DIR,
    SCRIPT_OUTPUT_DIR,
    CODE_OUTPUT_DIR,
]

# Delete everything
for directory in dirs_to_clean:
    if directory.exists():
        print(f"Cleaning {directory}")
        shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✅ Done")
    else:
        print(f"⚠️ {directory} doesn't exist")

print("🧹 All cleaned!")