from pathlib import Path

# Fix: Since paths.py is in src/config/, we need to go up 3 levels to reach project root
# src/config/paths.py -> src/config/ -> src/ -> project_root/
BASE_DIR = Path(__file__).parent.parent.parent

# Debug output to verify the path
print(f"🔍 BASE_DIR set to: {BASE_DIR}")
print(f"🔍 BASE_DIR absolute path: {BASE_DIR.absolute()}")
print(f"🔍 Data directory path: {BASE_DIR / 'data'}")
print(f"✅ Data directory exists: {(BASE_DIR / 'data').exists()}")

DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "src" / "config"  # Updated to reflect actual structure
OUTPUT_DIR = BASE_DIR / "output"

# Output directories
VIDEO_OUTPUT_DIR = OUTPUT_DIR / "videos"
CODE_OUTPUT_DIR = OUTPUT_DIR / "code"
AUDIO_OUTPUT_DIR = OUTPUT_DIR / "audio"

# Create output directories if they don't exist
VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CODE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Data files - these should now point to the correct data directory
MANIM_KNOWLEDGE_PATH = DATA_DIR / "manim_knowledge.txt"
MANIM_PROMPT_PATH = DATA_DIR / "prompts" / "manim_code_prompt.txt"  # Updated path
SCENE_EXAMPLES_PATH = DATA_DIR / "scene_examples.yaml"
SCRIPT_GEN_PROMPT_PATH = DATA_DIR / "prompts" / "script_gen_prompt.txt"  # Updated path

# Validate that the data directory exists (READ-ONLY - should already exist)
if not DATA_DIR.exists():
    raise FileNotFoundError(f"❌ Data directory not found at: {DATA_DIR}. Please ensure the data directory exists with required files.")

print(f"✅ Data directory found at: {DATA_DIR}")

# Validate that all required data files exist (READ-ONLY)
required_files = {
    "Manim Knowledge": MANIM_KNOWLEDGE_PATH,
    "Manim Prompt": MANIM_PROMPT_PATH,
    "Scene Examples": SCENE_EXAMPLES_PATH,
    "Script Generation Prompt": SCRIPT_GEN_PROMPT_PATH
}

missing_files = []
for name, path in required_files.items():
    if not path.exists():
        missing_files.append(f"  ❌ {name}: {path}")
        print(f"❌ Missing required file: {path}")
    else:
        print(f"✅ Found {name}: {path}")

if missing_files:
    error_msg = f"❌ Missing required data files:\n" + "\n".join(missing_files)
    error_msg += f"\n\nPlease ensure all required files exist in the data directory: {DATA_DIR}"
    raise FileNotFoundError(error_msg)

# Final validation summary
print(f"\n📋 Path Configuration Summary:")
print(f"   BASE_DIR: {BASE_DIR}")
print(f"   DATA_DIR: {DATA_DIR} (READ-ONLY)")
print(f"   OUTPUT_DIR: {OUTPUT_DIR} (WRITE)")
print(f"✅ All required data files found and validated!")
print(f"📁 Output directories created successfully!")