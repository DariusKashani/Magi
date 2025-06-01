from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional  # Add this import
import uuid
import os
import time
import uvicorn
import asyncio
import threading

# Import your existing video generation code
try:
    from backend.video_generator import make_video
except ImportError:
    from backend.video_generator import make_video

app = FastAPI()

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:3000"],
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
    subtitle_style: str = "modern"
    wpm: int = 150
    dry_run: bool = False

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    current_step: str = ""
    error: Optional[str] = None      # FIXED: Made Optional
    video_url: Optional[str] = None  # FIXED: Made Optional

def update_job_progress(job_id: str, progress: int, step: str, status: str = "processing"):
    """Thread-safe job progress update"""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update({
                "progress": min(progress, 100),  # Cap at 100%
                "current_step": step,
                "status": status,
                "updated_at": time.time()
            })
            print(f"📊 Job {job_id}: {progress}% - {step}")

def generate_video_with_job_id(job_id: str, request: VideoRequest):
    """Generate video with proper job ID tracking"""
    try:
        print(f"🚀 Starting video generation for job: {job_id}")
        update_job_progress(job_id, 0, "Initializing video generation...", "processing")
        
        # Create progress callback that updates our job
        def progress_callback(progress: int, step: str):
            update_job_progress(job_id, progress, step, "processing")
        
        # Call make_video with progress callback and job_id for naming
        video_path = make_video(
            topic=request.topic,
            level=request.level,
            duration=request.duration,
            dry_run=request.dry_run,
            subtitle_style=request.subtitle_style,
            wpm=request.wpm,
            progress_callback=progress_callback,
            job_id=job_id  # Pass job_id for consistent naming
        )
        
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
    """Start video generation job"""
    
    # Enhanced validation
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="Topic is required")
    
    if request.level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Level must be 1, 2, or 3")
    
    if not (2 <= request.duration <= 15):
        raise HTTPException(status_code=400, detail="Duration must be between 2-15 minutes")
    
    # Create unique job ID
    job_id = str(uuid.uuid4())
    
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
            "request": request.model_dump()  # FIXED: Use model_dump() instead of dict()
        }
    
    print(f"🆕 Created job {job_id} for topic: '{request.topic}'")
    
    # Start background job
    background_tasks.add_task(generate_video_with_job_id, job_id, request)
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": "Video generation started",
        "estimated_time": f"{request.duration * 2}-{request.duration * 3} minutes"
    }

@app.get("/api/video-status/{job_id}")
async def get_video_status(job_id: str):
    """Get video generation status and progress"""
    
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        job = jobs[job_id].copy()  # Copy to avoid race conditions
    
    print(f"📋 Status request for job {job_id}: {job['status']} ({job['progress']}%)")
    
    return JobStatus(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        current_step=job["current_step"],
        error=job.get("error"),      # These are now properly Optional
        video_url=job.get("video_url")
    )

@app.get("/api/video/{job_id}")
async def download_video(job_id: str):
    """Download generated video file"""
    
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        job = jobs[job_id].copy()
    
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Video not ready. Status: {job['status']}"
        )
    
    video_path = job.get("video_path")
    if not video_path:
        raise HTTPException(status_code=404, detail="Video path not found")
    
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found at {video_path}")
    
    print(f"📥 Serving video download for job {job_id}: {video_path}")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"magi_video_{job_id}.mp4"
    )

@app.get("/api/jobs")
async def list_jobs():
    """List all jobs (for debugging)"""
    with jobs_lock:
        return {
            "jobs": [
                {
                    "job_id": job["job_id"],
                    "status": job["status"],
                    "progress": job["progress"],
                    "topic": job["request"]["topic"],
                    "created_at": job["created_at"],
                    "current_step": job["current_step"]
                }
                for job in jobs.values()
            ]
        }

@app.get("/api/videos")
async def list_videos():
    """List all completed videos"""
    with jobs_lock:
        completed_jobs = [
            {
                "job_id": job["job_id"],
                "topic": job["request"]["topic"],
                "duration": job["request"]["duration"],
                "created_at": job["created_at"],
                "video_url": job.get("video_url")
            }
            for job in jobs.values()
            if job["status"] == "completed"
        ]
    
    return {"videos": completed_jobs}

@app.delete("/api/job/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running job"""
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job = jobs[job_id]
        if job["status"] in ["completed", "failed"]:
            raise HTTPException(status_code=400, detail=f"Cannot cancel {job['status']} job")
        
        jobs[job_id]["status"] = "cancelled"
        jobs[job_id]["current_step"] = "Cancelled by user"
    
    return {"message": f"Job {job_id} cancelled"}

@app.get("/health")
async def health_check():
    with jobs_lock:
        job_count = len(jobs)
        active_jobs = len([j for j in jobs.values() if j["status"] in ["started", "processing"]])
    
    return {
        "status": "healthy", 
        "service": "magi-video-generator",
        "total_jobs": job_count,
        "active_jobs": active_jobs,
        "timestamp": time.time()
    }

@app.get("/")
async def root():
    return {
        "message": "Magi Video Generator API",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    print("🚀 Starting Magi Video Generator API...")
    print("📍 API available at: http://localhost:8000")
    print("📚 API docs: http://localhost:8000/docs")
    print("🏥 Health check: http://localhost:8000/health")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")