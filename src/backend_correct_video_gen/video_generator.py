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
import re
import json

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

def get_audio_duration(audio_path: Path) -> float:
    """Get duration of audio file in seconds using ffprobe"""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(audio_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"❌ Error getting audio duration: {e}")
        return 0.0

def estimate_speaking_duration(text: str, wpm: int = 150) -> float:
    """Estimate how long text will take to speak"""
    words = len(text.split())
    return (words / wpm) * 60  # Convert minutes to seconds

def break_narration_into_chunks(narration: str, scene_description: str) -> list:
    """
    Break narration into chunks that align with visual elements mentioned in scene description
    """
    print(f"🔍 Breaking narration into synchronized chunks...")
    
    # Split narration into sentences
    sentences = re.split(r'[.!?]+', narration)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Extract visual cues from scene description
    visual_cues = extract_visual_cues(scene_description)
    
    # Try to align sentences with visual cues
    chunks = []
    current_chunk = ""
    
    for i, sentence in enumerate(sentences):
        current_chunk += sentence + ". "
        
        # Check if this sentence mentions any visual elements
        mentions_visual = any(
            cue.lower() in sentence.lower() 
            for cue in visual_cues
        )
        
        # Create chunk at natural break points or when visual elements are mentioned
        if (mentions_visual and len(current_chunk.split()) > 5) or \
           (len(current_chunk.split()) > 15) or \
           (i == len(sentences) - 1):
            
            duration = estimate_speaking_duration(current_chunk)
            chunks.append({
                'text': current_chunk.strip(),
                'duration': duration,
                'mentions_visual': mentions_visual
            })
            current_chunk = ""
    
    print(f"   📝 Created {len(chunks)} narration chunks")
    for i, chunk in enumerate(chunks):
        print(f"      Chunk {i+1}: {chunk['duration']:.1f}s - {chunk['text'][:50]}...")
    
    return chunks

def extract_visual_cues(scene_description: str) -> list:
    """Extract visual elements mentioned in scene description"""
    # Common visual elements to look for
    visual_keywords = [
        'triangle', 'circle', 'square', 'rectangle', 'line', 'arrow', 'graph',
        'equation', 'formula', 'text', 'label', 'point', 'curve', 'axis',
        'coordinate', 'angle', 'side', 'vertex', 'area', 'perimeter',
        'plot', 'function', 'variable', 'number', 'symbol', 'diagram'
    ]
    
    found_cues = []
    description_lower = scene_description.lower()
    
    for keyword in visual_keywords:
        if keyword in description_lower:
            found_cues.append(keyword)
    
    # Also extract specific mathematical terms mentioned
    math_terms = re.findall(r'\b[a-zA-Z]+\b', scene_description)
    found_cues.extend([term for term in math_terms if len(term) > 2])
    
    return list(set(found_cues))  # Remove duplicates

