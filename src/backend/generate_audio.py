import os
import re
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import shutil
import time

# Try to import ElevenLabs if available
try:
    from elevenlabs.client import ElevenLabs
    elevenlabs_available = True
    elevenlabs_version = "2.x"
    print("✅ ElevenLabs 2.x imported successfully")
except ImportError:
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

# ---------------------------
# Setup
# ---------------------------
load_dotenv()
# Use centralized path configuration
from config.paths import AUDIO_OUTPUT_DIR
OUTPUT_DIR = AUDIO_OUTPUT_DIR.parent
AUDIO_DIR = AUDIO_OUTPUT_DIR
print(f"✅ Using centralized audio directory: {AUDIO_DIR}")

# FFmpeg path
FFMPEG_PATH = shutil.which("ffmpeg")
if FFMPEG_PATH is None:
    print("⚠️ Warning: ffmpeg not found in PATH. Audio generation may fail.")

# ElevenLabs parameters
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
OUTPUT_FORMAT = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128")

# Chunking parameters
MAX_CHUNK_LENGTH = 2500  # Characters per chunk (ElevenLabs works well with ~2500 chars)
CHUNK_DELAY = 1.0        # Seconds to wait between API calls (rate limiting)

def smart_text_chunker(text: str, max_length: int = MAX_CHUNK_LENGTH) -> list[str]:
    """
    Intelligently chunk text at natural break points (sentences, paragraphs).
    Avoids cutting in the middle of sentences or words.
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    remaining_text = text.strip()
    
    while remaining_text:
        if len(remaining_text) <= max_length:
            chunks.append(remaining_text)
            break
        
        # Find the best split point within max_length
        chunk = remaining_text[:max_length]
        
        # Try to split at paragraph break first
        last_paragraph = chunk.rfind('\n\n')
        if last_paragraph > max_length * 0.5:  # Don't make chunks too small
            split_point = last_paragraph + 2
        else:
            # Try to split at sentence end
            sentence_endings = ['. ', '! ', '? ']
            best_split = -1
            
            for ending in sentence_endings:
                last_sentence = chunk.rfind(ending)
                if last_sentence > max_length * 0.5:  # Don't make chunks too small
                    best_split = max(best_split, last_sentence + len(ending))
            
            if best_split > -1:
                split_point = best_split
            else:
                # Fall back to word boundary
                last_space = chunk.rfind(' ')
                split_point = last_space + 1 if last_space > max_length * 0.7 else max_length
        
        chunks.append(remaining_text[:split_point].strip())
        remaining_text = remaining_text[split_point:].strip()
    
    return [chunk for chunk in chunks if chunk]  # Remove empty chunks

def generate_audio_chunk(text: str, chunk_index: int, total_chunks: int) -> bytes:
    """Generate audio for a single text chunk with retry logic."""
    
    print(f"🎵 Generating chunk {chunk_index + 1}/{total_chunks} ({len(text)} chars)")
    
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise Exception("ELEVENLABS_API_KEY not set")
    
    max_retries = 3
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            if elevenlabs_version == "2.x":
                client = ElevenLabs(api_key=api_key)
                audio_response = client.text_to_speech.convert(
                    text=text,
                    voice_id=VOICE_ID,
                    model_id=MODEL_ID,
                    output_format=OUTPUT_FORMAT,
                )
                
                # Handle both generator and bytes response
                if hasattr(audio_response, '__iter__') and not isinstance(audio_response, (bytes, str)):
                    # It's a generator - collect all chunks
                    print(f"🔄 Collecting audio stream for chunk {chunk_index + 1}...")
                    audio_bytes = b''.join(audio_response)
                else:
                    # It's already bytes
                    audio_bytes = audio_response
                    
            else:  # v1.x
                eleven_set_api_key(api_key)
                audio_bytes = eleven_generate(text=text, voice=VOICE_ID)
            
            # Verify we have actual audio data
            if not audio_bytes:
                raise Exception("Empty audio response")
            
            print(f"✅ Chunk {chunk_index + 1} completed ({len(audio_bytes):,} bytes)")
            return audio_bytes
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if "timeout" in error_msg or "timed out" in error_msg:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"⏱️ Timeout on attempt {attempt + 1}, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    raise Exception(f"Chunk timed out after {max_retries} attempts")
            
            elif "rate" in error_msg or "limit" in error_msg:
                if attempt < max_retries - 1:
                    delay = 10 * (attempt + 1)  # Longer delay for rate limits
                    print(f"🚦 Rate limited, waiting {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    raise Exception(f"Rate limited after {max_retries} attempts")
            
            else:
                # Other errors - don't retry
                print(f"❌ Chunk generation error: {e}")
                raise e
    
    return audio_bytes

def combine_audio_chunks(chunk_files: list[Path], output_path: Path) -> Path:
    """Combine multiple audio files into one using ffmpeg."""
    
    if not FFMPEG_PATH:
        raise Exception("ffmpeg not found - cannot combine audio chunks")
    
    if len(chunk_files) == 1:
        # Just rename/copy the single file
        shutil.copy2(chunk_files[0], output_path)
        chunk_files[0].unlink()  # Clean up the temp file
        print(f"✅ Single chunk moved to: {output_path}")
        return output_path
    
    # Create ffmpeg concat file
    concat_file = output_path.parent / f"concat_{output_path.stem}.txt"
    
    try:
        with open(concat_file, 'w') as f:
            for chunk_file in chunk_files:
                f.write(f"file '{chunk_file.absolute()}'\n")
        
        # Combine using ffmpeg
        cmd = [
            FFMPEG_PATH, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path)
        ]
        
        print(f"🔧 Combining {len(chunk_files)} chunks...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        print(f"✅ Combined {len(chunk_files)} chunks into: {output_path}")
        return output_path
        
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg concat failed: {e}")
        print(f"❌ FFmpeg stderr: {e.stderr}")
        raise
        
    finally:
        # Clean up
        if concat_file.exists():
            concat_file.unlink()
        for chunk_file in chunk_files:
            if chunk_file.exists():
                chunk_file.unlink()

def generate_audio_narration(text: str, filename: str = None, dry_run: bool = False) -> Path:
    """Generate audio narration with intelligent chunking to avoid timeouts."""
    
    if not filename:
        filename = "narration.mp3"
    audio_path = AUDIO_DIR / filename

    print(f"🎵 Generating audio for: {filename}")
    print(f"📝 Text length: {len(text):,} chars, {len(text.split()):,} words")
    print(f"📁 Output path: {audio_path}")

    if dry_run:
        print("🔇 Dry run - creating silent audio")
        return create_silent_audio(audio_path, len(text.split()) / 2.5)

    # Check if we need to chunk the text
    if len(text) > MAX_CHUNK_LENGTH:
        print(f"📄 Text is long ({len(text):,} chars), chunking for better reliability...")
        return generate_chunked_audio(text, audio_path)
    else:
        print("📄 Text is short enough for single API call")
        return generate_single_audio(text, audio_path)

def generate_single_audio(text: str, audio_path: Path) -> Path:
    """Generate audio from a single text chunk."""
    
    if not elevenlabs_available:
        print("❌ ElevenLabs not available, falling back to TTS")
        return fallback_to_tts(text, audio_path)
    
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ ELEVENLABS_API_KEY not set, falling back to TTS")
        return fallback_to_tts(text, audio_path)
    
    try:
        print("🎤 Using ElevenLabs for audio generation...")
        audio_bytes = generate_audio_chunk(text, 0, 1)
        
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)
        
        print(f"✅ Generated audio with ElevenLabs: {audio_path}")
        print(f"📊 Final audio size: {audio_path.stat().st_size:,} bytes")
        return audio_path
        
    except Exception as e:
        print(f"❌ Error using ElevenLabs: {e}")
        print("🍎 Falling back to TTS...")
        return fallback_to_tts(text, audio_path)

def generate_chunked_audio(text: str, audio_path: Path) -> Path:
    """Generate audio from multiple text chunks and combine them."""
    
    if not elevenlabs_available:
        print("❌ ElevenLabs not available, falling back to TTS")
        return fallback_to_tts(text, audio_path)
    
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ ELEVENLABS_API_KEY not set, falling back to TTS")
        return fallback_to_tts(text, audio_path)
    
    try:
        # Split text into chunks
        chunks = smart_text_chunker(text, MAX_CHUNK_LENGTH)
        print(f"📄 Split into {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            print(f"   Chunk {i+1}: {len(chunk):,} chars")
        
        # Generate audio for each chunk
        chunk_files = []
        
        for i, chunk in enumerate(chunks):
            try:
                print(f"\n🎵 Processing chunk {i+1}/{len(chunks)}...")
                audio_bytes = generate_audio_chunk(chunk, i, len(chunks))
                
                # Save chunk to temporary file
                chunk_file = audio_path.parent / f"chunk_{i:03d}_{audio_path.stem}.mp3"
                with open(chunk_file, "wb") as f:
                    f.write(audio_bytes)
                
                print(f"💾 Saved chunk to: {chunk_file}")
                chunk_files.append(chunk_file)
                
                # Rate limiting delay between chunks
                if i < len(chunks) - 1:  # Don't delay after the last chunk
                    print(f"⏳ Waiting {CHUNK_DELAY}s before next chunk...")
                    time.sleep(CHUNK_DELAY)
                    
            except Exception as e:
                print(f"❌ Failed to generate chunk {i + 1}: {e}")
                # Clean up any created chunks
                for cf in chunk_files:
                    if cf.exists():
                        cf.unlink()
                print("🍎 Falling back to TTS for entire text...")
                return fallback_to_tts(text, audio_path)
        
        # Combine all chunks
        print(f"\n🔗 Combining {len(chunk_files)} chunks...")
        final_audio = combine_audio_chunks(chunk_files, audio_path)
        print(f"✅ Generated chunked audio with ElevenLabs: {final_audio}")
        print(f"📊 Final audio size: {final_audio.stat().st_size:,} bytes")
        return final_audio
        
    except Exception as e:
        print(f"❌ Error in chunked generation: {e}")
        print("🍎 Falling back to TTS...")
        return fallback_to_tts(text, audio_path)

def fallback_to_tts(text: str, audio_path: Path) -> Path:
    """Fallback to macOS TTS when ElevenLabs fails."""
    
    try:
        print("🍎 Using macOS built-in TTS...")
        temp_aiff = audio_path.parent / f"temp_{audio_path.stem}.aiff"
        
        subprocess.run(["say", "-o", str(temp_aiff), text], check=True, capture_output=True)
        
        if FFMPEG_PATH:
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", str(temp_aiff),
                "-codec:a", "libmp3lame", "-b:a", "128k", str(audio_path)
            ], check=True, capture_output=True)
            temp_aiff.unlink()
            print(f"✅ Generated audio with macOS TTS: {audio_path}")
            return audio_path
        else:
            print(f"❌ ffmpeg missing, returning AIFF: {temp_aiff}")
            return temp_aiff
    except Exception as e:
        print(f"❌ macOS TTS failed: {e}")
        # Create silent audio as final fallback
        return create_silent_audio(audio_path, len(text.split()) / 2.5)

def create_silent_audio(output_path: Path, duration_seconds: float) -> Path:
    """Create silent audio file as final fallback."""
    if FFMPEG_PATH is None:
        print("❌ Cannot create silent audio: ffmpeg not found")
        return output_path
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

# Test function with better debugging
def test_single_chunk():
    """Test with a single, short chunk first"""
    test_text = "This is a short test to verify ElevenLabs is working correctly."
    
    print("🧪 Testing single chunk generation...")
    result = generate_audio_narration(test_text, "test_single.mp3")
    print(f"🎉 Single chunk test completed: {result}")
    
    if result and result.exists():
        print(f"✅ Audio file created successfully: {result.stat().st_size:,} bytes")
    else:
        print("❌ Audio file not created")

def test_chunked():
    """Test with text that requires chunking"""
    test_text = """
    A derivative represents the rate of change of a function at any given point. Think of it like the speedometer in your car - it tells you how fast you're going at that exact moment, not your average speed over a trip.

    When we have a function f(x), its derivative f'(x) tells us how much the function's output changes for a tiny change in input. Mathematically, it's the limit of the ratio of change in y to change in x as that change approaches zero.

    The power rule is one of the most fundamental differentiation techniques. For any function of the form f(x) = x^n, the derivative is f'(x) = n * x^(n-1). This means we bring down the exponent as a coefficient and reduce the exponent by one.

    Let's see this in action with some examples. For f(x) = x², we get f'(x) = 2x. For f(x) = x³, we get f'(x) = 3x². The pattern is consistent and powerful.

    Understanding derivatives opens up a world of applications in physics, economics, and engineering. They help us find maximum and minimum values, analyze motion, and solve optimization problems that appear everywhere in the real world.
    """ * 3  # Make it longer to test chunking
    
    print("🧪 Testing chunked audio generation...")
    result = generate_audio_narration(test_text, "test_chunked.mp3")
    print(f"🎉 Chunked test completed: {result}")

def main():
    print("🚀 AUDIO GENERATION TESTING")
    print("=" * 50)
    
    # Test single chunk first
    test_single_chunk()
    
    print("\n" + "=" * 50)
    
    # Then test chunking
    test_chunked()

if __name__ == "__main__":
    load_dotenv()
    main()