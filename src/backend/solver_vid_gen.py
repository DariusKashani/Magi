import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Import the new problem-solving script generator
from backend.solver_script_gen import generate_problem_script_for_pipeline

# Keep existing imports for the rest of the pipeline
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

def make_problem_solving_video(problem: str, detail_level: int = 2, duration: int = 3, dry_run: bool = False):
    """
    Generate a step-by-step problem-solving video
    
    Args:
        problem: The specific problem to solve (e.g., "Solve: 2x + 5 = 13")
        detail_level: Level of detail (1=Basic, 2=Standard, 3=Detailed)
        duration: Video duration in minutes
        dry_run: If True, creates silent audio for testing
    """
    print(f"🧮 GENERATING PROBLEM-SOLVING VIDEO")
    print("=" * 80)
    print(f"Problem: {problem}")
    print(f"Detail Level: {detail_level} ({'Basic' if detail_level == 1 else 'Standard' if detail_level == 2 else 'Detailed'})")
    print(f"Duration: {duration} minutes")
    print("=" * 80)

    # Step 1: Generate problem-solving script
    print("📝 Step 1: Generating problem-solving script...")
    try:
        # Use the new problem-solving script generator that returns a Script object
        script = generate_problem_script_for_pipeline(
            problem=problem, 
            duration_minutes=duration, 
            detail_level=detail_level
        )
        print(f"✅ Solution script generated with {len(script.concepts)} solution steps")
        
        # Show the solution steps
        for i, step in enumerate(script.concepts, 1):
            print(f"   Step {i}: {step.narration[:60]}...")
            
    except Exception as e:
        print(f"❌ Script generation failed: {e}")
        raise

    # Step 2: Generate video scenes (using existing pipeline)
    print("\n🎬 Step 2: Generating solution step videos...")
    try:
        video_path = generate_all_scenes_from_script(script, max_workers=1)
        
        if not video_path or not video_path.exists():
            raise Exception("Video generation failed")
            
        print(f"✅ Solution videos generated: {video_path}")
        
    except Exception as e:
        print(f"❌ Video generation failed: {e}")
        raise

    # Step 3: Generate narration audio (using existing pipeline)
    print("\n🎵 Step 3: Generating solution narration...")
    try:
        # Combine all step narrations
        full_narration = "\n\n".join([step.narration for step in script.concepts])
        
        audio_path = generate_audio_narration(
            text=full_narration, 
            filename="problem_solution_narration.mp3", 
            dry_run=dry_run
        )
        
        if not audio_path or not audio_path.exists():
            raise Exception("Audio generation failed")
            
        print(f"✅ Solution narration generated: {audio_path}")
        
    except Exception as e:
        print(f"❌ Audio generation failed: {e}")
        raise

    # Step 4: Combine video and audio
    print("\n🔗 Step 4: Combining video and audio...")
    try:
        final_output = video_path.parent / "problem_solution_video.mp4"
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy", "-c:a", "aac",
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest",  # End when the shorter stream ends
            str(final_output)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        print(f"✅ Final problem-solving video created: {final_output}")
        
        # Show summary
        print("\n🎉 PROBLEM-SOLVING VIDEO GENERATION COMPLETE!")
        print(f"📁 Final output: {final_output}")
        print(f"🧮 Problem solved: {problem}")
        print(f"📊 Solution steps: {len(script.concepts)}")
        print(f"⏱️ Duration: ~{duration} minutes")
        
        return final_output
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Video/audio combination failed: {e}")
        raise
    except Exception as e:
        print(f"❌ Final processing failed: {e}")
        raise

