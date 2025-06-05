from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Callable
import uuid
import os
import time
import uvicorn
import asyncio
import threading
import traceback
from pathlib import Path

# Import your existing video generation code
try:
    from backend.video_generator import make_perfectly_synchronized_video
    print("✅ Successfully imported make_perfectly_synchronized_video")
except ImportError as e:
    print(f"❌ Failed to import make_perfectly_synchronized_video: {e}")
    print("📝 Traceback:")
    traceback.print_exc()
    # Create a mock function for testing
    def make_perfectly_synchronized_video(*args, **kwargs):
        raise Exception("make_perfectly_synchronized_video function not available - import failed")

# Import problem-solving functionality
try:
    from backend.solver_script_gen import generate_problem_script_for_pipeline
    print("✅ Successfully imported generate_problem_script_for_pipeline")
except ImportError as e:
    print(f"❌ Failed to import generate_problem_script_for_pipeline: {e}")
    def generate_problem_script_for_pipeline(*args, **kwargs):
        raise Exception("Problem solving functionality not available - import failed")

try:
    from backend.generate_scenes import generate_all_scenes_from_script
    print("✅ Successfully imported generate_all_scenes_from_script")
except ImportError as e:
    print(f"❌ Failed to import generate_all_scenes_from_script: {e}")

try:
    from backend.generate_audio import generate_audio_narration
    print("✅ Successfully imported generate_audio_narration")
except ImportError as e:
    print(f"❌ Failed to import generate_audio_narration: {e}")

try:
    from backend.generate_script import generate_script
    print("✅ Successfully imported generate_script")
except ImportError as e:
    print(f"❌ Failed to import generate_script: {e}")

app = FastAPI(title="Magi Video Generator API", version="1.1.0")

# Enhanced CORS with more permissive settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job storage with thread safety
jobs = {}
jobs_lock = threading.Lock()

# ========================
# REQUEST MODELS
# ========================

class VideoRequest(BaseModel):
    topic: str
    level: int = 2
    duration: int = 5
    subtitle_style: str = "modern"
    wpm: int = 150
    dry_run: bool = False

class ProblemRequest(BaseModel):
    problem: str
    detail_level: int = 2  # 1=Basic, 2=Standard, 3=Detailed
    duration: int = 3
    subject: str = ""  # Optional subject classification
    problem_type: str = ""  # homework, concept, practice, test_prep
    dry_run: bool = False

class StepByStepRequest(BaseModel):
    problem_text: str
    subject: str
    problem_type: str  # homework, concept, practice, test_prep
    show_work: bool = True
    detail_level: int = 2
    video_duration: int = 3

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    current_step: str = ""
    error: Optional[str] = None
    video_url: Optional[str] = None

# ========================
# UTILITY FUNCTIONS
# ========================

def update_job_progress(job_id: str, progress: int, step: str, status: str = "processing"):
    """Thread-safe job progress update"""
    try:
        with jobs_lock:
            if job_id in jobs:
                jobs[job_id].update({
                    "progress": min(progress, 100),  # Cap at 100%
                    "current_step": step,
                    "status": status,
                    "updated_at": time.time()
                })
                print(f"📊 Job {job_id}: {progress}% - {step}")
    except Exception as e:
        print(f"❌ Error updating job progress: {e}")

def create_job(request_data: dict, job_type: str = "video") -> str:
    """Create a new job and return job ID"""
    job_id = str(uuid.uuid4())
    
    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "started",
            "progress": 0,
            "current_step": "Initializing...",
            "error": None,
            "video_url": None,
            "video_path": None,
            "created_at": time.time(),
            "updated_at": time.time(),
            "request": request_data
        }
    
    return job_id

# ========================
# BACKGROUND TASK FUNCTIONS
# ========================

