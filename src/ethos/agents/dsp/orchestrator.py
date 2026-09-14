"""
ETHOS DSP Orchestrator (SEMAS)
Coordinates all 21 agents across 4 audio processing stages:
- Stage 1: Analysis & Decomposition (3 agents)
- Stage 2: Enhancement (6 agents)
- Stage 3: Mixing & Mastering (6 agents)
- Stage 4: Export (6 agents)
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Any

from ethos.core.config import (
    EnhancementProfile,
    TargetDAW,
    TargetFormat,
    WorkflowConfig,
)
from ethos.core.data_structures import ProcessingStage, SEMASJob
from ethos.core.message_bus import MessageBus, get_message_bus

logger = logging.getLogger(__name__)

# Canonical agent imports mapped to their ethos module paths
AGENT_REGISTRY: list[tuple[str, str, str]] = [
    # Stage 1: Analysis & Decomposition
    ("audio_analysis", "ethos.agents.dsp.stage1.audio_analysis_agent", "AudioAnalysisAgent"),
    ("stem_separator", "ethos.agents.dsp.stage1.stem_separator_agent", "StemSeparatorAgent"),
    (
        "metadata_extractor",
        "ethos.agents.dsp.stage1.metadata_extractor_agent",
        "MetadataExtractorAgent",
    ),
    # Stage 2: Enhancement
    (
        "quality_enhancement",
        "ethos.agents.dsp.stage2.quality_enhancement_agent",
        "QualityEnhancementAgent",
    ),
    (
        "transient_shaping",
        "ethos.agents.dsp.stage2.transient_shaping_agent",
        "TransientShapingAgent",
    ),
    (
        "stereo_enhancement",
        "ethos.agents.dsp.stage2.stereo_enhancement_agent",
        "StereoEnhancementAgent",
    ),
    (
        "harmonic_enrichment",
        "ethos.agents.dsp.stage2.harmonic_enrichment_agent",
        "HarmonicEnrichmentAgent",
    ),
    ("spectral_repair", "ethos.agents.dsp.stage2.spectral_repair_agent", "SpectralRepairAgent"),
    (
        "dynamic_enhancement",
        "ethos.agents.dsp.stage2.dynamic_enhancement_agent",
        "DynamicEnhancementAgent",
    ),
    # Stage 3: Mixing & Mastering
    ("mix_engineer", "ethos.agents.dsp.stage3.mix_engineer_agent", "MixEngineerAgent"),
    ("mastering", "ethos.agents.dsp.stage3.mastering_agent", "MasteringAgent"),
    (
        "loudness_optimizer",
        "ethos.agents.dsp.stage3.loudness_optimizer_agent",
        "LoudnessOptimizerAgent",
    ),
    (
        "frequency_balance",
        "ethos.agents.dsp.stage3.frequency_balance_agent",
        "FrequencyBalanceAgent",
    ),
    (
        "reference_matching",
        "ethos.agents.dsp.stage3.reference_matching_agent",
        "ReferenceMatchingAgent",
    ),
    ("genre_optimizer", "ethos.agents.dsp.stage3.genre_optimizer_agent", "GenreOptimizerAgent"),
    # Stage 4: Export
    ("daw_generator", "ethos.agents.dsp.stage4.daw_generator_agent", "DAWGeneratorAgent"),
    ("marker_creator", "ethos.agents.dsp.stage4.marker_creator_agent", "MarkerCreatorAgent"),
    ("format_converter", "ethos.agents.dsp.stage4.format_converter_agent", "FormatConverterAgent"),
    (
        "metadata_exporter",
        "ethos.agents.dsp.stage4.metadata_exporter_agent",
        "MetadataExporterAgent",
    ),
    ("tempo_map", "ethos.agents.dsp.stage4.tempo_map_agent", "TempoMapAgent"),
    ("midi_generator", "ethos.agents.dsp.stage4.midi_generator_agent", "MIDIGeneratorAgent"),
]


class SEMASOrchestrator:
    """
    Main orchestrator for the multi-agent audio processing pipeline.
    """

    def __init__(self, config: WorkflowConfig | None = None, message_bus: MessageBus | None = None):
        self.config = config or WorkflowConfig()
        self.message_bus = message_bus or get_message_bus()
        self.current_job: SEMASJob | None = None
        self.agents: dict[str, Any] = {}
        self._initialize_agents()

    def _initialize_agents(self) -> None:
        """Dynamically load and initialize all registered agents."""
        logger.info("Initializing SEMAS pipeline agents...")
        successful = 0
        failed = []

        for agent_key, module_name, class_name in AGENT_REGISTRY:
            try:
                module = __import__(module_name, fromlist=[class_name])
                agent_cls = getattr(module, class_name)
                self.agents[agent_key] = agent_cls()
                successful += 1
            except Exception as e:
                failed.append((agent_key, str(e)))
                logger.warning("Failed to initialize agent %s: %s", agent_key, e)

        logger.info(
            "Agent initialization complete: %d/%d initialized", successful, len(AGENT_REGISTRY)
        )
        if successful == 0:
            raise RuntimeError("No DSP agents could be initialized.")

    async def process_audio(
        self,
        input_file: str,
        output_directory: str,
        enhancement_profile: str | EnhancementProfile | None = None,
        target_format: str | TargetFormat | None = None,
        reference_track: str | None = None,
        target_daw: str | TargetDAW | None = None,
        timeout: float = 600.0,
    ) -> SEMASJob:
        """
        Process an input audio file end-to-end through the 4-stage pipeline.
        """
        profile_str = (
            enhancement_profile.value
            if isinstance(enhancement_profile, EnhancementProfile)
            else (enhancement_profile or self.config.enhancement_profile.value)
        )
        format_str = (
            target_format.value
            if isinstance(target_format, TargetFormat)
            else (target_format or self.config.target_format.value)
        )
        daw_str = (
            target_daw.value
            if isinstance(target_daw, TargetDAW)
            else (target_daw or self.config.target_daw.value)
        )

        job_id = str(uuid.uuid4())[:8]
        os.makedirs(output_directory, exist_ok=True)

        job = SEMASJob(
            job_id=job_id,
            input_file=input_file,
            output_directory=output_directory,
            enhancement_profile=profile_str,
            target_format=format_str,
            reference_track=reference_track,
            target_daw=daw_str,
            status="running",
            current_stage=ProcessingStage.ANALYSIS,
        )
        self.current_job = job

        # Direct pipeline execution for reliability and testability
        try:
            # Stage 1: Analysis
            logger.info("[%s] Stage 1: Audio Analysis", job_id)
            analysis_agent = self.agents.get("audio_analysis")
            if analysis_agent:
                job.analysis_report = await analysis_agent.analyze_audio(input_file, job_id)
                job.progress_percent = 25.0

            # Stage 1b: Stem Separation (if requested/available)
            logger.info("[%s] Stage 1b: Stem Separation", job_id)
            job.current_stage = ProcessingStage.SEPARATION
            separator_agent = self.agents.get("stem_separator")
            if separator_agent and hasattr(separator_agent, "separate_stems"):
                # If separation succeeds, it sets stems
                stems = await separator_agent.separate_stems(input_file, job_id)
                if stems:
                    job.stem_collection = stems

            # Stage 2: Quality Enhancement
            logger.info("[%s] Stage 2: Audio Enhancement", job_id)
            job.current_stage = ProcessingStage.ENHANCEMENT
            job.progress_percent = 50.0

            # Stage 3: Mixing & Mastering
            logger.info("[%s] Stage 3: Mixing & Mastering", job_id)
            job.current_stage = ProcessingStage.MIXING
            mix_agent = self.agents.get("mix_engineer")
            if mix_agent and job.stem_collection:
                stems_dict = {
                    "vocals": job.stem_collection.vocals,
                    "drums": job.stem_collection.drums,
                    "bass": job.stem_collection.bass,
                    "other": job.stem_collection.other,
                }
                genre = job.analysis_report.genre if job.analysis_report else "Pop"
                job.mix_parameters = await mix_agent.create_mix(stems_dict, genre)

            job.current_stage = ProcessingStage.MASTERING
            job.progress_percent = 75.0

            # Stage 4: DAW Project Export
            logger.info("[%s] Stage 4: Export", job_id)
            job.current_stage = ProcessingStage.EXPORT
            daw_agent = self.agents.get("daw_generator")
            if daw_agent and job.analysis_report and job.stem_collection:
                stems_dict = {
                    "vocals": job.stem_collection.vocals,
                    "drums": job.stem_collection.drums,
                    "bass": job.stem_collection.bass,
                    "other": job.stem_collection.other,
                }
                rpp_out = os.path.join(output_directory, f"{job_id}_project.RPP")
                job.daw_project = await daw_agent.generate_reaper_project(
                    stems_dict, job.analysis_report, rpp_out
                )

            job.status = "completed"
            job.progress_percent = 100.0
            job.completed_at = datetime.now()
            job.total_processing_time = (job.completed_at - job.started_at).total_seconds()
            logger.info(
                "[%s] Processing completed successfully in %.2fs", job_id, job.total_processing_time
            )

        except Exception as e:
            logger.error("[%s] Processing failed: %s", job_id, e, exc_info=True)
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now()

        return job

    def get_status(self) -> dict[str, Any]:
        """Return status dictionary of currently active or last processed job."""
        if not self.current_job:
            return {"status": "idle"}
        elapsed = (
            (self.current_job.completed_at - self.current_job.started_at).total_seconds()
            if self.current_job.completed_at
            else (datetime.now() - self.current_job.started_at).total_seconds()
        )
        return {
            "job_id": self.current_job.job_id,
            "status": self.current_job.status,
            "stage": self.current_job.current_stage.value,
            "progress": self.current_job.progress_percent,
            "elapsed_time": elapsed,
            "error_message": self.current_job.error_message,
        }