def make_problem_solving_video_with_perfect_sync(problem: str, detail_level: int = 2, duration: int = 3, dry_run: bool = False):
    """
    Generate problem-solving video with perfect step-by-step synchronization
    This uses the advanced synchronization from the original system
    """
    print(f"🧮 GENERATING PERFECTLY SYNCHRONIZED PROBLEM-SOLVING VIDEO")
    print("=" * 80)
    print(f"Problem: {problem}")
    print("This will create perfect synchronization where audio matches each solution step exactly")
    print("=" * 80)

    # Step 1: Generate problem-solving script
    script = generate_problem_script_for_pipeline(problem, duration, detail_level)
    
    # Step 2: Use the existing perfect synchronization system
    # Import the advanced synchronization functions
    from backend.video_generator import create_perfectly_synced_video
    
    try:
        result = create_perfectly_synced_video(script, dry_run)
        
        if result:
            print("🎉 PERFECTLY SYNCHRONIZED PROBLEM-SOLVING VIDEO COMPLETE!")
            print(f"📁 Final output: {result}")
            print("\n🎯 SYNCHRONIZATION ACHIEVED:")
            print("   ✅ Audio narration matches each solution step timing")
            print("   ✅ Visual math work appears when mentioned in narration") 
            print("   ✅ No delays between audio and corresponding visual steps")
            return result
        else:
            raise Exception("Perfect synchronization failed")
            
    except Exception as e:
        print(f"❌ Perfect synchronization failed: {e}")
        print("🔄 Falling back to basic problem-solving video...")
        
        # Fallback to basic problem-solving video
        return make_problem_solving_video(problem, detail_level, duration, dry_run)

# Integration with existing API
def update_api_for_problem_solving():
    """
    Shows how to integrate with the existing API
    """
    return """
    # Add to api_server.py:
    
    class ProblemRequest(BaseModel):
        problem: str
        detail_level: int = 2
        duration: int = 3
        dry_run: bool = False

    @app.post("/api/solve-problem")
    async def solve_problem(request: ProblemRequest, background_tasks: BackgroundTasks):
        '''Generate step-by-step problem solution video'''
        
        if not request.problem or not request.problem.strip():
            raise HTTPException(status_code=400, detail="Problem is required")
        
        job_id = str(uuid.uuid4())
        
        # Store job
        with jobs_lock:
            jobs[job_id] = {
                "job_id": job_id,
                "status": "started",
                "progress": 0,
                "current_step": "Starting problem solving...",
                "error": None,
                "video_url": None,
                "video_path": None,
                "created_at": time.time(),
                "request": request.model_dump()
            }
        
        # Start background task
        background_tasks.add_task(solve_problem_background, job_id, request)
        
        return {"job_id": job_id, "status": "started", "message": "Problem-solving video generation started"}
    
    def solve_problem_background(job_id: str, request: ProblemRequest):
        try:
            video_path = make_problem_solving_video_with_perfect_sync(
                problem=request.problem,
                detail_level=request.detail_level,
                duration=request.duration,
                dry_run=request.dry_run
            )
            
            # Update job as completed
            with jobs_lock:
                jobs[job_id].update({
                    "status": "completed",
                    "progress": 100,
                    "current_step": "Problem solved! Video ready for download.",
                    "video_path": str(video_path),
                    "video_url": f"/api/video/{job_id}"
                })
                
        except Exception as e:
            with jobs_lock:
                jobs[job_id].update({
                    "status": "failed",
                    "error": str(e),
                    "current_step": f"Problem solving failed: {str(e)}"
                })
    """

# Example usage and testing
def test_problem_solving():
    """Test the problem-solving video generation"""
    
    test_problems = [
        "Solve: 2x + 5 = 13",
        "Find the derivative of x^2 + 3x + 1",
        "Simplify: (x^2 - 4)/(x - 2)",
        "Solve the system: x + y = 5, 2x - y = 1"
    ]
    
    print("🧪 TESTING PROBLEM-SOLVING VIDEO GENERATION")
    print("=" * 50)
    
    for i, problem in enumerate(test_problems, 1):
        print(f"\n🧮 Test {i}: {problem}")
        
        try:
            # Test script generation only
            script = generate_problem_script_for_pipeline(problem, duration_minutes=2, detail_level=2)
            print(f"✅ Script generated with {len(script.concepts)} steps")
            
            # Show first step
            if script.concepts:
                print(f"   First step: {script.concepts[0].narration[:100]}...")
                
        except Exception as e:
            print(f"❌ Failed: {e}")
    
    # Try generating a full video for one problem
    print(f"\n🎬 Generating full video for: {test_problems[0]}")
    try:
        result = make_problem_solving_video(
            problem=test_problems[0],
            detail_level=2,
            duration=2,
            dry_run=True  # Use dry_run for testing
        )
        print(f"✅ Test video generated: {result}")
    except Exception as e:
        print(f"❌ Test video failed: {e}")

if __name__ == "__main__":
    # Run tests
    test_problem_solving()
    
    # Example: Generate a real problem-solving video
    # result = make_problem_solving_video_with_perfect_sync("Solve: 3x - 7 = 14", detail_level=2, duration=3)