def generate_video_with_job_id(job_id: str, request: VideoRequest):
    """Generate video using make_perfectly_synchronized_video with progress updates"""
    try:
        print(f"🚀 Starting video generation for job: {job_id}")
        print(f"📋 Request: {request.model_dump()}")
        
        update_job_progress(job_id, 5, "Initializing video generation...", "processing")
        
        # Validate make_perfectly_synchronized_video is available
        if "make_perfectly_synchronized_video" not in globals() or make_perfectly_synchronized_video is None:
            raise Exception("Video generation function not available")
        
        update_job_progress(job_id, 10, "Starting perfectly synchronized video generation...", "processing")
        
        # Call make_perfectly_synchronized_video - this is the correct function to use!
        print(f"🎬 Calling make_perfectly_synchronized_video function...")
        video_path = make_perfectly_synchronized_video(
            topic=request.topic,
            level=request.level,
            duration=request.duration,
            dry_run=request.dry_run
        )
        
        print(f"✅ make_perfectly_synchronized_video returned: {video_path}")
        
        # Validate video path
        if not video_path:
            raise Exception("Video generation returned no path")
        
        if not Path(video_path).exists():
            raise Exception(f"Generated video file not found at: {video_path}")
        
        # Success
        with jobs_lock:
            jobs[job_id].update({
                "status": "completed",
                "progress": 100,
                "current_step": "Video ready for download!",
                "video_path": str(video_path),
                "video_url": f"/api/video/{job_id}",
                "completed_at": time.time()
            })
        
        print(f"✅ Video generation completed for job: {job_id}")
        print(f"📁 Video saved at: {video_path}")
        
    except Exception as e:
        print(f"❌ Video generation failed for job {job_id}: {e}")
        print(f"📝 Full traceback:")
        traceback.print_exc()
        
        with jobs_lock:
            jobs[job_id].update({
                "status": "failed",
                "error": str(e),
                "progress": 0,
                "current_step": f"Generation failed: {str(e)[:100]}...",
                "failed_at": time.time()
            })

def solve_problem_background(job_id: str, request: ProblemRequest):
    """Background task for problem solving video generation"""
    try:
        print(f"🧮 Starting problem solving for job: {job_id}")
        print(f"📋 Problem: {request.problem}")
        
        update_job_progress(job_id, 5, "Analyzing problem structure...", "processing")
        
        # Generate problem-solving script
        update_job_progress(job_id, 15, "Generating solution steps...", "processing")
        script = generate_problem_script_for_pipeline(
            problem=request.problem,
            duration_minutes=request.duration,
            detail_level=request.detail_level
        )
        
        update_job_progress(job_id, 30, f"Generated {len(script.concepts)} solution steps", "processing")
        
        # Generate video scenes
        update_job_progress(job_id, 40, "Creating visual animations...", "processing")
        video_path = generate_all_scenes_from_script(script, max_workers=1)
        
        if not video_path or not Path(video_path).exists():
            raise Exception("Video scene generation failed")
        
        update_job_progress(job_id, 70, "Generating narration audio...", "processing")
        
        # Generate audio narration
        full_narration = "\n\n".join([step.narration for step in script.concepts])
        audio_path = generate_audio_narration(
            text=full_narration,
            filename=f"problem_solution_{job_id}.mp3",
            dry_run=request.dry_run
        )
        
        update_job_progress(job_id, 85, "Combining audio and video...", "processing")
        
        # Combine video and audio
        if audio_path and Path(audio_path).exists():
            import subprocess
            import shutil
            
            FFMPEG_PATH = shutil.which("ffmpeg")
            if FFMPEG_PATH:
                final_output = video_path.parent / f"problem_solution_{job_id}.mp4"
                
                cmd = [
                    FFMPEG_PATH, "-y",
                    "-i", str(video_path),
                    "-i", str(audio_path),
                    "-c:v", "copy", "-c:a", "aac",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-shortest",
                    str(final_output)
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                video_path = final_output
        
        update_job_progress(job_id, 95, "Finalizing video...", "processing")
        
        # Success
        with jobs_lock:
            jobs[job_id].update({
                "status": "completed",
                "progress": 100,
                "current_step": "Problem solved! Video ready for download.",
                "video_path": str(video_path),
                "video_url": f"/api/video/{job_id}",
                "completed_at": time.time()
            })
            
        print(f"✅ Problem solving completed for job: {job_id}")
        
    except Exception as e:
        print(f"❌ Problem solving failed for job {job_id}: {e}")
        print(f"📝 Full traceback:")
        traceback.print_exc()
        
        with jobs_lock:
            jobs[job_id].update({
                "status": "failed",
                "error": str(e),
                "progress": 0,
                "current_step": f"Problem solving failed: {str(e)[:100]}...",
                "failed_at": time.time()
            })

def generate_step_by_step_background(job_id: str, request: StepByStepRequest):
    """Background task for step-by-step problem solution"""
    try:
        print(f"📚 Starting step-by-step solution for job: {job_id}")
        
        update_job_progress(job_id, 10, "Understanding your problem...", "processing")
        
        # Convert StepByStepRequest to ProblemRequest
        problem_request = ProblemRequest(
            problem=request.problem_text,
            detail_level=request.detail_level,
            duration=request.video_duration,
            subject=request.subject,
            problem_type=request.problem_type,
            dry_run=False  # Step-by-step always includes audio
        )
        
        # Use the existing problem solving logic
        solve_problem_background(job_id, problem_request)
        
    except Exception as e:
        print(f"❌ Step-by-step generation failed for job {job_id}: {e}")
        with jobs_lock:
            jobs[job_id].update({
                "status": "failed",
                "error": str(e),
                "progress": 0,
                "current_step": f"Step-by-step generation failed: {str(e)[:100]}...",
                "failed_at": time.time()
            })

# ========================
# API ENDPOINTS
# ========================

@app.post("/api/generate-video")
async def create_video(request: VideoRequest, background_tasks: BackgroundTasks):
    """Start educational video generation job"""
    
    print(f"📨 Received video generation request: {request.model_dump()}")
    
    # Enhanced validation
    if not request.topic or not request.topic.strip():
        print("❌ Validation failed: Empty topic")
        raise HTTPException(status_code=400, detail="Topic is required and cannot be empty")
    
    if request.level not in [1, 2, 3]:
        print(f"❌ Validation failed: Invalid level {request.level}")
        raise HTTPException(status_code=400, detail="Level must be 1, 2, or 3")
    
    if not (1 <= request.duration <= 15):
        print(f"❌ Validation failed: Invalid duration {request.duration}")
        raise HTTPException(status_code=400, detail="Duration must be between 1-15 minutes")
    
    # Create job
    job_id = create_job(request.model_dump(), "educational_video")
    print(f"🆕 Created educational video job {job_id} for topic: '{request.topic}'")
    
    # Start background task
    try:
        background_tasks.add_task(generate_video_with_job_id, job_id, request)
        print(f"🔄 Background task added for job: {job_id}")
    except Exception as e:
        print(f"❌ Failed to add background task: {e}")
        with jobs_lock:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = f"Failed to start background task: {str(e)}"
        raise HTTPException(status_code=500, detail="Failed to start video generation")
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": "Educational video generation started",
        "estimated_time": f"{request.duration * 2}-{request.duration * 4} minutes"
    }

