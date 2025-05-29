from pathlib import Path

# ---------------------------
# Root and Base Directories
# ---------------------------
ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------
# Data and Output Structure
# ---------------------------
DATA_PATH = ROOT / "data"
PROMPTS_PATH = DATA_PATH / "prompts"
MANIM_REF_PATH = DATA_PATH

OUTPUT_PATH = ROOT / "output"
VIDEO_OUTPUT_DIR = OUTPUT_PATH / "videos"
AUDIO_OUTPUT_DIR = OUTPUT_PATH / "audio"
SCRIPT_OUTPUT_DIR = OUTPUT_PATH / "script"
CODE_OUTPUT_DIR = OUTPUT_PATH / "code"

# ---------------------------
# Prompt Files
# ---------------------------
SCRIPT_GEN_PROMPT_PATH = PROMPTS_PATH / "script_gen_prompt.txt"
MANIM_PROMPT_PATH = PROMPTS_PATH / "manim_code_prompt.txt"

# ---------------------------
# Knowledge Base
# ---------------------------
MANIM_KNOWLEDGE_PATH = DATA_PATH / "manim_knowledge.txt"
SCENE_EXAMPLES_PATH = Path("data/scene_examples.yaml")  # Change extension
