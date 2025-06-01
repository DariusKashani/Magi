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
import time

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

def add_audio_to_video(video_path: Path, audio_path: Path, progress_callback=None) -> Path:
    """Add audio track to the video"""
    if progress_callback:
        progress_callback(85, "Combining video and audio...")
    
    output_path = video_path.parent / "final_video_with_audio.mp4"
    
    cmd = [FFMPEG_PATH, "-y", "-i", str(video_path)]
    
    if audio_path and audio_path.exists():
        cmd += ["-i", str(audio_path)]
        cmd += ["-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0"]
    else:
        print("⚠️ No audio file found, proceeding without audio")
        cmd += ["-c:v", "copy", "-map", "0:v:0"]
    
    cmd += [str(output_path)]
    print(f"Running ffmpeg command: {' '.join(cmd)}")
    
    subprocess.run(cmd, check=True)
    print(f"Final video created: {output_path}")
    
    if progress_callback:
        progress_callback(95, "Video finalization complete...")
    
    return output_path

def generate_audio_worker(narrator_text: str, dry_run: bool, progress_callback=None) -> Path:
    """Worker function to generate audio in parallel"""
    print("🎵 [PARALLEL] Starting audio generation...")
    if progress_callback:
        progress_callback(35, "Synthesizing audio narration...")
    
    audio_path = generate_audio_narration(text=narrator_text, filename="narration.mp3", dry_run=dry_run)
    
    if audio_path:
        print(f"✅ [PARALLEL] Audio generated: {audio_path}")
        if progress_callback:
            progress_callback(65, "Audio narration complete...")
    else:
        print("❌ [PARALLEL] Audio generation failed")
    
    return audio_path

def make_video(topic: str, level: int = 2, duration: int = 10, dry_run: bool = False, 
               subtitle_style: str = "modern", wpm: int = 150, use_legacy_srt: bool = False,
               progress_callback=None, job_id: str = None):
    """
    Generate complete video with scenes and audio in parallel

    Args:
        topic: Educational topic/question
        level: Sophistication level (1-3)
        duration: Duration in minutes
        dry_run: If True, skip actual audio generation
        subtitle_style: Style for subtitles (modern, clean, typewriter)
        wpm: Words per minute for narration timing
        use_legacy_srt: Use legacy SRT subtitles
        progress_callback: Function to call with (progress_percent, status_message)
        job_id: Unique identifier for this job (for consistent file naming)
    """
    print(f"🚀 GENERATING VIDEO for topic: {topic}")
    
    # Use job_id for folder naming if provided, otherwise use topic
    folder_name = job_id if job_id else safe_slugify(topic)
    print(f"📁 Using folder name: {folder_name}")

    # Step 1: Generate script
    print("📝 Step 1: Generating script...")
    if progress_callback:
        progress_callback(5, "Analyzing your request...")
    
    try:
        script = generate_script(topic=topic, duration_minutes=duration, sophistication_level=level)
        print(f"✅ Script generated with {len(script.concepts)} concepts")
        if progress_callback:
            progress_callback(15, "Educational script generated...")
    except Exception as e:
        if progress_callback:
            progress_callback(0, f"Script generation failed: {str(e)}")
        raise

    # Prepare narration text for audio generation
    narrator_text = "\n\n".join([c.narration for c in script.concepts])
    word_count = len(narrator_text.split())
    char_count = len(narrator_text)
    print(f"📊 Total narration: {char_count} chars, {word_count} words")

    # Step 2: Start parallel processes
    print("🔄 Step 2: Starting parallel generation...")
    if progress_callback:
        progress_callback(20, "Starting video and audio generation...")
    
    # Start audio generation in background thread
    audio_result = {"path": None, "error": None}
    
    def audio_thread():
        try:
            audio_result["path"] = generate_audio_worker(narrator_text, dry_run, progress_callback)
        except Exception as e:
            audio_result["error"] = e
            print(f"❌ [PARALLEL] Audio thread failed: {e}")
    
    # Start audio generation thread
    audio_thread_obj = threading.Thread(target=audio_thread, daemon=True)
    audio_thread_obj.start()
    print("🎵 Audio generation started in parallel...")
    
    # Generate video scenes in main thread
    print("🎬 [MAIN] Generating video scenes...")
    if progress_callback:
        progress_callback(25, "Creating visual scenes...")
    
    try:
        # Pass the folder_name (job_id) to ensure consistent naming
        concatenated_video = generate_all_scenes_from_script(
            script, 
            max_workers=1, 
            custom_output_name=folder_name
        )
        print("✅ [MAIN] Video scenes rendered")
        if progress_callback:
            progress_callback(55, "Visual scenes complete...")
    except Exception as e:
        if progress_callback:
            progress_callback(0, f"Video generation failed: {str(e)}")
        # Still wait for audio thread to complete for cleanup
        audio_thread_obj.join(timeout=10)
        raise

    # Wait for audio generation to complete
    print("⏳ Waiting for audio generation to complete...")
    if progress_callback:
        progress_callback(70, "Finalizing audio...")
    
    audio_thread_obj.join(timeout=300)  # 5 minute timeout
    
    if audio_thread_obj.is_alive():
        print("⚠️ Audio generation timed out after 5 minutes")
        if progress_callback:
            progress_callback(75, "Audio generation timed out, proceeding with video only...")
    
    audio_path = audio_result["path"]
    if audio_result["error"]:
        print(f"❌ Audio generation failed: {audio_result['error']}")
        if progress_callback:
            progress_callback(75, "Audio failed, proceeding with video only...")
        audio_path = None
    elif audio_path:
        print(f"✅ Audio generation completed: {audio_path}")
    else:
        print("⚠️ Audio generation completed but no file returned")

    # Step 3: Combine video and audio
    print("🔗 Step 3: Combining video and audio...")
    if progress_callback:
        progress_callback(80, "Adding audio to video...")
    
    try:
        final_output = add_audio_to_video(concatenated_video, audio_path, progress_callback)
        
        if progress_callback:
            progress_callback(100, "Video ready for download!")
        
        print("🎉 VIDEO GENERATION COMPLETE")
        print(f"📁 Final output: {final_output}")
        return final_output
        
    except Exception as e:
        if progress_callback:
            progress_callback(90, f"Audio combination failed, video-only available")
        print(f"❌ Failed to combine video and audio: {e}")
        print(f"📁 Video only available at: {concatenated_video}")
        
        # Return video-only version if audio combination fails
        return concatenated_video

