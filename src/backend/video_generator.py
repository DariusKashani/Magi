import os
import sys
import time
import shutil
import subprocess
import re
import tempfile
from pathlib import Path
import concurrent.futures
import concurrent.futures
import importlib.util
import sys
import os
from pathlib import Path
from manim import config
from backend import generate_script
from src.backend import manim_generator
from backend.generate_audio import generate_audio_narration
from backend.generate_scenes import render_manim_scenes, generate_manim_code_parallel
from dotenv import load_dotenv
from openai import OpenAI
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

from config import (
    get_subtitle_path,
    get_project_dirs
)


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
    try:
        result = subprocess.run(
            [FFMPEG_PATH, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, check=True
        )
        original_duration = float(result.stdout.strip())
        logger.info(f"Original video duration: {original_duration:.2f}s")
        
        if original_duration >= target_duration:
            shutil.copy2(video_path, output_path)
            return output_path
        
        freeze_duration = target_duration - original_duration
        logger.info(f"Extending video by freezing last frame for {freeze_duration:.2f}s")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            last_frame_path = temp_dir_path / "last_frame.png"
            frame_time = max(0, original_duration - 0.1)
            subprocess.run([
                FFMPEG_PATH, "-y", "-ss", str(frame_time),
                "-i", video_path, "-vframes", "1",
                "-q:v", "1", str(last_frame_path)
            ], check=True)
            
            frozen_video_path = temp_dir_path / "frozen.mp4"
            subprocess.run([
                FFMPEG_PATH, "-y", "-loop", "1", "-i", str(last_frame_path),
                "-c:v", "libx264", "-t", str(freeze_duration),
                "-pix_fmt", "yuv420p", str(frozen_video_path)
            ], check=True)
            
            concat_file = temp_dir_path / "concat.txt"
            with concat_file.open("w") as f:
                f.write(f"file '{Path(video_path).resolve()}'\n")
                f.write(f"file '{frozen_video_path.resolve()}'\n")
            
            subprocess.run([
                FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_file), "-c", "copy", output_path
            ], check=True)
        
        logger.info(f"Successfully extended video to {output_path}")
        return output_path
    except Exception as e:
        logger.exception(f"Error extending video: {e}")
        return None


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
    if not video_files:
        logger.error("No video files to merge")
        return None

    try:
        temp_dir = Path(output_dirs.get("temp", "temp"))
        temp_dir.mkdir(parents=True, exist_ok=True)
        list_file = temp_dir / "concat_list.txt"
        with list_file.open("w") as f:
            for video in video_files:
                f.write(f"file '{Path(video).resolve()}'\n")
        
        # First concatenate the video files
        concat_video = temp_dir / "concat_video.mp4"
        subprocess.run([
            FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(concat_video)
        ], check=True)
        logger.info(f"Videos concatenated to {concat_video}")

        # Intermediate file with audio
        audio_video = temp_dir / "audio_video.mp4"
        
        # Add audio if available
        if audio_path and Path(audio_path).exists() and Path(audio_path).stat().st_size > 0:
            logger.info(f"Adding audio narration from {audio_path}")
            
            # Get video duration
            try:
                # Use ffprobe to get video duration
                ffprobe_cmd = [
                    FFMPEG_PATH, "-v", "error", "-select_streams", "v:0", 
                    "-show_entries", "stream=duration", "-of", "csv=p=0", 
                    str(concat_video)
                ]
                logger.info(f"Running ffprobe command: {' '.join(ffprobe_cmd)}")
                result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
                video_duration = float(result.stdout.strip())
                logger.info(f"Video duration: {video_duration:.2f} seconds")
            except subprocess.CalledProcessError as e:
                logger.error(f"Error getting video duration: {str(e)}")
                if e.stderr:
                    logger.error(f"ffprobe error output: {e.stderr}")
                logger.info("Using estimated duration from timing data")
            
            # Add audio to video
            subprocess.run([
                FFMPEG_PATH, "-y",
                "-i", str(concat_video),  # Video input
                "-i", str(audio_path),    # Audio input
                "-c:v", "copy",           # Copy video codec
                "-c:a", "aac",            # Convert audio to AAC
                "-shortest",              # Match to shortest input
                str(audio_video)
            ], check=True)
            logger.info(f"Added audio to video: {audio_video}")
            
            # Use the audio+video file for final steps
            processed_video = audio_video
        else:
            logger.warning("No valid audio file found. Using video without narration.")
            processed_video = concat_video
        
        # Final video with subtitles if available
        final_output = temp_dir / "final_with_subs.mp4"
        
        if subtitle_path and Path(subtitle_path).exists():
            logger.info(f"Adding subtitles from {subtitle_path}")
            
            # Add subtitles to the video
            subprocess.run([
                FFMPEG_PATH, "-y",
                "-i", str(processed_video),
                "-vf", f"subtitles={subtitle_path}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H80000000,BorderStyle=4,Outline=1,Shadow=0,MarginV=30'",
                "-c:a", "copy",
                str(final_output)
            ], check=True)
            logger.info(f"Added subtitles to video: {final_output}")
            
            # Use file with subtitles as the final version
            final_source = final_output
        else:
            logger.warning("No subtitle file found. Using video without subtitles.")
            final_source = processed_video
        
        # Save final video directly to the root directory for simplicity
        root_final_video = Path(project_root) / "final_video.mp4"
        
        # Copy the final video to project root
        try:
            shutil.copy2(str(final_source), str(root_final_video))
            logger.info(f"Final video created at root: {root_final_video}")
        except Exception as e:
            logger.error(f"Failed to copy to root directory: {e}")
            # Continue with other locations even if root copy fails
        
        # Save in standard output location
        final_video = Path(output_dirs.get("videos", ".")) / "final_video.mp4"
        final_video.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(final_source), str(final_video))
        logger.info(f"Final video created at {final_video}")
        
        # Create a more accessible copy in the output directory (for backward compatibility)
        accessible_copy = Path("output") / "final_video.mp4"
        try:
            accessible_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(final_source), str(accessible_copy))
            logger.info(f"Created accessible copy at {accessible_copy}")
        except Exception as e:
            logger.error(f"Failed to create accessible copy: {e}")
        
        return str(final_video)
    except Exception as e:
        logger.exception(f"Error merging videos with audio: {e}")
        return None