@app.post("/api/solve-problem") 
async def solve_problem(request: ProblemRequest, background_tasks: BackgroundTasks):
    """Generate step-by-step problem solution video"""
    
    print(f"🧮 Received problem solving request: {request.model_dump()}")
    
    # Validation
    if not request.problem or not request.problem.strip():
        raise HTTPException(status_code=400, detail="Problem is required")
    
    if request.detail_level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Detail level must be 1, 2, or 3")
    
    if not (1 <= request.duration <= 10):
        raise HTTPException(status_code=400, detail="Duration must be 1-10 minutes")
    
    # Create job
    job_id = create_job(request.model_dump(), "problem_solving")
    print(f"🆕 Created problem solving job {job_id} for problem: '{request.problem[:50]}...'")
    
    # Start background task
    try:
        background_tasks.add_task(solve_problem_background, job_id, request)
    except Exception as e:
        print(f"❌ Failed to add background task: {e}")
        with jobs_lock:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = f"Failed to start background task: {str(e)}"
        raise HTTPException(status_code=500, detail="Failed to start problem solving")
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Problem-solving video generation started",
        "estimated_time": f"{request.duration * 2}-{request.duration * 4} minutes",
        "problem": request.problem[:100] + "..." if len(request.problem) > 100 else request.problem
    }

