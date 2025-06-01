import subprocess
from dotenv import load_dotenv
from backend.generate_script import Script, generate_script
from config.paths import MANIM_KNOWLEDGE_PATH, MANIM_PROMPT_PATH, VIDEO_OUTPUT_DIR, CODE_OUTPUT_DIR
from config.llm import LLMClient
from pathlib import Path
import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional, List
import time

# Load environment variables
load_dotenv()
import shutil

# FFmpeg path for video concatenation
FFMPEG_PATH = shutil.which("ffmpeg")
if FFMPEG_PATH is None:
    raise FileNotFoundError("ffmpeg not found in PATH. Please install it or add it to your PATH.")

# Initialize the LLM client
llm = LLMClient(model="claude-sonnet-4-20250514", temperature=0.3, max_tokens=8000)

# Load Manim knowledge and prompt template
manim_knowledge = MANIM_KNOWLEDGE_PATH.read_text(encoding="utf-8")
manim_prompt_template = MANIM_PROMPT_PATH.read_text(encoding="utf-8")
math_tex_knowledge = Path("data/math_tex_knowledge.txt").read_text(encoding="utf-8")

# -----------------------------------------------
# Generate code from LLM and extract Python code block
# -----------------------------------------------
def generate_manim_code(prompt: str) -> str:
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
    match = re.search(r"'''(.*?)'''", raw_output, flags=re.DOTALL)
    return match.group(1).strip() if match else ""

def fix_manim_code(original_code: str, error_message: str, scene_description: str) -> str:
    """
    Ask LLM to fix broken Manim code based on error message
    """
    system_prompt = f"""
You are a Manim expert. Fix the broken Manim code based on the error message.

Manim knowledge:
{manim_knowledge}

Math tex knowledge:
{math_tex_knowledge}

Original scene requirements:
{scene_description}

IMPORTANT: Always return the complete fixed Python code wrapped in triple backticks (```).
"""
    
    # Truncate very long error messages but keep the important parts
    if len(error_message) > 2000:
        lines = error_message.split('\n')
        # Keep first 10 and last 10 lines of error
        if len(lines) > 20:
            truncated_lines = lines[:10] + ['... (truncated) ...'] + lines[-10:]
            error_message = '\n'.join(truncated_lines)
    
    user_prompt = f"""
The following Manim code failed to render with this error:

ERROR MESSAGE:
{error_message}

BROKEN CODE:
```python
{original_code}
```

Please fix the code to resolve this error while maintaining the original scene requirements. 

Common Manim issues to check:
- Import statements (missing imports)
- Class names and inheritance
- Method calls and syntax
- Mathematical notation in MathTex
- Animation timing and parameters

Return ONLY the corrected Python code wrapped in triple backticks (```).
"""
    
    print(f"🔧 Asking LLM to fix error...")
    
    try:
        raw_output = llm.chat(system_prompt, user_prompt)
        
        # Try multiple patterns to extract code
        patterns = [
            r"```python\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```", 
            r"`{3}python\s*(.*?)\s*`{3}",
            r"`{3}\s*(.*?)\s*`{3}"
        ]
        
        fixed_code = ""
        for pattern in patterns:
            match = re.search(pattern, raw_output, flags=re.DOTALL)
            if match:
                fixed_code = match.group(1).strip()
                break
        
        if fixed_code:
            print(f"✅ LLM provided fixed code ({len(fixed_code)} chars)")
        else:
            print(f"❌ LLM failed to provide fixed code")
            print(f"Raw LLM output (first 500 chars): {raw_output[:500]}")
        
        return fixed_code
        
    except Exception as e:
        print(f"❌ Error calling LLM for fix: {str(e)}")
        return ""

# Slugify string for safe folder names
def safe_slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

# Extract class name from Manim code
def extract_scene_class(code: str) -> str:
    match = re.search(r'class\s+(\w+)\s*\(.*?Scene\)', code)
    if match:
        return match.group(1)
    return "Scene"

