import os
import sys
import shutil
import re
import tempfile
from pathlib import Path
import sys
import os
import subprocess
from pathlib import Path
from backend.generate_script import Script, generate_script
from backend.generate_scenes import generate_all_scenes_from_script, safe_slugify
from backend.generate_audio import generate_audio_narration

from dotenv import load_dotenv
from openai import OpenAI
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Add config imports
from config.paths import VIDEO_OUTPUT_DIR




project_root = Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(project_root))
load_dotenv()
FFMPEG_PATH = os.path.expanduser("~/bin/ffmpeg")



def extend_video_duration(video_path: str, target_duration: float, output_path: str) -> str:
    """
    Extend a video to the target duration by freezing the last frame.
    
    Args:
        video_path: Path to the input video.
        target_duration: Desired duration in seconds.
        output_path: Path to save the extended video.
        
    Returns:
        Path to the extended video if successful, otherwise None.
    """


def merge_videos_with_audio(video_files: list, timing_data: list, output_dirs: dict,
                            audio_path: str = None, duration_minutes: int = 5,
                            subtitle_path: str = None) -> str:
    """
    Merge videos with audio using ffmpeg.
    
    Args:
        video_files: List of paths to video files.
        timing_data: Timing data for synchronization.
        output_dirs: Dictionary of output directories.
        audio_path: Path to the audio file.
        duration_minutes: Target duration in minutes.
        subtitle_path: Path to subtitle file.
        
    Returns:
        Path to the final video if successful, otherwise None.
    """


def generate_tutorial_video(topic: str, duration_minutes: int = 5, sophistication_level: int = 2):
    """
    Create a complete math tutorial from script to final video.
    Acts as the entry point for the code base backend. 
    
    Args: topic - the topic we want to generate,
          sophistication level-how sophisitcated the tutoral is (default 2),
          duration - length of the video (default 5 minutes)
    
    Output: The completed tutorial video
    """
    
    # Generate script
    print(f"Generating script for {topic}")

    # Calls generate_script function in generate_script.py, returns Script dataclass
    script = generate_script(
        topic=topic, 
        sophistication_level=sophistication_level, 
        duration_minutes=duration_minutes, 
    )
    
    # Create the scenes from the script
    generate_all_scenes_from_script(script)

    
    slugged_topic_file = safe_slugify(topic)
    video_dir = VIDEO_OUTPUT_DIR / slugged_topic_file / "videos/scene_1/"
    
    # List of paths for all the scenes
    video_files = sorted(video_dir.rglob("scene_*.mp4"))
    
    if not video_files:
        raise FileNotFoundError(f"[ERROR] No scenes videos found in {video_dir}")


    # Build FFmpeg list file
    list_file = video_dir / "scenes.txt"
    with list_file.open("w") as f:
        for vf in video_files:
            f.write(f"file '{vf.resolve()}'\n")

    # Define output video path
    final_video_path = video_dir / f"{slugged_topic_file}_final.mp4"

    # Run FFmpeg to merge
    try:
        subprocess.run(
            ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(final_video_path)],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Final tutorial video saved to: {final_video_path}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg failed: {e.stderr}")
    
    # 05/27/2025 --- Arman Vossoughi
    # --- Start of Notes ---
    # What I need to do, overlay audio with the video
        # Essentially scenes should be modified to have the proper audio overlayed, w/scenes slowed down or paused on last frame
        # In order to ensure ample time for audio to happen
    
    # What to look into:
        # Concept extraction from script, right now only one scene is being generated, but I believe there should be more. 
    
    # --- End of Notes ---
if __name__ == "__main__":
    # Example usage
    generate_tutorial_video("Pythagorean Theorem", sophistication_level=2, duration_minutes=5)