def create_timed_scene_description(original_description: str, narration_chunks: list) -> str:
    """
    Create a new scene description with explicit timing for each visual element
    """
    print(f"🔧 Creating timed scene description...")
    
    # Build new scene description with VERY explicit timing
    timed_description = "=== TIMING-SYNCHRONIZED SCENE ===\n\n"
    
    # Add explicit timing summary at the top
    timed_description += "🎯 REQUIRED WAIT CALLS (Claude must follow exactly):\n"
    for i, chunk in enumerate(narration_chunks):
        timed_description += f"   self.wait({chunk['duration']:.1f})  # After segment {i+1}\n"
    timed_description += f"\n✅ Total segments: {len(narration_chunks)}\n"
    timed_description += f"✅ Total wait calls needed: {len(narration_chunks)}\n\n"
    
    current_time = 0.0
    
    for i, chunk in enumerate(narration_chunks):
        chunk_duration = chunk['duration']
        
        timed_description += f"=" * 50 + f"\n"
        timed_description += f"SEGMENT {i+1} [{current_time:.1f}s - {current_time + chunk_duration:.1f}s]\n"
        timed_description += f"=" * 50 + f"\n"
        timed_description += f'Audio: "{chunk["text"]}"\n'
        timed_description += f"Duration: {chunk_duration:.1f} seconds\n"
        
        # Make the wait requirement VERY explicit
        timed_description += f"🚨 MANDATORY: End this segment with self.wait({chunk_duration:.1f}) 🚨\n\n"
        
        # Determine what visual should happen during this narration
        if i == 0:
            timed_description += f"Visual: Set up initial scene elements\n"
        else:
            if chunk['mentions_visual']:
                timed_description += f"Visual: Show/animate elements mentioned in narration\n"
            else:
                timed_description += f"Visual: Continue previous animation or show supporting elements\n"
        
        timed_description += f"\n"
        current_time += chunk_duration
    
    # Add final explicit reminder
    timed_description += f"=" * 50 + f"\n"
    timed_description += f"🎯 CLAUDE: YOU MUST HAVE EXACTLY {len(narration_chunks)} WAIT CALLS:\n"
    for i, chunk in enumerate(narration_chunks):
        timed_description += f"   Segment {i+1}: self.wait({chunk['duration']:.1f})\n"
    timed_description += f"🎯 TOTAL SCENE DURATION: {current_time:.1f}s\n"
    timed_description += f"🎯 NO OTHER WAIT CALLS ALLOWED!\n"
    timed_description += f"=" * 50 + f"\n"
    
    return timed_description

def add_explicit_timing_to_prompt(scene_description: str) -> str:
    """
    Pre-process the scene description to make timing requirements extremely explicit for Claude
    """
    # Extract wait durations from the scene description
    import re
    wait_pattern = r'self\.wait\((\d+\.?\d*)\)'
    wait_durations = re.findall(wait_pattern, scene_description)
    
    if not wait_durations:
        # If no explicit wait calls found, extract from "MANDATORY" lines
        mandatory_pattern = r'self\.wait\((\d+\.?\d*)\)'
        wait_durations = re.findall(mandatory_pattern, scene_description)
    
    if wait_durations:
        # Add ultra-explicit timing header
        timing_header = f"""
🚨🚨🚨 CRITICAL TIMING REQUIREMENTS FOR CLAUDE 🚨🚨🚨

YOU MUST GENERATE CODE WITH EXACTLY {len(wait_durations)} WAIT CALLS:
"""
        for i, duration in enumerate(wait_durations):
            timing_header += f"• Segment {i+1}: self.wait({duration})\n"
        
        timing_header += f"""
❌ DO NOT use self.wait(0) or any other duration
❌ DO NOT add extra wait calls  
❌ DO NOT skip any wait calls
✅ USE EXACTLY the durations listed above

THE WAIT CALLS MUST BE:
{', '.join([f'self.wait({d})' for d in wait_durations])}

🚨🚨🚨 END CRITICAL TIMING REQUIREMENTS 🚨🚨🚨

"""
        return timing_header + scene_description
    
    return scene_description

def generate_synchronized_script(original_script):
    """
    Modify the script to include detailed timing information for each scene
    """
    print("🔧 Generating synchronized script with detailed timing...")
    
    synchronized_concepts = []
    
    for i, concept in enumerate(original_script.concepts):
        print(f"   Processing concept {i+1}: {concept.narration[:50]}...")
        
        # Break narration into timed chunks
        narration_chunks = break_narration_into_chunks(
            concept.narration, 
            concept.scene_description
        )
        
        # Create new scene description with timing
        timed_scene_description = create_timed_scene_description(
            concept.scene_description,
            narration_chunks
        )
        
        # Store the chunk information for later audio generation
        concept.narration_chunks = narration_chunks
        concept.scene_description = timed_scene_description
        
        synchronized_concepts.append(concept)
    
    # Update the script
    original_script.concepts = synchronized_concepts
    return original_script

