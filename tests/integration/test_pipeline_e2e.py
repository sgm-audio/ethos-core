"""
End-to-end integration test for ETHOS Core DSP pipeline:
Executes an audio file through all 4 stages of the SEMASOrchestrator.
"""

import pytest

from ethos.agents.dsp.orchestrator import SEMASOrchestrator
from ethos.core.config import EnhancementProfile, TargetDAW, TargetFormat


@pytest.mark.asyncio
async def test_pipeline_end_to_end(tmp_path, synthetic_stereo_wav: str):
    """
    Run full end-to-end pipeline processing:
    Stage 1: Analysis & Decomposition
    Stage 2: Enhancement
    Stage 3: Mixing & Mastering
    Stage 4: DAW Project Export
    """
    orchestrator = SEMASOrchestrator()
    out_dir = str(tmp_path / "pipeline_output")

    job = await orchestrator.process_audio(
        input_file=synthetic_stereo_wav,
        output_directory=out_dir,
        enhancement_profile=EnhancementProfile.BALANCED,
        target_format=TargetFormat.STREAMING,
        target_daw=TargetDAW.REAPER,
    )

    assert job.status == "completed"
    assert job.total_processing_time >= 0.0
    assert job.progress_percent == 100.0
    assert job.analysis_report is not None
    assert job.analysis_report.bpm > 0
    assert job.analysis_report.key != ""

    status_dict = orchestrator.get_status()
    assert status_dict["status"] == "completed"
    assert status_dict["job_id"] == job.job_id
