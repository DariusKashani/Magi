import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import re

# Try to import ElevenLabs if available
try:
    from elevenlabs import ElevenLabs
    elevenlabs_available = True
    elevenlabs_version = "2.x"
    print("✅ ElevenLabs 2.x imported successfully")
except ImportError:
    # Try old API (pre 2.0)
    try:
        from elevenlabs import generate as eleven_generate
        from elevenlabs import set_api_key as eleven_set_api_key
        elevenlabs_available = True
        elevenlabs_version = "1.x"
        print("✅ ElevenLabs 1.x imported successfully")
    except ImportError:
        elevenlabs_available = False
        elevenlabs_version = None
        print("❌ ElevenLabs not available")

# Import our script generator function
from backend.generate_script import generate_script

# ---------------------------
# Setup
# ---------------------------
load_dotenv()  # Load environment variables
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
AUDIO_DIR = OUTPUT_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

# FFmpeg path
FFMPEG_PATH = os.path.expanduser("~/bin/ffmpeg")

# ---------------------------
# Audio Generation Functions
# ---------------------------
def create_silent_audio(output_path: Path, duration_seconds: float) -> Path:
    """Create a silent audio file of specified duration."""
    try:
        subprocess.run([
            FFMPEG_PATH, "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration_seconds),
            "-c:a", "libmp3lame", "-b:a", "128k",
            str(output_path)
        ], check=True, capture_output=True)
        print(f"✅ Created silent audio: {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Error creating silent audio: {e}")
        return output_path

def generate_audio_narration(text: str, filename: str = None, dry_run: bool = False) -> Path:
    """Generate audio narration (tries ElevenLabs, falls back to macOS TTS, then silent audio)."""
    if not filename:
        filename = f"narration.mp3"
    audio_path = AUDIO_DIR / filename

    print(f"🎵 Generating audio for: {filename}")
    print(f"📝 Text length: {len(text)} characters, {len(text.split())} words")

    if dry_run:
        print(f"🔇 Dry run mode - creating silent audio")
        estimated_duration = len(text.split()) / 2.5
        return create_silent_audio(audio_path, estimated_duration)

    # Try ElevenLabs first if available
    if elevenlabs_available:
        try:
            api_key = os.environ.get("ELEVENLABS_API_KEY")
            if api_key:
                print(f"🎤 Using ElevenLabs {elevenlabs_version} for audio generation...")
                
                if elevenlabs_version == "2.x":
                    # New API (2.x)
                    client = ElevenLabs(api_key=api_key)
                    audio = client.generate(text=text, voice="Rachel")
                    with open(audio_path, "wb") as f:
                        for chunk in audio:
                            f.write(chunk)
                    print(f"✅ Generated audio with ElevenLabs 2.x: {audio_path}")
                    return audio_path
                else:
                    # Old API (1.x)
                    eleven_set_api_key(api_key)
                    audio = eleven_generate(text=text, voice="Rachel")
                    with open(audio_path, "wb") as f:
                        f.write(audio)
                    print(f"✅ Generated audio with ElevenLabs 1.x: {audio_path}")
                    return audio_path
            else:
                print(f"⚠️ ElevenLabs API key not found in environment")
        except Exception as e:
            print(f"❌ Error using ElevenLabs: {e}")
    else:
        print(f"⚠️ ElevenLabs not available (import failed)")

    # Try macOS built-in TTS
    try:
        print(f"🍎 Trying macOS built-in TTS...")
        temp_aiff = AUDIO_DIR / "temp_narration.aiff"
        
        # Use macOS 'say' command to generate speech
        subprocess.run([
            "say", "-o", str(temp_aiff), text
        ], check=True, capture_output=True)
        
        # Convert AIFF to MP3 using FFmpeg
        subprocess.run([
            FFMPEG_PATH, "-y", "-i", str(temp_aiff), 
            "-codec:a", "libmp3lame", "-b:a", "128k",
            str(audio_path)
        ], check=True, capture_output=True)
        
        # Clean up temp file
        temp_aiff.unlink()
        
        print(f"✅ Generated audio with macOS TTS: {audio_path}")
        return audio_path
        
    except Exception as e:
        print(f"❌ Error using macOS TTS: {e}")

    # Fallback to silent audio
    print("🔇 Falling back to silent audio")
    estimated_duration = len(text.split()) / 2.5
    return create_silent_audio(audio_path, estimated_duration)

def main():
    """Test audio generation with a real script."""
    print("🚀 Testing Audio Generation")
    print("=" * 50)
    
    # Debug ElevenLabs setup
    print(f"🔍 ElevenLabs available: {elevenlabs_available}")
    if elevenlabs_available:
        print(f"🔍 ElevenLabs version: {elevenlabs_version}")
    print(f"🔑 API key set: {'ELEVENLABS_API_KEY' in os.environ}")
    if 'ELEVENLABS_API_KEY' in os.environ:
        key = os.environ['ELEVENLABS_API_KEY']
        print(f"🔑 API key preview: {key[:8]}...{key[-4:] if len(key) > 12 else '[short]'}")
    print()
    
    # Generate a test script
    print("📜 Generating test script...")
    topic = "What is calculus?"
    duration = 3  # Short test script
    level = 2
    
    try:
        script = generate_script(topic=topic, duration_minutes=duration, sophistication_level=level)
        print(f"✅ Script generated with {len(script.concepts)} concepts")
        
        # Extract all narration text
        narration_parts = []
        for i, concept in enumerate(script.concepts, 1):
            print(f"  Scene {i}: {len(concept.narration.split())} words")
            narration_parts.append(concept.narration)
        
        # Combine all narration
        full_narration = "\n\n".join(narration_parts)
        total_words = len(full_narration.split())
        
        print(f"\n📊 Total narration: {total_words} words")
        print(f"🎯 Estimated duration: {total_words / 100:.1f} minutes")
        
        # Generate audio
        print(f"\n🎵 Generating audio...")
        audio_file = generate_audio_narration(
            text=full_narration,
            filename="test_narration.mp3",
            dry_run=False  # Actually generate audio
        )
        
        print(f"\n🎉 SUCCESS!")
        print(f"📁 Audio file: {audio_file}")
        print(f"📂 Full path: {audio_file.absolute()}")
        
        if audio_file.exists():
            file_size = audio_file.stat().st_size
            print(f"📏 File size: {file_size / 1024:.1f} KB")
        
    except Exception as e:
        print(f"❌ Error in main: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()