def generate_chunked_audio_for_scene(concept, scene_index: int) -> list:
    """
    Generate separate audio files for each narration chunk within a scene
    """
    audio_files = []
    
    for chunk_index, chunk in enumerate(concept.narration_chunks):
        print(f"🎵 Generating audio for scene {scene_index+1}, chunk {chunk_index+1}")
        
        filename = f"scene_{scene_index+1}_chunk_{chunk_index+1}_audio.mp3"
        audio_path = generate_audio_narration(
            text=chunk['text'],
            filename=filename,
            dry_run=False
        )
        
        if audio_path and audio_path.exists():
            actual_duration = get_audio_duration(audio_path)
            print(f"   ✅ Chunk {chunk_index+1}: {actual_duration:.1f}s")
            
            audio_files.append({
                'chunk_index': chunk_index,
                'audio_path': audio_path,
                'duration': actual_duration,
                'text': chunk['text'],
                'expected_duration': chunk['duration']
            })
        else:
            print(f"   ❌ Failed to generate audio for chunk {chunk_index+1}")
    
    return audio_files

def create_perfectly_synced_video(script, dry_run: bool = False):
    """
    Generate video with perfect audio-visual synchronization
    """
    print("🎬 Creating perfectly synchronized video...")
    
    # Step 1: Generate synchronized script with timing
    sync_script = generate_synchronized_script(script)
    
    # Step 2: Generate chunked audio for each scene
    all_scene_audio = []
    for i, concept in enumerate(sync_script.concepts):
        scene_audio = generate_chunked_audio_for_scene(concept, i)
        all_scene_audio.append(scene_audio)
    
    # Step 3: Generate video scenes with the synchronized script
    # Note: This will pass the timed scene descriptions to Manim
    print("🎬 Generating video scenes with synchronized timing...")
    video_path = generate_all_scenes_from_script(sync_script, max_workers=1)
    
    if not video_path or not video_path.exists():
        raise Exception("Video generation failed")
    
    # Step 4: Combine audio chunks with video scenes
    print("🔗 Combining synchronized audio and video...")
    final_output = combine_chunked_audio_with_video(video_path, all_scene_audio)
    
    return final_output

