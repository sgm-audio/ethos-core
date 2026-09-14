"""
Centralized configuration management for ETHOS Core
"""

from enum import Enum

from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"


class EnhancementProfile(str, Enum):
    MINIMAL = "minimal"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class TargetFormat(str, Enum):
    STREAMING = "streaming"
    CD = "cd"
    VINYL = "vinyl"
    BROADCAST = "broadcast"


class TargetDAW(str, Enum):
    REAPER = "reaper"
    ABLETON = "ableton"
    LOGIC = "logic"


class AudioConfig(BaseModel):
    sample_rate: int = 44100
    bit_depth: int = 16
    channels: int = 2
    chunk_size: float = 10.0
    overlap_ratio: float = 0.5

    # AI-specific processing
    apply_spectral_cleaning: bool = True
    enhance_transients: bool = True
    artifact_reduction: bool = True

    # Normalization
    target_level: float = -14.0
    headroom_db: float = -1.0


class ModelConfig(BaseModel):
    demucs_model: str = "htdemucs"
    use_transformer: bool = True
    device: DeviceType = DeviceType.AUTO
    enable_spleeter_fallback: bool = True
    spleeter_model: str = "spleeter:4stems"


class PathConfig(BaseModel):
    output_dir: str | None = None
    templates_dir: str | None = None
    temp_dir: str | None = None
    audio_extensions: list[str] = [".wav", ".mp3", ".flac", ".m4a", ".ogg"]
    project_extensions: list[str] = [".rpp", ".als", ".logicx"]


class WorkflowConfig(BaseModel):
    paths: PathConfig = Field(default_factory=PathConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    models: ModelConfig = Field(default_factory=ModelConfig)

    auto_import: bool = True
    create_stems_dir: bool = True
    copy_original: bool = True
    generate_instructions: bool = True

    enable_semas: bool = True
    enhancement_profile: EnhancementProfile = EnhancementProfile.BALANCED
    target_format: TargetFormat = TargetFormat.STREAMING
    target_daw: TargetDAW = TargetDAW.REAPER


# Legacy-compatible Constants
TIMEOUTS = {
    "stem_separation": 300,
    "semas_processing": 600,
    "file_operations": 30,
    "model_loading": 60,
}

ERROR_MESSAGES = {
    "file_not_found": "File not found: {file_path}",
    "permission_denied": "Permission denied accessing: {file_path}",
    "model_not_loaded": "Model failed to load: {model_name}",
    "separation_failed": "Stem separation failed: {error}",
    "invalid_format": "Unsupported audio format: {format}",
}

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "": {"handlers": ["console"], "level": "INFO"},
    },
}
