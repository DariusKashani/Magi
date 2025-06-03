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

# Also try to import individual components for debugging
try:
    from backend.generate_script import generate_script
    print("✅ Successfully imported generate_script")
except ImportError as e:
    print(f"❌ Failed to import generate_script: {e}")

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

app = FastAPI(title="Magi Video Generator API", version="1.0.0")

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

class VideoRequest(BaseModel):
    topic: str
    level: int = 2
    duration: int = 5
    dry_run: bool = False

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    current_step: str = ""
    error: Optional[str] = None
    video_url: Optional[str] = None

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

@app.post("/api/generate-video")
async def create_video(request: VideoRequest, background_tasks: BackgroundTasks):
    """Start video generation job using make_perfectly_synchronized_video"""
    
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
    
    # Create unique job ID
    job_id = str(uuid.uuid4())
    print(f"🆔 Generated job ID: {job_id}")
    
    # Initialize job with proper structure
    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "status": "started",
            "progress": 0,
            "current_step": "Initializing...",
            "error": None,
            "video_url": None,
            "video_path": None,
            "created_at": time.time(),
            "updated_at": time.time(),
            "request": request.model_dump()
        }
    
    print(f"🆕 Created job {job_id} for topic: '{request.topic}'")
    print(f"📋 Job stored in memory: {job_id in jobs}")
    
    # Start background job using the correct function
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
        "message": "Video generation started using make_perfectly_synchronized_video",
        "estimated_time": f"{request.duration * 2}-{request.duration * 4} minutes"
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
    
    try:
        return FileResponse(
            video_path,
            media_type="video/mp4",
            filename="perfectly_synced_video.mp4"  # Clean filename for download
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
                "status": job["status"],
                "progress": job["progress"],
                "topic": job["request"]["topic"],
                "created_at": job["created_at"],
                "current_step": job["current_step"],
                "error": job.get("error")
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
                "topic": job["request"]["topic"],
                "duration": job["request"]["duration"],
                "created_at": job["created_at"],
                "video_url": job.get("video_url"),
                "video_path": job.get("video_path")
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
    
    with jobs_lock:
        job_count = len(jobs)
        active_jobs = len([j for j in jobs.values() if j["status"] in ["started", "processing"]])
        completed_jobs = len([j for j in jobs.values() if j["status"] == "completed"])
        failed_jobs = len([j for j in jobs.values() if j["status"] == "failed"])
    
    health_data = {
        "status": "healthy", 
        "service": "magi-video-generator",
        "total_jobs": job_count,
        "active_jobs": active_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "video_functions": video_functions_available,
        "timestamp": time.time(),
        "version": "1.0.0"
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
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "debug": "/debug",
        "endpoints": {
            "POST /api/generate-video": "Start video generation using make_perfectly_synchronized_video",
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