@app.post("/api/step-by-step")
async def generate_step_by_step(request: StepByStepRequest, background_tasks: BackgroundTasks):
    """Generate step-by-step solution video (frontend-friendly endpoint)"""
    
    print(f"📚 Received step-by-step request: {request.model_dump()}")
    
    # Validation
    if not request.problem_text or not request.problem_text.strip():
        raise HTTPException(status_code=400, detail="Problem text is required")
    
    if not request.subject:
        raise HTTPException(status_code=400, detail="Subject is required")
    
    if request.detail_level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Detail level must be 1, 2, or 3")
    
    # Create job
    job_id = create_job(request.model_dump(), "step_by_step")
    print(f"🆕 Created step-by-step job {job_id}")
    
    # Start background task
    try:
        background_tasks.add_task(generate_step_by_step_background, job_id, request)
    except Exception as e:
        print(f"❌ Failed to add background task: {e}")
        with jobs_lock:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = f"Failed to start background task: {str(e)}"
        raise HTTPException(status_code=500, detail="Failed to start step-by-step generation")
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": "Step-by-step solution video generation started",
        "estimated_time": f"{request.video_duration * 2}-{request.video_duration * 4} minutes",
        "subject": request.subject,
        "problem_type": request.problem_type
    }

@app.get("/api/video-status/{job_id}")
async def get_video_status(job_id: str):
    """Get video generation status and progress"""
    
    print(f"📋 Status request for job: {job_id}")
    
    with jobs_lock:
        if job_id not in jobs:
            print(f"❌ Job {job_id} not found in {list(jobs.keys())}")
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        job = jobs[job_id].copy()  # Copy to avoid race conditions
    
    print(f"📊 Status for job {job_id}: {job['status']} ({job['progress']}%) - {job['current_step']}")
    
    return JobStatus(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        current_step=job["current_step"],
        error=job.get("error"),
        video_url=job.get("video_url")
    )

@app.get("/api/video/{job_id}")
async def download_video(job_id: str):
    """Download generated video file"""
    
    print(f"📥 Video download request for job: {job_id}")
    
    with jobs_lock:
        if job_id not in jobs:
            print(f"❌ Job {job_id} not found for download")
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        job = jobs[job_id].copy()
    
    if job["status"] != "completed":
        print(f"❌ Video not ready for job {job_id}. Status: {job['status']}")
        raise HTTPException(
            status_code=400, 
            detail=f"Video not ready. Status: {job['status']}"
        )
    
    video_path = job.get("video_path")
    if not video_path:
        print(f"❌ No video path found for job {job_id}")
        raise HTTPException(status_code=404, detail="Video path not found")
    
    if not os.path.exists(video_path):
        print(f"❌ Video file not found at {video_path} for job {job_id}")
        raise HTTPException(status_code=404, detail=f"Video file not found at {video_path}")
    
    print(f"📤 Serving video download for job {job_id}: {video_path}")
    
    # Determine filename based on job type
    job_type = job.get("job_type", "video")
    if job_type == "problem_solving":
        filename = f"magi_problem_solution_{job_id}.mp4"
    elif job_type == "step_by_step":
        filename = f"magi_step_by_step_{job_id}.mp4"
    else:
        filename = f"magi_educational_video_{job_id}.mp4"
    
    try:
        return FileResponse(
            video_path,
            media_type="video/mp4",
            filename=filename
        )
    except Exception as e:
        print(f"❌ Error serving file: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving video file: {str(e)}")

@app.get("/api/jobs")
async def list_jobs():
    """List all jobs (for debugging)"""
    print("📋 Listing all jobs...")
    with jobs_lock:
        job_list = [
            {
                "job_id": job["job_id"],
                "job_type": job.get("job_type", "unknown"),
                "status": job["status"],
                "progress": job["progress"],
                "created_at": job["created_at"],
                "current_step": job["current_step"],
                "error": job.get("error"),
                "request_preview": str(job["request"])[:100] + "..." if len(str(job["request"])) > 100 else str(job["request"])
            }
            for job in jobs.values()
        ]
        print(f"📊 Found {len(job_list)} jobs")
        return {"jobs": job_list}

@app.get("/api/videos")
async def list_videos():
    """List all completed videos"""
    print("🎬 Listing completed videos...")
    with jobs_lock:
        completed_jobs = [
            {
                "job_id": job["job_id"],
                "job_type": job.get("job_type", "unknown"),
                "created_at": job["created_at"],
                "video_url": job.get("video_url"),
                "video_path": job.get("video_path"),
                "request": job.get("request", {})
            }
            for job in jobs.values()
            if job["status"] == "completed"
        ]
    
    print(f"🎬 Found {len(completed_jobs)} completed videos")
    return {"videos": completed_jobs}