def make_video_with_detailed_progress(topic: str, level: int = 2, duration: int = 10, 
                                    dry_run: bool = False, progress_callback=None, job_id: str = None):
    """
    Enhanced version with more detailed progress tracking
    """
    print(f"🚀 DETAILED VIDEO GENERATION for topic: {topic}")
    print("=" * 60)

    # Use job_id for consistent naming
    folder_name = job_id if job_id else safe_slugify(topic)
    
    try:
        # Step 1: Script Generation (0% -> 15%)
        if progress_callback:
            progress_callback(0, "Starting script generation...")
        
        script = generate_script(topic=topic, duration_minutes=duration, sophistication_level=level)
        
        if progress_callback:
            progress_callback(10, f"Script complete: {len(script.concepts)} concepts")
        
        # Prepare narration
        narrator_text = "\n\n".join([c.narration for c in script.concepts])
        word_count = len(narrator_text.split())
        estimated_time = word_count / 150
        
        print(f"📊 Script Stats: {word_count} words, ~{estimated_time:.1f}min audio")
        
        if progress_callback:
            progress_callback(15, f"Prepared {word_count} words for narration")

        # Step 2: Parallel Generation Setup (15% -> 25%)
        if progress_callback:
            progress_callback(20, "Starting parallel audio and video generation...")
        
        # Shared progress tracking
        progress_state = {
            "audio_progress": 0,
            "video_progress": 0,
            "audio_complete": False,
            "video_complete": False,
            "audio_path": None,
            "video_path": None,
            "errors": []
        }
        
        def enhanced_audio_thread():
            try:
                if progress_callback:
                    progress_callback(25, "Synthesizing audio narration...")
                
                audio_path = generate_audio_narration(text=narrator_text, filename="narration.mp3", dry_run=dry_run)
                progress_state["audio_path"] = audio_path
                progress_state["audio_complete"] = True
                
                if progress_callback:
                    progress_callback(50, "Audio narration complete")
                    
            except Exception as e:
                progress_state["errors"].append(f"Audio: {e}")
                print(f"❌ Audio generation failed: {e}")
        
        # Start enhanced audio generation
        audio_thread_obj = threading.Thread(target=enhanced_audio_thread, daemon=True)
        audio_thread_obj.start()
        
        # Step 3: Video Generation (25% -> 60%)
        if progress_callback:
            progress_callback(30, "Generating visual scenes...")
        
        concatenated_video = generate_all_scenes_from_script(
            script, 
            max_workers=1, 
            custom_output_name=folder_name
        )
        
        progress_state["video_path"] = concatenated_video
        progress_state["video_complete"] = True
        
        if progress_callback:
            progress_callback(60, "Visual scenes complete")
        
        # Step 4: Wait for Audio (60% -> 70%)
        if progress_callback:
            progress_callback(65, "Waiting for audio completion...")
        
        audio_thread_obj.join(timeout=300)
        
        if progress_callback:
            progress_callback(70, "Audio processing finished")
        
        # Step 5: Final Assembly (70% -> 100%)
        if progress_callback:
            progress_callback(75, "Combining video and audio...")
        
        audio_path = progress_state["audio_path"]
        final_output = add_audio_to_video(concatenated_video, audio_path, progress_callback)
        
        if progress_callback:
            progress_callback(100, "Video ready for download!")
        
        print("🎉 DETAILED VIDEO GENERATION COMPLETE!")
        print(f"📁 Final output: {final_output}")
        
        return final_output
        
    except Exception as e:
        if progress_callback:
            progress_callback(0, f"Generation failed: {str(e)}")
        print(f"❌ Video generation failed: {e}")
        raise

if __name__ == "__main__":
    # Test with detailed progress
    def test_progress(progress, message):
        print(f"[{progress:3d}%] {message}")
    
    make_video_with_detailed_progress(
        "Explain derivatives in calculus", 
        level=2, 
        duration=5, 
        progress_callback=test_progress,
        job_id="test-job-123"
    )