def make_make_video(topic, level="beginner", duration=5, dry_run=False, progress_callback=None):
    """Create a complete math tutorial from script to final video."""
    import concurrent.futures
    import time
    from pathlib import Path
    
    # Set duration limits and default progress callback
    duration = max(3, min(int(duration), 15))
    progress_callback = progress_callback or (lambda progress, message: None)
    
    # Get output directories
    output_dirs = get_project_dirs(create_dirs=True)
    
    # Step 1: Generate script
    progress_callback(5.0, "Generating script...")
    script = generate_script.generate_math_tutorial_script(
        topic=topic, 
        level=level, 
        duration=duration, 
        dry_run=dry_run
    )
    
    # Step 2: Extract scenes
    scenes = generate_script.extract_scenes_from_script(script)
    
    # Step 3: Generate Manim code for scenes
    scene_files = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(
                generate_manim_code_parallel, 
                (i, scene_description), 
                output_dirs, 
                manim_generator, 
                dry_run
            ) 
            for i, scene_description in enumerate(scenes)
        ]
        
        for future in concurrent.futures.as_completed(futures):
            idx, scene_path, success = future.result()
            if success and scene_path:
                scene_files.append(scene_path)
    
    # Sort scene files by index
    scene_files.sort(key=lambda p: int(p.stem.split('_')[-1]))
    
    # Step 4: Create timing data
    timing_data = create_timing_data(scenes, output_dirs, duration)
    
    # Step 5: Render scenes
    video_files = render_manim_scenes(scene_files, output_dirs["videos"])
    
    # Step 6: Generate audio narration
    narrator_script = generate_script.clean_script_for_narration(script)
    audio_path = generate_audio_narration(
        text=narrator_script,
        filename="narration.mp3",
        dry_run=dry_run
    )
    
    # Step 7: Generate subtitle file
    subtitle_path = generate_subtitle_file(script, Path(get_subtitle_path()))
    
    # Step 8: Merge videos with audio
    final_video = merge_videos_with_audio(
        video_files=video_files,
        output_dirs=output_dirs,
        audio_path=audio_path,
        subtitle_path=subtitle_path
    )
    
    return final_video

if __name__ == "__main__":
    # Example usage
    make_make_video("Pythagorean Theorem", level=2, duration=5)
