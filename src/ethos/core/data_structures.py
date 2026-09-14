"""
Audio DSP Data Structures & Analysis Models
Shared dataclasses representing audio analysis, stems, mix parameters, and job status.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np


class ProcessingStage(str, Enum):
    ANALYSIS = "analysis"
    SEPARATION = "separation"
    ENHANCEMENT = "enhancement"
    MIXING = "mixing"
    MASTERING = "mastering"
    EXPORT = "export"


@dataclass
class Section:
    """Song section (verse, chorus, etc.)"""

    name: str
    start_time: float
    end_time: float
    start_bar: int = 0
    end_bar: int = 0
    confidence: float = 1.0


@dataclass
class FrequencyAnalysis:
    """Frequency spectrum analysis"""

    spectrum: np.ndarray  # FFT magnitude
    frequencies: np.ndarray  # Frequency bins
    spectral_centroid: float
    spectral_rolloff: float
    spectral_flatness: float

    # Band energy (dB)
    sub_bass: float  # 20-60 Hz
    bass: float  # 60-250 Hz
    low_mids: float  # 250-500 Hz
    mids: float  # 500-2000 Hz
    upper_mids: float  # 2000-4000 Hz
    presence: float  # 4000-8000 Hz
    brilliance: float  # 8000-20000 Hz


@dataclass
class DynamicRange:
    """Dynamic range metrics"""

    peak_db: float
    rms_db: float
    lufs_integrated: float
    lufs_short_term: float
    lufs_momentary: float
    true_peak_db: float
    dynamic_range: float  # DR meter value
    crest_factor: float


@dataclass
class StereoAnalysis:
    """Stereo field analysis"""

    correlation: float  # -1 to 1
    width: float  # 0 to 200%
    balance: float  # -100% (left) to +100% (right)
    mono_compatible: bool
    phase_issues: list[str] = field(default_factory=list)


@dataclass
class AudioIssue:
    """Detected audio quality issue"""

    issue_type: str  # "clipping", "artifact", "phase", etc.
    severity: float  # 0.0 to 1.0
    location: float  # Time in seconds
    description: str
    recommended_fix: str


@dataclass
class AudioAnalysisReport:
    """Comprehensive audio analysis"""

    file_id: str
    file_path: str
    duration: float
    sample_rate: int
    bit_depth: int
    channels: int

    # Musical metadata
    bpm: float
    bpm_confidence: float
    key: str
    key_confidence: float
    time_signature: str

    # Structure
    sections: list[Section] = field(default_factory=list)

    # Technical analysis
    frequency_analysis: FrequencyAnalysis | None = None
    dynamic_range: DynamicRange | None = None
    stereo_analysis: StereoAnalysis | None = None

    # Quality
    overall_quality_score: float = 1.0
    detected_issues: list[AudioIssue] = field(default_factory=list)

    # Genre/mood
    genre: str = "Unknown"
    subgenre: str = ""
    mood: list[str] = field(default_factory=list)
    energy_level: float = 0.5

    # Metadata
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    analysis_version: str = "1.0"


@dataclass
class AudioStem:
    """Single audio stem"""

    name: str
    file_path: str
    stem_type: str  # vocals, drums, bass, other
    duration: float
    sample_rate: int

    # Quality metrics
    separation_quality: float = 1.0  # 0.0 to 1.0
    spectral_leakage: float = 0.0  # Amount of other stems present
    transient_preservation: float = 1.0  # How well transients preserved

    # Processing history
    processing_chain: list[str] = field(default_factory=list)
    enhancement_applied: bool = False


@dataclass
class DrumKitStems:
    """Sub-stems for drum kit"""

    kick: AudioStem | None = None
    snare: AudioStem | None = None
    hihat: AudioStem | None = None
    toms: AudioStem | None = None
    cymbals: AudioStem | None = None
    room: AudioStem | None = None


@dataclass
class VocalStems:
    """Sub-stems for vocals"""

    lead: AudioStem | None = None
    backing: AudioStem | None = None
    harmony: AudioStem | None = None


@dataclass
class StemCollection:
    """Collection of separated stems"""

    vocals: AudioStem
    drums: AudioStem
    bass: AudioStem
    other: AudioStem

    # Optional sub-stems
    drum_kit: DrumKitStems | None = None
    vocal_layers: VocalStems | None = None

    # Metadata
    separation_model: str = "demucs-htdemucs"
    separation_timestamp: datetime = field(default_factory=datetime.now)
    total_separation_time: float = 0.0


@dataclass
class AudioProcessingStep:
    """Single DSP processing step record"""

    step_name: str
    processor: str
    parameters: dict[str, Any] = field(default_factory=dict)
    input_metrics: dict[str, float] = field(default_factory=dict)
    output_metrics: dict[str, float] = field(default_factory=dict)
    improvement_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


# Compatibility alias
ProcessingStep = AudioProcessingStep


@dataclass
class ProcessingChain:
    """Complete processing chain for a stem"""

    stem_name: str
    steps: list[AudioProcessingStep] = field(default_factory=list)
    total_improvement: float = 0.0
    processing_time: float = 0.0


@dataclass
class MixParameters:
    """Mix parameters for multi-track summing"""

    stem_levels: dict[str, float] = field(default_factory=dict)  # dB levels
    stem_pans: dict[str, float] = field(default_factory=dict)  # -1.0 to 1.0
    bus_routing: dict[str, list[str]] = field(default_factory=dict)  # bus -> stems
    send_effects: dict[str, dict[str, float]] = field(
        default_factory=dict
    )  # effect -> {stem: level}


@dataclass
class MasteringParameters:
    """Mastering chain parameters"""

    target_lufs: float = -14.0
    true_peak_limit: float = -1.0
    eq_curve: list[tuple] = field(default_factory=list)  # [(freq, gain, q)]
    compression_ratio: float = 2.0
    compression_threshold: float = -10.0


@dataclass
class DAWProject:
    """DAW project file representation"""

    daw_type: str  # "reaper", "ableton", "logic"
    project_file_path: str
    tempo: float
    time_signature: str
    sample_rate: int

    # Tracks
    stem_tracks: dict[str, str] = field(default_factory=dict)  # stem_name -> track_file
    markers: list[Section] = field(default_factory=list)

    # Export metadata
    created_timestamp: datetime = field(default_factory=datetime.now)
    semas_version: str = "1.0"


@dataclass
class SEMASJob:
    """Complete audio processing job status and results"""

    job_id: str
    input_file: str
    output_directory: str

    # Configuration
    enhancement_profile: str = "balanced"  # minimal, balanced, aggressive
    target_format: str = "streaming"  # streaming, cd, vinyl, broadcast
    reference_track: str | None = None
    target_daw: str = "reaper"

    # Processing stages
    current_stage: ProcessingStage = ProcessingStage.ANALYSIS
    progress_percent: float = 0.0

    # Results
    analysis_report: AudioAnalysisReport | None = None
    stem_collection: StemCollection | None = None
    mix_parameters: MixParameters | None = None
    mastering_parameters: MasteringParameters | None = None
    daw_project: DAWProject | None = None

    # Timing
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    total_processing_time: float = 0.0

    # Status
    status: str = "queued"  # queued, running, completed, failed
    error_message: str | None = None
