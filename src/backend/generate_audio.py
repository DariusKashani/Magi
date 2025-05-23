import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import re

# Try to import ElevenLabs if available
try:
    from elevenlabs import generate as eleven_generate
    from elevenlabs import set_api_key as eleven_set_api_key
    elevenlabs_available = True
except ImportError:
    elevenlabs_available = False

# Import our script generator function

# ---------------------------
# Setup
# ---------------------------
load_dotenv()  # Load environment variables
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
AUDIO_DIR = OUTPUT_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

# ---------------------------
# Audio Generation Functions
# ---------------------------
def create_silent_audio(output_path: Path, duration_seconds: float) -> Path:
    """Create a silent audio file of specified duration."""
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", str(duration_seconds),
            "-c:a", "aac", "-b:a", "128k",
            str(output_path)
        ], check=True, capture_output=True)
        return output_path
    except Exception as e:
        print(f"Error creating silent audio: {e}")
        return output_path

def generate_audio_narration(text: str, filename: str = None, dry_run: bool = True) -> Path:
    """Generate audio narration (defaults to silent audio to avoid using ElevenLabs API credits)."""
    if not filename:
        filename = f"narration.mp3"
    audio_path = AUDIO_DIR / filename

    if dry_run:
        print(f"Creating silent audio for: {os.path.basename(filename)}")
        estimated_duration = len(text.split()) / 2.5
        return create_silent_audio(audio_path, estimated_duration)

    # ElevenLabs is only used if explicitly requested and dry_run is False
    if not dry_run and elevenlabs_available:
        try:
            api_key = os.environ.get("ELEVENLABS_API_KEY")
            if api_key:
                eleven_set_api_key(api_key)
                audio = eleven_generate(text=text, voice="Rachel")
                with open(audio_path, "wb") as f:
                    f.write(audio)
                print(f"Generated audio with ElevenLabs")
                return audio_path
        except Exception as e:
            print(f"Error using ElevenLabs: {e}")

    # Use silent audio by default
    print("Using silent audio")
    estimated_duration = len(text.split()) / 2.5
    return create_silent_audio(audio_path, estimated_duration)