@app.delete("/api/job/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running job"""
    print(f"🚫 Cancel request for job: {job_id}")
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job = jobs[job_id]
        if job["status"] in ["completed", "failed"]:
            raise HTTPException(status_code=400, detail=f"Cannot cancel {job['status']} job")
        
        jobs[job_id]["status"] = "cancelled"
        jobs[job_id]["current_step"] = "Cancelled by user"
    
    print(f"✅ Job {job_id} cancelled")
    return {"message": f"Job {job_id} cancelled"}

@app.get("/health")
async def health_check():
    """Enhanced health check with system info"""
    print("🏥 Health check requested")
    
    # Check if video generation functions are available
    video_functions_available = {}
    
    try:
        if "make_perfectly_synchronized_video" in globals() and make_perfectly_synchronized_video is not None:
            video_functions_available["make_perfectly_synchronized_video"] = "✅ Available"
        else:
            video_functions_available["make_perfectly_synchronized_video"] = "❌ Not available"
    except Exception as e:
        video_functions_available["make_perfectly_synchronized_video"] = f"❌ Error: {e}"
    
    try:
        from backend.generate_script import generate_script
        video_functions_available["generate_script"] = "✅ Available"
    except ImportError as e:
        video_functions_available["generate_script"] = f"❌ Import failed: {e}"
    
    try:
        from backend.generate_scenes import generate_all_scenes_from_script
        video_functions_available["generate_scenes"] = "✅ Available"
    except ImportError as e:
        video_functions_available["generate_scenes"] = f"❌ Import failed: {e}"
    
    try:
        from backend.generate_audio import generate_audio_narration
        video_functions_available["generate_audio"] = "✅ Available"
    except ImportError as e:
        video_functions_available["generate_audio"] = f"❌ Import failed: {e}"
    
    try:
        video_functions_available["problem_solving"] = "✅ Available" if "generate_problem_script_for_pipeline" in globals() else "❌ Not available"
    except Exception as e:
        video_functions_available["problem_solving"] = f"❌ Error: {e}"
    
    with jobs_lock:
        job_count = len(jobs)
        active_jobs = len([j for j in jobs.values() if j["status"] in ["started", "processing"]])
        completed_jobs = len([j for j in jobs.values() if j["status"] == "completed"])
        failed_jobs = len([j for j in jobs.values() if j["status"] == "failed"])
        
        # Count by job type
        job_types = {}
        for job in jobs.values():
            job_type = job.get("job_type", "unknown")
            job_types[job_type] = job_types.get(job_type, 0) + 1
    
    health_data = {
        "status": "healthy", 
        "service": "magi-video-generator",
        "version": "1.1.0",
        "features": {
            "educational_videos": True,
            "problem_solving": "generate_problem_script_for_pipeline" in globals(),
            "step_by_step_solutions": True
        },
        "jobs": {
            "total": job_count,
            "active": active_jobs,
            "completed": completed_jobs,
            "failed": failed_jobs,
            "by_type": job_types
        },
        "video_functions": video_functions_available,
        "timestamp": time.time()
    }
    
    print(f"🏥 Health check response: {health_data}")
    return health_data

@app.get("/debug")
async def debug_info():
    """Debug endpoint with detailed system information"""
    import sys
    import platform
    
    # Check imports
    import_status = {}
    
    try:
        from backend.video_generator import make_perfectly_synchronized_video
        import_status["video_generator.make_perfectly_synchronized_video"] = "✅ Available"
    except ImportError as e:
        import_status["video_generator.make_perfectly_synchronized_video"] = f"❌ Failed: {e}"
    
    try:
        from backend.generate_script import generate_script
        import_status["generate_script.generate_script"] = "✅ Available"
    except ImportError as e:
        import_status["generate_script.generate_script"] = f"❌ Failed: {e}"
    
    try:
        from backend.generate_scenes import generate_all_scenes_from_script
        import_status["generate_scenes.generate_all_scenes_from_script"] = "✅ Available"
    except ImportError as e:
        import_status["generate_scenes.generate_all_scenes_from_script"] = f"❌ Failed: {e}"
    
    try:
        from backend.generate_audio import generate_audio_narration
        import_status["generate_audio.generate_audio_narration"] = "✅ Available"
    except ImportError as e:
        import_status["generate_audio.generate_audio_narration"] = f"❌ Failed: {e}"
    
    try:
        from backend.solver_script_gen import generate_problem_script_for_pipeline
        import_status["problem_solver_script_gen.generate_problem_script_for_pipeline"] = "✅ Available"
    except ImportError as e:
        import_status["problem_solver_script_gen.generate_problem_script_for_pipeline"] = f"❌ Failed: {e}"
    
    # Check for required external tools
    external_tools = {}
    import shutil
    
    external_tools["ffmpeg"] = "✅ Available" if shutil.which("ffmpeg") else "❌ Not found"
    external_tools["manim"] = "✅ Available" if shutil.which("manim") else "❌ Not found"
    
    debug_info = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "current_directory": os.getcwd(),
        "import_status": import_status,
        "external_tools": external_tools,
        "environment_variables": {
            k: ("***HIDDEN***" if any(secret in k.upper() for secret in ["KEY", "SECRET", "TOKEN"]) else v)
            for k, v in os.environ.items() 
            if any(keyword in k.upper() for keyword in ["API", "KEY", "PATH", "ELEVEN", "MANIM", "FFMPEG"])
        },
        "jobs_in_memory": list(jobs.keys()) if jobs else [],
        "backend_directory_exists": os.path.exists("backend"),
        "backend_files": [f for f in os.listdir("backend")] if os.path.exists("backend") else []
    }
    
    return debug_info

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Magi Video Generator API",
        "version": "1.1.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "debug": "/debug",
        "features": {
            "educational_videos": "Generate educational videos on any topic",
            "problem_solving": "Step-by-step problem solution videos",
            "step_by_step": "Detailed solution walkthroughs"
        },
        "endpoints": {
            "POST /api/generate-video": "Generate educational videos on topics",
            "POST /api/solve-problem": "Generate step-by-step problem solution videos",
            "POST /api/step-by-step": "Generate detailed solution walkthroughs",
            "GET /api/video-status/{job_id}": "Check generation status",
            "GET /api/video/{job_id}": "Download completed video",
            "GET /api/jobs": "List all jobs",
            "GET /api/videos": "List completed videos"
        }
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"🚨 Unhandled exception: {exc}")
    print(f"📝 Request: {request.method} {request.url}")
    traceback.print_exc()
    
    return {"error": "Internal server error", "detail": str(exc)}, 500