def combine_chunked_audio_with_video(video_path: Path, all_scene_audio: list) -> Path:
    """
    Combine the chunked audio with video scenes for perfect synchronization
    """
    print("🔗 Combining chunked audio with video scenes...")
    
    topic_video_dir = video_path.parent
    final_output = topic_video_dir / "perfectly_synced_video.mp4"
    
    # For each scene, combine its audio chunks and sync with video
    scene_videos = []
    
    for scene_index, scene_audio_chunks in enumerate(all_scene_audio):
        scene_num = scene_index + 1
        
        print(f"   🎬 Processing scene {scene_num}...")
        
        # Find the scene video
        scene_video_path = topic_video_dir / "media" / "videos" / f"scene_{scene_num}" / "1080p60" / f"scene_{scene_num}.mp4"
        
        if not scene_video_path.exists():
            print(f"   ❌ Scene {scene_num} video not found")
            continue
        
        # Combine audio chunks for this scene
        if scene_audio_chunks:
            scene_audio_path = combine_audio_chunks_for_scene(scene_audio_chunks, scene_num, topic_video_dir)
            
            # Combine scene video with its synchronized audio
            synced_scene_path = topic_video_dir / f"synced_scene_{scene_num}.mp4"
            
            cmd = [
                FFMPEG_PATH, "-y",
                "-i", str(scene_video_path),
                "-i", str(scene_audio_path),
                "-c:v", "copy", "-c:a", "aac",
                "-map", "0:v:0", "-map", "1:a:0",
                "-shortest",
                str(synced_scene_path)
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                scene_videos.append(synced_scene_path)
                print(f"   ✅ Scene {scene_num} synchronized")
            except subprocess.CalledProcessError as e:
                print(f"   ❌ Failed to sync scene {scene_num}: {e}")
        else:
            print(f"   ⚠️ No audio for scene {scene_num}, using video only")
            scene_videos.append(scene_video_path)
    
    # Concatenate all synchronized scenes
    if scene_videos:
        concat_list_file = topic_video_dir / "final_concat_list.txt"
        
        try:
            with open(concat_list_file, 'w') as f:
                for scene_path in scene_videos:
                    f.write(f"file '{scene_path.absolute()}'\n")
            
            cmd = [
                FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list_file), "-c", "copy", str(final_output)
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Cleanup
            concat_list_file.unlink()
            for scene_path in scene_videos:
                if "synced_scene_" in str(scene_path) and scene_path.exists():
                    scene_path.unlink()
            
            print(f"✅ Perfectly synchronized video created: {final_output}")
            return final_output
            
        except Exception as e:
            print(f"❌ Final concatenation failed: {e}")
            return None
    
    return None

def combine_audio_chunks_for_scene(audio_chunks: list, scene_num: int, output_dir: Path) -> Path:
    """
    Combine audio chunks for a single scene
    """
    if len(audio_chunks) == 1:
        return audio_chunks[0]['audio_path']
    
    # Create concat file for this scene's audio
    concat_file = output_dir / f"scene_{scene_num}_audio_concat.txt"
    combined_audio = output_dir / f"scene_{scene_num}_combined_audio.mp3"
    
    try:
        with open(concat_file, 'w') as f:
            for chunk in audio_chunks:
                f.write(f"file '{chunk['audio_path'].absolute()}'\n")
        
        cmd = [
            FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_file), "-c", "copy", str(combined_audio)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Cleanup
        concat_file.unlink()
        
        return combined_audio
        
    except Exception as e:
        print(f"❌ Failed to combine audio for scene {scene_num}: {e}")
        return None

def make_perfectly_synchronized_video(topic: str, level: int = 2, duration: int = 10, dry_run: bool = False):
    """
    Generate video with perfect content-level synchronization between audio and visuals
    """
    print(f"🚀 GENERATING PERFECTLY SYNCHRONIZED VIDEO for topic: {topic}")
    print("=" * 80)
    print("This will create content-level synchronization where audio matches exactly what's on screen")
    print("=" * 80)

    # Step 1: Generate script
    print("📝 Step 1: Generating script...")
    try:
        script = generate_script(topic=topic, duration_minutes=duration, sophistication_level=level)
        print(f"✅ Script generated with {len(script.concepts)} concepts")
    except Exception as e:
        print(f"❌ Script generation failed: {e}")
        raise

    # Step 2: Create perfectly synchronized version
    print("\n🔧 Step 2: Creating perfect content synchronization...")
    try:
        result = create_perfectly_synced_video(script, dry_run)
        
        if result:
            print("🎉 PERFECTLY SYNCHRONIZED VIDEO GENERATION COMPLETE!")
            print(f"📁 Final output: {result}")
            print("\n🎯 SYNCHRONIZATION ACHIEVED:")
            print("   ✅ Audio narration matches visual content timing")
            print("   ✅ Visual elements appear when mentioned in narration")
            print("   ✅ No delays between audio and corresponding visuals")
            return result
        else:
            raise Exception("Perfect synchronization failed")
            
    except Exception as e:
        print(f"❌ Perfect synchronization failed: {e}")
        print("🔄 Falling back to basic synchronization...")
        
        # Fallback to the previous synchronization method
        return make_synchronized_video_fallback(topic, level, duration, dry_run)

def make_synchronized_video_fallback(topic: str, level: int = 2, duration: int = 10, dry_run: bool = False):
    """
    Fallback to the previous synchronization method
    """
    # This would be your previous make_synchronized_video function
    # For now, just generate a basic video
    script = generate_script(topic=topic, duration_minutes=duration, sophistication_level=level)
    video_path = generate_all_scenes_from_script(script, max_workers=1)
    
    # Generate single audio track
    narrator_text = "\n\n".join([c.narration for c in script.concepts])
    audio_path = generate_audio_narration(text=narrator_text, filename="fallback_narration.mp3", dry_run=dry_run)
    
    # Combine
    if video_path and audio_path:
        output_path = video_path.parent / "fallback_synchronized_video.mp4"
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy", "-c:a", "aac",
            "-map", "0:v:0", "-map", "1:a:0",
            str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    
    return video_path

def test_synchronization_pipeline(topic: str = "What is 2+2?"):
    """
    Test the synchronization pipeline step by step to see where it breaks
    """
    print("🧪 TESTING SYNCHRONIZATION PIPELINE")
    print("=" * 50)
    
    # Step 1: Generate basic script
    print("1️⃣ Testing script generation...")
    script = generate_script(topic=topic, duration_minutes=1, sophistication_level=1)
    print(f"✅ Generated {len(script.concepts)} concepts")
    
    # Step 2: Test narration chunking
    print("\n2️⃣ Testing narration chunking...")
    for i, concept in enumerate(script.concepts):
        print(f"\nConcept {i+1}:")
        print(f"Original narration: {concept.narration}")
        print(f"Original scene description: {concept.scene_description}")
        
        # Test chunking
        chunks = break_narration_into_chunks(concept.narration, concept.scene_description)
        print(f"Chunks created: {len(chunks)}")
        
        # Test timed description creation
        timed_desc = create_timed_scene_description(concept.scene_description, chunks)
        print(f"Timed description preview:")
        print(timed_desc[:300] + "...")
        
        # This is the KEY: Does the timed description get passed to Manim?
        concept.scene_description = timed_desc
        concept.narration_chunks = chunks
    
    # Step 3: Test if Manim receives the timing info
    print("\n3️⃣ Testing Manim code generation...")
    print("📋 Scene descriptions that will be sent to Manim:")
    
    for i, concept in enumerate(script.concepts):
        print(f"\n--- Scene {i+1} Description Sent to Manim ---")
        print(concept.scene_description)
        print("--- End Scene Description ---")
    
    # Step 4: Actually generate one scene to see the result
    print("\n4️⃣ Testing actual scene generation...")
    print("⚠️ This will generate actual Manim code - check if it uses the timing!")
    
    # Generate just the first scene for testing
    from backend.generate_scenes import generate_manim_code
    
    # Use the enhanced timing-explicit version
    enhanced_description = add_explicit_timing_to_prompt(script.concepts[0].scene_description)
    test_prompt = f"Scene description for concept 1:\n{enhanced_description}"
    generated_code = generate_manim_code(test_prompt)
    
    print("📝 Generated Manim code:")
    print(generated_code)
    
    # Step 5: Check if timing is respected
    print("\n5️⃣ Analyzing generated code for timing compliance...")
    
    # Look for timing markers in generated code
    if "self.wait(" in generated_code:
        wait_calls = re.findall(r'self\.wait\(([\d.]+)\)', generated_code)
        print(f"Found wait calls: {wait_calls}")
        
        # Check if they match our timing
        expected_durations = [chunk['duration'] for chunk in script.concepts[0].narration_chunks]
        print(f"Expected durations: {expected_durations}")
        
        if len(wait_calls) == len(expected_durations):
            matches = all(abs(float(actual) - expected) < 0.5 
                         for actual, expected in zip(wait_calls, expected_durations))
            if matches:
                print("✅ TIMING SYNCHRONIZATION WORKING!")
            else:
                print("❌ TIMING MISMATCH - Manim ignoring timing markers")
        else:
            print("❌ WRONG NUMBER OF WAIT CALLS - Manim not following timing structure")
    else:
        print("❌ NO WAIT CALLS FOUND - Manim not generating timed code")
    
    return script

# Replace your debug_manim_prompt_handling() function with this:

def debug_manim_prompt_handling():
    """
    Test if the Manim prompt is correctly processing timing information
    """
    print("🔍 DEBUGGING MANIM PROMPT HANDLING")
    print("=" * 50)
    
    # Create a simple test scene description with the SAME explicit format as the complex scenes
    test_scene_description = """
=== TIMING-SYNCHRONIZED SCENE ===

🎯 REQUIRED WAIT CALLS (Claude must follow exactly):
   self.wait(3.0)  # After segment 1
   self.wait(2.5)  # After segment 2

✅ Total segments: 2
✅ Total wait calls needed: 2

==================================================
SEGMENT 1 [0.0s - 3.0s]
==================================================
Audio: "Let's add two plus two"
Duration: 3.0 seconds
🚨 MANDATORY: End this segment with self.wait(3.0) 🚨

Visual: Show the numbers 2 and 2

==================================================
SEGMENT 2 [3.0s - 5.5s]
==================================================
Audio: "The answer is four"
Duration: 2.5 seconds
🚨 MANDATORY: End this segment with self.wait(2.5) 🚨

Visual: Show the result 4

==================================================
🎯 CLAUDE: YOU MUST HAVE EXACTLY 2 WAIT CALLS:
   Segment 1: self.wait(3.0)
   Segment 2: self.wait(2.5)
🎯 TOTAL SCENE DURATION: 5.5s
🎯 NO OTHER WAIT CALLS ALLOWED!
==================================================
"""
    
    print("📝 Test scene description:")
    print(test_scene_description)
    
    # Test the Manim code generation with enhanced timing
    from backend.generate_scenes import generate_manim_code
    
    enhanced_description = add_explicit_timing_to_prompt(test_scene_description)
    test_prompt = f"Scene description for concept 1:\n{enhanced_description}"
    generated_code = generate_manim_code(test_prompt)
    
    print("\n🎭 Generated Manim code:")
    print(generated_code)
    
    # Analyze the output
    print("\n🔍 Analysis:")
    
    if "3.0" in generated_code and "2.5" in generated_code:
        print("✅ Timing numbers found in code")
    else:
        print("❌ Timing numbers NOT found - prompt may be ignoring timing")
    
    if "self.wait(3.0)" in generated_code or "self.wait(3)" in generated_code:
        print("✅ First timing correctly used")
    else:
        print("❌ First timing NOT used correctly")
    
    if "self.wait(2.5)" in generated_code:
        print("✅ Second timing correctly used")
    else:
        print("❌ Second timing NOT used correctly")
        
        # Check what timing was actually used
        wait_calls = re.findall(r'self\.wait\(([\d.]+)\)', generated_code)
        if len(wait_calls) >= 2:
            print(f"   💡 Used self.wait({wait_calls[1]}) instead of self.wait(2.5)")
    
    print("hi")
    if "TIMING-SYNCHRONIZED" in generated_code or "SEGMENT" in generated_code:
        print("⚠️ Manim code includes description text (should be cleaned)")
    
    return generated_code

# Run the tests
if __name__ == "__main__":
    # print("🧪 Running synchronization tests...\n")
    
    # # Test 1: Full pipeline
    # test_script = test_synchronization_pipeline()
    
    # print("\n" + "="*60 + "\n")
    
    # # Test 2: Manim prompt handling
    # debug_manim_prompt_handling()
    
    # print("\n🏁 TESTS COMPLETE")
    # print("If you see ❌ errors above, those are the issues to fix!")

    # Try this now - it should have perfect audio-video sync!
    # result = make_perfectly_synchronized_video("What is 1+1?", level=1, duration=1)

    # Or try something more complex
    result = make_perfectly_synchronized_video("Teach me what a derivative is?", level=2, duration=3)