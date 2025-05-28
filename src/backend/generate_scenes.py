import subprocess
from dotenv import load_dotenv
from backend.generate_script import Script, generate_script
from config.paths import MANIM_KNOWLEDGE_PATH, MANIM_PROMPT_PATH, VIDEO_OUTPUT_DIR, CODE_OUTPUT_DIR
from config.llm import LLMClient
from pathlib import Path
import re

# Load environment variables
load_dotenv()

# Initialize the LLM client
llm = LLMClient(model="claude-sonnet-4-20250514", temperature=0.3, max_tokens=4000)

# Load Manim knowledge and prompt template
manim_knowledge = MANIM_KNOWLEDGE_PATH.read_text(encoding="utf-8")
manim_prompt_template = MANIM_PROMPT_PATH.read_text(encoding="utf-8")
math_tex_knowledge = Path("data/math_tex_knowledge.txt").read_text(encoding="utf-8")

# -----------------------------------------------
# Generate code from LLM and extract Python code block
# -----------------------------------------------
def generate_manim_code(prompt: str) -> str:
    print("\n--- LLM Prompt Start ---")
    print(prompt)
    print("--- LLM Prompt End ---")

    system_prompt = f"""
This is the full breakdown on how to use manim:
{manim_knowledge}
\n\n
This is the full breakdown on how to use math_tex::
{math_tex_knowledge}
\n\n
This is the task we would like you to accomplish with the given information:
{manim_prompt_template}
"""
    raw_output = llm.chat(system_prompt, prompt)

    print("\n--- Raw LLM Output ---")
    print(raw_output)
    print("--- End Raw Output ---")

    match = re.search(r"'''(.*?)'''", raw_output, flags=re.DOTALL)
    code = match.group(1).strip() if match else ""

    print("\n--- Extracted Code ---")
    print(code if code else "[No code found in triple quotes]")
    print("--- End Extracted Code ---")

    return code

# Slugify string for safe folder names
def safe_slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

# Extract class name from Manim code
def extract_scene_class(code: str) -> str:
    match = re.search(r'class\s+(\w+)\s*\(.*?Scene\)', code)
    if match:
        print(f"✅ Scene class: {match.group(1)}")
        return match.group(1)
    print("⚠️ No scene class found, using fallback: Scene")
    return "Scene"

# Save Manim code to .py file
def save_code(code: str, filename: str, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    py_file = output_dir / f"{filename}.py"
    with py_file.open("w", encoding="utf-8") as f:
        f.write(code)
    print(f"✅ Code saved to: {py_file}")
    return py_file

# Render .py file using Manim
def render_code(py_file: Path, scene_name: str, output_dir: Path):
    print(f"🎬 Rendering {scene_name} from {py_file.name}...")
    try:
        subprocess.run(
            ["manim", str(py_file), scene_name, "-o", f"{py_file.stem}.mp4"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Render complete.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Render failed: {e.stderr}")

# Process all scenes in a script, sequentially
def generate_all_scenes_from_script(script: Script):
    topic_slug = safe_slugify(script.topic)
    topic_code_dir = CODE_OUTPUT_DIR / topic_slug
    topic_video_dir = VIDEO_OUTPUT_DIR / topic_slug

    topic_code_dir.mkdir(parents=True, exist_ok=True)
    topic_video_dir.mkdir(parents=True, exist_ok=True)

    for i, concept in enumerate(script.concepts):
        print(f"\n==============================")
        print(f"🔧 Processing Concept {i + 1}/{len(script.concepts)}")
        print("==============================")

        prompt = f"Scene description for concept {i + 1}:\n{concept.scene_description}"
        code = generate_manim_code(prompt)

        if not code.strip():
            print("⚠️ Skipping scene — empty code.")
            continue

        filename = f"scene_{i + 1}"
        py_file = save_code(code, filename, topic_code_dir)
        scene_class = extract_scene_class(code)
        render_code(py_file, scene_class, topic_video_dir)

# CLI test
if __name__ == "__main__":
    topic = "Teach me what a derivative is?"
    duration = 10
    level = 3

    print("📜 Generating script...")
    script = generate_script(topic=topic, duration_minutes=duration, sophistication_level=level)
    print("🚀 Script generated. Starting scene generation...\n")

    generate_all_scenes_from_script(script)