# Save Manim code to .py file
def save_code(code: str, filename: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    py_file = output_dir / f"{filename}.py"
    with py_file.open("w", encoding="utf-8") as f:
        f.write(code)
    return py_file

def concatenate_scene_videos(video_dir: Path, successful_scenes: List[int]) -> Optional[Path]:
    """
    Concatenate all successful scene videos into final_video.mp4
    """
    if not successful_scenes:
        print("❌ No successful scenes to concatenate")
        return None
    
    print(f"\n🎬 Concatenating {len(successful_scenes)} scene videos...")
    
    # Find all scene video files using Manim's actual output structure
    video_files = []
    for scene_idx in sorted(successful_scenes):
        scene_num = scene_idx + 1  # Convert 0-based to 1-based
        
        # Manim's actual output structure includes /media/videos/
        video_path = video_dir / "media" / "videos" / f"scene_{scene_num}" / "1080p60" / f"scene_{scene_num}.mp4"
        
        if video_path.exists():
            video_files.append(video_path)
            print(f"  ✅ Found scene {scene_num}: {video_path}")
        else:
            print(f"  ❌ Missing scene {scene_num} at: {video_path}")
    
    if not video_files:
        print("❌ No video files found for concatenation")
        return None
    
    if len(video_files) == 1:
        print("ℹ️ Only one video file, copying as final_video.mp4")
        final_path = video_dir / "final_video.mp4"
        import shutil
        shutil.copy2(video_files[0], final_path)
        return final_path
    
    # Create file list for FFmpeg concatenation
    list_file = video_dir / "video_list.txt"
    with list_file.open("w") as f:
        for video_file in video_files:
            f.write(f"file '{video_file.resolve()}'\n")
    
    final_path = video_dir / "final_video.mp4"
    
    cmd = [
        FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(final_path)
    ]
    
    print(f"🎬 Running FFmpeg concatenation...")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Videos concatenated successfully: {final_path}")
        
        # Clean up the list file
        list_file.unlink()
        
        return final_path
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg concatenation failed: {e.stderr}")
        return None

# Render .py file using Manim with error capture
def render_code(py_file: Path, scene_name: str, output_dir: Path) -> Tuple[bool, str]:
    """
    Render Manim code and return (success, error_message)
    """
    print(f"🎬 Rendering {scene_name} from {py_file.name}...")
    try:
        result = subprocess.run(
            ["manim", str(py_file), scene_name, "-o", f"{py_file.stem}.mp4"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            check=True,
            timeout=300  # 5 minute timeout
        )
        print(f"✅ Render complete for {py_file.name}")
        return True, ""
    except subprocess.CalledProcessError as e:
        # Get full error message and filter out progress bars
        full_error = e.stderr if e.stderr else str(e)
        
        # Filter out progress bar lines and animation progress
        error_lines = []
        for line in full_error.split('\n'):
            line = line.strip()
            # Skip progress bars and animation progress indicators
            if (not line or 
                'it/s]' in line or 
                '%|' in line or 
                'Animation' in line and ('Create(' in line or 'Transform(' in line) and '%' in line):
                continue
            error_lines.append(line)
        
        # Join meaningful error lines
        filtered_error = '\n'.join(error_lines).strip()
        
        # If no meaningful error after filtering, use original
        if not filtered_error:
            filtered_error = full_error
        
        print(f"❌ Render failed for {py_file.name}")
        print(f"Error (first 300 chars): {filtered_error[:300]}...")
        return False, filtered_error
    except subprocess.TimeoutExpired:
        print(f"❌ Render timed out for {py_file.name}")
        return False, "Render process timed out after 5 minutes"

# Process a single scene with automatic error correction
def process_single_scene(concept_data: Tuple[int, object, Path, Path]) -> Tuple[int, bool]:
    """
    Process a single scene with automatic error correction if rendering fails.
    """
    scene_index, concept, topic_code_dir, topic_video_dir = concept_data
    max_retries = 3
    
    print(f"\n🔧 Processing Scene {scene_index + 1}")
    
    try:
        # Generate initial code
        prompt = f"Scene description for concept {scene_index + 1}:\n{concept.scene_description}"
        code = generate_manim_code(prompt)

        if not code.strip():
            print(f"⚠️ Skipping scene {scene_index + 1} — empty code.")
            return (scene_index, False)

        filename = f"scene_{scene_index + 1}"
        
        # Try rendering with automatic error correction
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"🔄 Retry attempt {attempt}/{max_retries} for scene {scene_index + 1}")
            
            # Save and try to render current code
            py_file = save_code(code, filename, topic_code_dir)
            scene_class = extract_scene_class(code)
            success, error_message = render_code(py_file, scene_class, topic_video_dir)
            
            if success:
                print(f"✅ Scene {scene_index + 1} rendered successfully!")
                return (scene_index, True)
            
            # If we failed and have retries left, ask LLM to fix it
            if attempt < max_retries and error_message:
                print(f"🔧 Attempting to fix scene {scene_index + 1} (attempt {attempt + 1}/{max_retries})")
                
                # Ask LLM to fix the code
                fixed_code = fix_manim_code(code, error_message, concept.scene_description)
                
                if fixed_code and fixed_code != code:
                    code = fixed_code
                    print(f"🆕 Updated code for scene {scene_index + 1}")
                else:
                    print(f"❌ LLM couldn't fix the code for scene {scene_index + 1}")
                    break
            else:
                break
        
        print(f"❌ Scene {scene_index + 1} failed after {max_retries} attempts")
        return (scene_index, False)
        
    except Exception as e:
        print(f"❌ Error processing scene {scene_index + 1}: {str(e)}")
        return (scene_index, False)

# Process all scenes in a script, in parallel
def generate_all_scenes_from_script(script: Script, max_workers: Optional[int] = None, custom_output_name: Optional[str] = None):
    """
    Generate and render all scenes in parallel with automatic error correction.
    
    Args:
        script: The script containing concepts to generate scenes for
        max_workers: Maximum number of parallel workers (None for default)
        custom_output_name: Custom name for output folders (e.g., job_id), 
                          if None uses script.topic
    """
    if not script.concepts:
        print("❌ No concepts in script!")
        return
    
    # Use custom_output_name if provided, otherwise use topic slug
    if custom_output_name:
        folder_name = custom_output_name
        print(f"📁 Using custom output name: {custom_output_name}")
    else:
        folder_name = safe_slugify(script.topic)
        print(f"📁 Using topic-based name: {safe_slugify(script.topic)}")
    
    # Create output directories using the determined folder name
    topic_code_dir = CODE_OUTPUT_DIR / folder_name
    topic_video_dir = VIDEO_OUTPUT_DIR / folder_name

    topic_code_dir.mkdir(parents=True, exist_ok=True)
    topic_video_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n==============================")
    print(f"🚀 Processing {len(script.concepts)} scenes with auto-correction")
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
    successful_scene_indices = []  # Track which scenes succeeded

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
                    successful_scene_indices.append(scene_index)
                    print(f"✅ Scene {scene_index + 1} completed successfully")
                else:
                    failed_scenes += 1
                    print(f"❌ Scene {scene_index + 1} failed permanently")
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

    # Concatenate successful videos
    if successful_scenes > 0:
        final_video = concatenate_scene_videos(topic_video_dir, successful_scene_indices)
        if final_video:
            print(f"\n🎉 FINAL VIDEO CREATED: {final_video}")
            print(f"📊 Combined {len(successful_scene_indices)} scenes into final video")
            return final_video
        else:
            print(f"\n❌ Failed to create final video")
    else:
        print(f"\n💥 No scenes were successfully generated - cannot create final video")
    
    return None

# CLI test
if __name__ == "__main__":
    topic = "Teach me what a derivative is?"
    duration = 10
    level = 3

    print("📜 Generating script...")
    script = generate_script(topic=topic, duration_minutes=duration, sophistication_level=level)
    print(f"🔍 DEBUG: Generated {len(script.concepts)} concepts/scenes")
    print("🚀 Script generated. Starting parallel scene generation...\n")

    # Limit workers to respect API rate limits
    final_video = generate_all_scenes_from_script(script, max_workers=2)
    
    if final_video:
        print(f"\n🎊 SUCCESS! Complete video pipeline finished!")
        print(f"📹 Final video: {final_video}")
    else:
        print(f"\n💥 FAILED! Video pipeline did not complete successfully")