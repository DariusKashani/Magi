import subprocess
from dotenv import load_dotenv
from backend.generate_script import Script, generate_script
from config.paths import MANIM_KNOWLEDGE_PATH, MANIM_PROMPT_PATH, VIDEO_OUTPUT_DIR, CODE_OUTPUT_DIR
from config.llm import LLMClient
from pathlib import Path
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional
import time

# Load environment variables
load_dotenv()

# Initialize the LLM client
llm = LLMClient(model="claude-sonnet-4-20250514", temperature=0.3, max_tokens=20000)

# Load Manim knowledge and prompt template
manim_knowledge = MANIM_KNOWLEDGE_PATH.read_text(encoding="utf-8")
manim_prompt_template = MANIM_PROMPT_PATH.read_text(encoding="utf-8")
math_tex_knowledge = Path("data/math_tex_knowledge.txt").read_text(encoding="utf-8")

# -----------------------------------------------
# Generate code from LLM and extract Python code block
# -----------------------------------------------
def generate_manim_code(prompt: str) -> str:
    print(f"\n--- LLM Prompt Start (Thread: {prompt[:50]}...) ---")
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

    print(f"\n--- Raw LLM Output (Thread: {prompt[:50]}...) ---")
    print(raw_output)
    print("--- End Raw Output ---")

    match = re.search(r"'''(.*?)'''", raw_output, flags=re.DOTALL)
    code = match.group(1).strip() if match else ""

    print(f"\n--- Extracted Code (Thread: {prompt[:50]}...) ---")
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
def save_code(code: str, filename: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    py_file = output_dir / f"{filename}.py"
    with py_file.open("w", encoding="utf-8") as f:
        f.write(code)
    print(f"✅ Code saved to: {py_file}")
    return py_file

# Render .py file using Manim
def render_code(py_file: Path, scene_name: str, output_dir: Path) -> bool:
    print(f"🎬 Rendering {scene_name} from {py_file.name}...")
    try:
        result = subprocess.run(
            ["manim", str(py_file), scene_name, "-o", f"{py_file.stem}.mp4"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ Render complete for {py_file.name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Render failed for {py_file.name}: {e.stderr}")
        return False

# Process a single scene (generate code + render)
def process_single_scene(concept_data: Tuple[int, object, Path, Path]) -> Tuple[int, bool]:
    """
    Process a single scene: generate code, save it, and render it.
    
    Args:
        concept_data: Tuple of (scene_index, concept, topic_code_dir, topic_video_dir)
    
    Returns:
        Tuple of (scene_index, success_status)
    """
    scene_index, concept, topic_code_dir, topic_video_dir = concept_data
    
    print(f"\n🔧 Processing Scene {scene_index + 1}")
    
    try:
        # Generate code
        prompt = f"Scene description for concept {scene_index + 1}:\n{concept.scene_description}"
        code = generate_manim_code(prompt)

        if not code.strip():
            print(f"⚠️ Skipping scene {scene_index + 1} — empty code.")
            return (scene_index, False)

        # Save code
        filename = f"scene_{scene_index + 1}"
        py_file = save_code(code, filename, topic_code_dir)
        
        # Extract scene class and render
        scene_class = extract_scene_class(code)
        success = render_code(py_file, scene_class, topic_video_dir)
        
        return (scene_index, success)
        
    except Exception as e:
        print(f"❌ Error processing scene {scene_index + 1}: {str(e)}")
        return (scene_index, False)

# Process all scenes in a script, in parallel
def generate_all_scenes_from_script(script: Script, max_workers: Optional[int] = None):
    """
    Generate and render all scenes in parallel.
    
    Args:
        script: The script containing all concepts/scenes
        max_workers: Maximum number of parallel workers (defaults to None for auto-detection)
    """
    topic_slug = safe_slugify(script.topic)
    topic_code_dir = CODE_OUTPUT_DIR / topic_slug
    topic_video_dir = VIDEO_OUTPUT_DIR / topic_slug

    topic_code_dir.mkdir(parents=True, exist_ok=True)
    topic_video_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n==============================")
    print(f"🚀 Processing {len(script.concepts)} scenes in parallel")
    print(f"📁 Code output: {topic_code_dir}")
    print(f"🎥 Video output: {topic_video_dir}")
    print("==============================")

    # Prepare data for parallel processing
    concept_data_list = [
        (i, concept, topic_code_dir, topic_video_dir)
        for i, concept in enumerate(script.concepts)
    ]

    start_time = time.time()
    successful_scenes = 0
    failed_scenes = 0

    # Process scenes in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_scene = {
            executor.submit(process_single_scene, concept_data): concept_data[0]
            for concept_data in concept_data_list
        }

        # Collect results as they complete
        for future in as_completed(future_to_scene):
            scene_index = future_to_scene[future]
            try:
                scene_index, success = future.result()
                if success:
                    successful_scenes += 1
                    print(f"✅ Scene {scene_index + 1} completed successfully")
                else:
                    failed_scenes += 1
                    print(f"❌ Scene {scene_index + 1} failed")
            except Exception as e:
                failed_scenes += 1
                print(f"❌ Scene {scene_index + 1} threw exception: {str(e)}")

    end_time = time.time()
    total_time = end_time - start_time

    print(f"\n==============================")
    print(f"🏁 Parallel processing complete!")
    print(f"⏱️  Total time: {total_time:.2f} seconds")
    print(f"✅ Successful scenes: {successful_scenes}")
    print(f"❌ Failed scenes: {failed_scenes}")
    print(f"📊 Success rate: {(successful_scenes / len(script.concepts) * 100):.1f}%")
    print("==============================")

# CLI test
if __name__ == "__main__":
    topic = "Teach me what a derivative is?"
    duration = 10
    level = 3

    print("📜 Generating script...")
    script = generate_script(topic=topic, duration_minutes=duration, sophistication_level=level)
    print("🚀 Script generated. Starting parallel scene generation...\n")

    # You can adjust max_workers based on your system capabilities
    # None = auto-detect, or specify a number like 4, 8, etc.
    generate_all_scenes_from_script(script, max_workers=None)