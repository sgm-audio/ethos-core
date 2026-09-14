"""
ETHOS Core REST API
Production FastAPI interface for audio intelligence pipelines and agent orchestration.
"""

import os
import shutil
import tempfile
from datetime import datetime
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ethos.agents.dsp.orchestrator import SEMASOrchestrator
from ethos.core.config import EnhancementProfile, TargetDAW, TargetFormat

app = FastAPI(
    title="ETHOS Core API",
    description="Unified Audio Intelligence Platform - Autonomous DSP, RL and Infrastructure Agents",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for web and client frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator instance
orchestrator = SEMASOrchestrator()

# In-memory job registry
jobs: dict[str, Any] = {}


class ProcessRequest(BaseModel):
    input_file: str = Field(..., description="Absolute or relative path to input audio file")
    output_directory: str = Field(default="./output", description="Output destination directory")
    enhancement_profile: EnhancementProfile = EnhancementProfile.BALANCED
    target_format: TargetFormat = TargetFormat.STREAMING
    target_daw: TargetDAW = TargetDAW.REAPER
    reference_track: str | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress_percent: float
    elapsed_time: float | None = None
    error_message: str | None = None


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint returning API metadata."""
    return {
        "name": "ETHOS Core Audio Intelligence API",
        "version": "0.1.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "process": "/process",
            "jobs": "/jobs",
        },
    }


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check probe for Kubernetes and Docker container monitoring."""
    return {
        "status": "healthy",
        "service": "ethos-core",
        "version": "0.1.0",
        "active_agents": len(orchestrator.agents),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload and perform Stage 1 audio analysis on a WAV/MP3 track."""
    allowed_exts = [".wav", ".mp3", ".flac", ".ogg"]
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400, detail=f"Unsupported format {ext}. Allowed: {allowed_exts}"
        )

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        analysis_agent = orchestrator.agents.get("audio_analysis")
        if not analysis_agent:
            raise HTTPException(status_code=500, detail="AudioAnalysisAgent not available")
        report = await analysis_agent.analyze_audio(tmp_path, "quick_analysis")
        return {
            "bpm": report.bpm,
            "bpm_confidence": report.bpm_confidence,
            "key": report.key,
            "key_confidence": report.key_confidence,
            "genre": report.genre,
            "subgenre": report.subgenre,
            "duration": report.duration,
            "channels": report.channels,
            "sample_rate": report.sample_rate,
            "sections": [
                {"name": s.name, "start": s.start_time, "end": s.end_time} for s in report.sections
            ],
        }
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/process")
async def process_track(
    request: ProcessRequest, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Trigger the complete 4-stage DSP pipeline asynchronously."""
    if not os.path.exists(request.input_file):
        raise HTTPException(status_code=404, detail=f"Input file not found: {request.input_file}")

    job_id = os.urandom(4).hex()

    async def _run_job():
        job = await orchestrator.process_audio(
            input_file=request.input_file,
            output_directory=request.output_directory,
            enhancement_profile=request.enhancement_profile,
            target_format=request.target_format,
            target_daw=request.target_daw,
            reference_track=request.reference_track,
        )
        jobs[job_id] = job

    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "stage": "analysis",
        "progress_percent": 0.0,
        "started_at": datetime.now(),
    }
    background_tasks.add_task(_run_job)

    return {"job_id": job_id, "status": "queued", "message": "Job queued for processing"}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    """Retrieve current processing status and artifacts for a job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job = jobs[job_id]
    if hasattr(job, "status"):
        return {
            "job_id": job.job_id,
            "status": job.status,
            "stage": job.current_stage.value
            if hasattr(job.current_stage, "value")
            else str(job.current_stage),
            "progress_percent": job.progress_percent,
            "total_processing_time": job.total_processing_time,
            "error_message": job.error_message,
        }
    return job


@app.get("/jobs")
async def list_jobs() -> list[str]:
    """List all tracked job IDs."""
    return list(jobs.keys())


@app.get("/metrics")
async def get_metrics():
    """Expose Prometheus telemetry and Service Level Indicators (SLIs)."""
    from fastapi.responses import PlainTextResponse

    completed = sum(
        1
        for j in jobs.values()
        if getattr(j, "status", None) == "completed"
        or (isinstance(j, dict) and j.get("status") == "completed")
    )
    failed = sum(
        1
        for j in jobs.values()
        if getattr(j, "status", None) == "failed"
        or (isinstance(j, dict) and j.get("status") == "failed")
    )

    metrics_text = (
        "# HELP ethos_active_agents Total number of registered DSP agents\n"
        "# TYPE ethos_active_agents gauge\n"
        f"ethos_active_agents {len(orchestrator.agents)}\n"
        "# HELP ethos_jobs_total Total audio processing jobs by status\n"
        "# TYPE ethos_jobs_total counter\n"
        f'ethos_jobs_total{{status="completed"}} {completed}\n'
        f'ethos_jobs_total{{status="failed"}} {failed}\n'
        f'ethos_jobs_total{{status="total"}} {len(jobs)}\n'
        "# HELP ethos_pipeline_stages Total DSP pipeline stages\n"
        "# TYPE ethos_pipeline_stages gauge\n"
        "ethos_pipeline_stages 4\n"
    )
    return PlainTextResponse(content=metrics_text, media_type="text/plain; version=0.0.4")
