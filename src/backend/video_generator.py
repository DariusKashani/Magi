import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from backend.generate_script import generate_script
from backend.generate_scenes import generate_all_scenes_from_script
from backend.generate_audio import generate_audio_narration
from config.paths import VIDEO_OUTPUT_DIR
import threading
import shutil

load_dotenv()

FFMPEG_PATH = shutil.which("ffmpeg")
if FFMPEG_PATH is None:
    raise FileNotFoundError("ffmpeg not found in PATH. Please install it or add it to your PATH.")

def safe_slugify(text: str) -> str:
    """Convert text to safe folder name"""
    import re
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def add_audio_to_video(video_path: Path, audio_path: Path) -> Path:
    """Add audio track to the video"""
    output_path = video_path.parent / "final_video_with_audio.mp4"
    
    cmd = [FFMPEG_PATH, "-y", "-i", str(video_path)]
    
    if audio_path and audio_path.exists():
        cmd += ["-i", str(audio_path)]
        cmd += ["-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0"]
    else:
        print("No audio file found, proceeding without audio")
        cmd += ["-c:v", "copy", "-map", "0:v:0"]
    
    cmd += [str(output_path)]
    print(f"Running ffmpeg command: {' '.join(cmd)}")
    
    subprocess.run(cmd, check=True)
    print(f"Final video created: {output_path}")
    return output_path

def generate_audio_worker(narrator_text: str, dry_run: bool) -> Path:
    """Worker function to generate audio in parallel"""
    print("🎵 [PARALLEL] Starting audio generation...")
    audio_path = generate_audio_narration(text=narrator_text, filename="narration.mp3", dry_run=dry_run)
    if audio_path:
        print(f"✅ [PARALLEL] Audio generated: {audio_path}")
    else:
        print("❌ [PARALLEL] Audio generation failed")
    return audio_path

def make_video(topic: str, level: int = 2, duration: int = 10, dry_run: bool = False):
    """
    Generate complete video with scenes and audio in parallel

    Args:
        topic: Educational topic/question
        level: Sophistication level (1-3)
        duration: Duration in minutes
        dry_run: If True, skip actual audio generation
    """
    print(f"🚀 GENERATING VIDEO for topic: {topic}")

    # Step 1: Generate script
    print("📝 Step 1: Generating script...")
    script = generate_script(topic=topic, duration_minutes=duration, sophistication_level=level)
    print(f"✅ Script generated with {len(script.concepts)} concepts")

    # Prepare narration text for audio generation
    narrator_text = "\n\n".join([c.narration for c in script.concepts])
    print(f"📊 Total narration: {len(narrator_text)} chars, {len(narrator_text.split())} words")

    # Step 2: Start parallel processes
    print("🔄 Step 2: Starting parallel generation...")
    
    # Start audio generation in background thread
    audio_result = {"path": None, "error": None}
    
    def audio_thread():
        try:
            audio_result["path"] = generate_audio_worker(narrator_text, dry_run)
        except Exception as e:
            audio_result["error"] = e
            print(f"❌ [PARALLEL] Audio thread failed: {e}")
    
    # Start audio generation thread
    audio_thread_obj = threading.Thread(target=audio_thread, daemon=True)
    audio_thread_obj.start()
    print("🎵 Audio generation started in parallel...")
    
    # Generate video scenes in main thread
    print("🎬 [MAIN] Generating video scenes...")
    concatenated_video = generate_all_scenes_from_script(script, max_workers=1)
    print("✅ [MAIN] Video scenes rendered")

    # Wait for audio generation to complete
    print("⏳ Waiting for audio generation to complete...")
    audio_thread_obj.join()
    
    audio_path = audio_result["path"]
    if audio_result["error"]:
        print(f"❌ Audio generation failed: {audio_result['error']}")
        audio_path = None
    elif audio_path:
        print(f"✅ Audio generation completed: {audio_path}")
    else:
        print("⚠️ Audio generation completed but no file returned")

    # Step 3: Combine video and audio
    print("🔗 Step 3: Combining video and audio...")
    final_output = add_audio_to_video(concatenated_video, audio_path)

    print("🎉 VIDEO GENERATION COMPLETE")
    print(f"📁 Final output: {final_output}")
    return final_output

