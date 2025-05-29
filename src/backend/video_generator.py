import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from backend.generate_script import generate_script
from backend.generate_scenes import generate_all_scenes_from_script
from backend.generate_audio import generate_audio_narration
from config.paths import VIDEO_OUTPUT_DIR
from config.settings import WORDS_PER_MINUTE

load_dotenv()
import shutil

FFMPEG_PATH = shutil.which("ffmpeg")
if FFMPEG_PATH is None:
    raise FileNotFoundError("ffmpeg not found in PATH. Please install it or add it to your PATH.")

def safe_slugify(text: str) -> str:
    """Convert text to safe folder name"""
    import re
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def format_srt_time(seconds: float) -> str:
    """Format seconds into SRT timestamp format"""
    hrs, remainder = divmod(int(seconds), 3600)
    mins, secs = divmod(remainder, 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"

def generate_subtitle_file(script, output_dir: Path) -> Path:
    """Generate SRT subtitle file using proper timing from settings"""
    srt_path = output_dir / "subtitles.srt"
    words_per_second = WORDS_PER_MINUTE / 60

    with srt_path.open("w", encoding="utf-8") as f:
        start_time = 0.0
        counter = 1
        for concept in script.concepts:
            word_count = len(concept.narration.split())
            duration = max(word_count / words_per_second, 2)
            end_time = start_time + duration

            f.write(f"{counter}\n")
            f.write(f"{format_srt_time(start_time)} --> {format_srt_time(end_time)}\n")
            f.write(concept.narration.strip() + "\n\n")

            start_time = end_time
            counter += 1

    print(f"Subtitles generated: {srt_path}")
    return srt_path

def find_concatenated_video(topic: str) -> Path:
    """Find the concatenated video file"""
    topic_slug = safe_slugify(topic)
    topic_video_dir = VIDEO_OUTPUT_DIR / topic_slug
    possible_names = ["concatenated.mp4", "final.mp4", "merged.mp4", "output.mp4"]

    for name in possible_names:
        video_path = topic_video_dir / name
        if video_path.exists():
            print(f"Found concatenated video: {video_path}")
            return video_path

    mp4_files = list(topic_video_dir.glob("*.mp4"))
    if mp4_files:
        largest_video = max(mp4_files, key=lambda f: f.stat().st_size)
        print(f"Using largest video file as concatenated video: {largest_video}")
        return largest_video

    raise FileNotFoundError(f"No concatenated video found in {topic_video_dir}")

def add_audio_and_subtitles(video_path: Path, audio_path: Path, subtitle_path: Path) -> Path:
    """Add audio track and subtitles to the video"""
    output_path = video_path.parent / "final_video_with_audio_subtitles.mp4"
    cmd = [FFMPEG_PATH, "-y", "-i", str(video_path)]

    if audio_path and audio_path.exists():
        cmd += ["-i", str(audio_path)]
        audio_map = ["-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0"]
    else:
        print("No audio file found, proceeding without audio")
        audio_map = ["-map", "0:v:0"]

    if subtitle_path and subtitle_path.exists():
        cmd += ["-vf", f"subtitles={subtitle_path}"]
    else:
        print("No subtitle file found, proceeding without subtitles")

    cmd += audio_map + ["-c:v", "libx264", str(output_path)]
    print(f"Running ffmpeg command: {' '.join(cmd)}")

    subprocess.run(cmd, check=True)
    print(f"Final video created: {output_path}")
    return output_path

# 05/29/2025 --- Arman Vossoughi

def make_video(topic: str, level: int = 2, duration: int = 10, dry_run: bool = False):
    """
    Generate complete video with scenes, audio, and subtitles

    Args:
        topic: Educational topic/question
        level: Sophistication level (1-3)
        duration: Duration in minutes
        dry_run: If True, skip actual audio generation
    """
    print(f"GENERATING VIDEO for topic: {topic}")

    # Step 1: Generate script
    print("Step 1: Generating script...")
    script = generate_script(topic=topic, duration_minutes=duration, sophistication_level=level)
    print(f"Script generated with {len(script.concepts)} concepts")

    # Step 2: Generate scenes
    print("Step 2: Generating scenes...")
    generate_all_scenes_from_script(script)
    print("Scenes rendered")

    # Step 2.5: Concatenate scene videos
    slugged = safe_slugify(topic)
    video_dir = VIDEO_OUTPUT_DIR / slugged
    video_files = sorted(video_dir.rglob("scene_*.mp4"))
    if not video_files:
        raise FileNotFoundError(f"No scene videos found in {video_dir}")

    list_file = video_dir / "scenes.txt"
    with list_file.open("w") as f:
        for vf in video_files:
            f.write(f"file '{vf.resolve()}'\n")

    concatenated_path = video_dir / "concatenated.mp4"
    subprocess.run([
        FFMPEG_PATH,
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(concatenated_path)
    ], check=True)
    print(f"Concatenated video saved to: {concatenated_path}")

    # Step 3: Find the concatenated video
    print("Step 3: Locating concatenated video...")
    concatenated_video = find_concatenated_video(topic)

    # Step 4: Generate audio narration
    print("Step 4: Generating audio narration...")
    narrator_text = "\n\n".join([c.narration for c in script.concepts])
    audio_path = generate_audio_narration(text=narrator_text, filename="narration.mp3", dry_run=dry_run)
    if audio_path:
        print(f"Audio generated: {audio_path}")

    # Step 5: Generate subtitles
    print("Step 5: Generating subtitles...")
    subtitle_path = generate_subtitle_file(script, video_dir)

    # Step 6: Combine everything
    print("Step 6: Adding audio and subtitles...")
    final_output = add_audio_and_subtitles(concatenated_video, audio_path, subtitle_path)

    print("VIDEO GENERATION COMPLETE")
    print(f"Final output: {final_output}")
    return final_output

if __name__ == "__main__":
    make_video("Teach me what a derivative is?", level=2, duration=10)