if __name__ == "__main__":
    print("🚀 Starting Magi Video Generator API...")
    print("📍 API available at: http://localhost:8000")
    print("📚 API docs: http://localhost:8000/docs")
    print("🏥 Health check: http://localhost:8000/health")
    print("🔍 Debug info: http://localhost:8000/debug")
    
    print("\n🎯 Available Features:")
    print("  ✅ Educational video generation (/api/generate-video)")
    print("  ✅ Problem solving videos (/api/solve-problem)")
    print("  ✅ Step-by-step solutions (/api/step-by-step)")
    
    # Test imports on startup
    print("\n🔍 Testing imports on startup...")
    try:
        from backend.video_generator import make_perfectly_synchronized_video
        print("✅ make_perfectly_synchronized_video imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import make_perfectly_synchronized_video: {e}")
    
    try:
        from backend.generate_script import generate_script
        print("✅ generate_script imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import generate_script: {e}")
    
    try:
        from backend.generate_scenes import generate_all_scenes_from_script  
        print("✅ generate_all_scenes_from_script imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import generate_all_scenes_from_script: {e}")
        
    try:
        from backend.generate_audio import generate_audio_narration
        print("✅ generate_audio_narration imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import generate_audio_narration: {e}")
    
    try:
        from backend.solver_script_gen import generate_problem_script_for_pipeline
        print("✅ problem solving functionality imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import problem solving functionality: {e}")
    
    try:
        import uvicorn
        print("✅ uvicorn available")
    except ImportError:
        print("❌ uvicorn not available")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_level="info",
        reload=False  # Disable reload to avoid import issues
    )