# Enhanced version with better error handling and progress tracking
def make_video_enhanced(topic: str, level: int = 2, duration: int = 10, dry_run: bool = False):
    """
    Enhanced version with better progress tracking and error handling
    """
    print(f"🚀 ENHANCED VIDEO GENERATION for topic: {topic}")
    print("=" * 60)

    # Step 1: Generate script
    print("📝 Step 1: Generating script...")
    try:
        script = generate_script(topic=topic, duration_minutes=duration, sophistication_level=level)
        print(f"✅ Script generated with {len(script.concepts)} concepts")
    except Exception as e:
        print(f"❌ Script generation failed: {e}")
        raise

    # Prepare narration text
    narrator_text = "\n\n".join([c.narration for c in script.concepts])
    word_count = len(narrator_text.split())
    char_count = len(narrator_text)
    estimated_audio_time = word_count / 150  # ~150 WPM speaking rate
    
    print(f"📊 Narration stats:")
    print(f"   📝 {char_count:,} characters")
    print(f"   🔤 {word_count:,} words") 
    print(f"   ⏱️ ~{estimated_audio_time:.1f} minutes estimated audio")

    # Step 2: Start parallel processes with progress tracking
    print("\n🔄 Step 2: Starting parallel generation...")
    
    # Shared state for progress tracking
    progress = {
        "audio_status": "Starting...",
        "video_status": "Starting...",
        "audio_complete": False,
        "video_complete": False,
        "audio_path": None,
        "audio_error": None
    }
    
    def audio_thread():
        try:
            progress["audio_status"] = "Generating audio..."
            audio_path = generate_audio_worker(narrator_text, dry_run)
            progress["audio_path"] = audio_path
            progress["audio_status"] = "Complete ✅"
            progress["audio_complete"] = True
        except Exception as e:
            progress["audio_error"] = e
            progress["audio_status"] = f"Failed ❌: {e}"
            print(f"❌ [AUDIO] Generation failed: {e}")
    
    def video_thread():
        try:
            progress["video_status"] = "Generating scenes..."
            concatenated_video = generate_all_scenes_from_script(script, max_workers=1)
            progress["video_path"] = concatenated_video
            progress["video_status"] = "Complete ✅"
            progress["video_complete"] = True
            return concatenated_video
        except Exception as e:
            progress["video_error"] = e
            progress["video_status"] = f"Failed ❌: {e}"
            raise
    
    # Start both threads
    audio_thread_obj = threading.Thread(target=audio_thread, daemon=True)
    audio_thread_obj.start()
    print("🎵 Audio generation started in background...")
    
    # Run video generation in main thread (for better error handling)
    print("🎬 Starting video scene generation...")
    try:
        concatenated_video = video_thread()
        print("✅ Video scenes completed")
    except Exception as e:
        print(f"❌ Video generation failed: {e}")
        # Still wait for audio to complete for cleanup
        audio_thread_obj.join(timeout=10)
        raise

    # Wait for audio with timeout
    print("⏳ Waiting for audio generation...")
    audio_thread_obj.join(timeout=300)  # 5 minute timeout
    
    if audio_thread_obj.is_alive():
        print("⚠️ Audio generation timed out after 5 minutes")
        progress["audio_status"] = "Timed out ⏰"
    
    # Report final status
    print(f"\n📊 GENERATION STATUS:")
    print(f"   🎵 Audio: {progress['audio_status']}")
    print(f"   🎬 Video: {progress['video_status']}")
    
    audio_path = progress.get("audio_path")
    
    # Step 3: Combine if both succeeded
    print("\n🔗 Step 3: Combining video and audio...")
    try:
        final_output = add_audio_to_video(concatenated_video, audio_path)
        print("🎉 VIDEO GENERATION COMPLETE!")
        print(f"📁 Final output: {final_output}")
        return final_output
    except Exception as e:
        print(f"❌ Failed to combine video and audio: {e}")
        print(f"📁 Video only available at: {concatenated_video}")
        raise

if __name__ == "__main__":
    # Use the enhanced version for better feedback
    make_video_enhanced("Teach me what a derivative is?", level=2, duration=10)