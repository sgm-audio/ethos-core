from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ProcessingOp(str, Enum):
    STEM_SEPARATION = "stem_separation"
    EQ = "eq"
    COMPRESSION = "compression"
    NORMALIZE = "normalize"
    CLEANUP = "cleanup"


class ResourceLimits(BaseModel):
    cpu: str = Field(..., description="CPU request/limit (e.g. '500m', '2')")
    memory: str = Field(..., description="Memory request/limit (e.g. '512Mi', '4Gi')")
    gpu: str | None = Field(None, description="GPU request (e.g. '1')")


class ProcessingStep(BaseModel):
    op: ProcessingOp
    params: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None  # e.g. "demucs_htdemucs", "spleeter:2stems"


class DSPRequest(BaseModel):
    job_id: UUID
    audio_source: str = Field(..., description="URL or local path to audio file")
    pipeline: list[ProcessingStep]
    output_format: Literal["wav", "mp3", "flac"] = "wav"
    webhook_url: HttpUrl | None = None


class ProcessingMetrics(BaseModel):
    latency_ms: float
    peak_memory_mb: float
    gpu_utilization_pct: float | None = None


class DSPResponse(BaseModel):
    job_id: UUID
    status: Literal["success", "failed", "processing"]
    artifacts: dict[str, str] = Field(..., description="Map of artifact names to URLs/paths")
    metrics: ProcessingMetrics | None = None
    error_message: str | None = None


class ServiceSpec(BaseModel):
    service_name: str
    image_tag: str
    replicas: int = Field(1, ge=1)
    resources: ResourceLimits
    env_vars: dict[str, str] = Field(default_factory=dict)
    ports: list[int] = Field(default_factory=list)


class DeploymentStatus(BaseModel):
    service_name: str
    state: Literal["pending", "running", "crashed", "unknown"]
    endpoint: str | None = None
    uptime_seconds: float = 0.0
