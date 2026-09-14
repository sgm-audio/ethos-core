"""
Unit tests for Stage 1 DSP Agents:
- AudioAnalysisAgent (tempo, key, spectral balance, structure)
- MetadataExtractorAgent (tags, sections, metadata packaging)
- StemSeparatorAgent (model execution and stem collation)
"""

from unittest.mock import AsyncMock, patch

import pytest

from ethos.agents.dsp.stage1.audio_analysis_agent import AudioAnalysisAgent
from ethos.agents.dsp.stage1.metadata_extractor_agent import MetadataExtractorAgent
from ethos.agents.dsp.stage1.stem_separator_agent import StemSeparatorAgent
from ethos.core.data_structures import AudioStem, StemCollection


@pytest.mark.asyncio
async def test_audio_analysis_agent(synthetic_stereo_wav: str):
    """Test comprehensive audio analysis on synthetic musical audio."""
    agent = AudioAnalysisAgent()
    report = await agent.analyze_audio(synthetic_stereo_wav, "test_job_1")

    assert report.file_id == "test_job_1"
    assert report.duration > 0.0
    assert report.sample_rate == 44100
    assert report.channels == 2
    assert report.bpm > 0
    assert isinstance(report.key, str)
    assert report.frequency_analysis is not None
    assert report.frequency_analysis.spectral_centroid > 0
    assert report.dynamic_range is not None
    assert report.dynamic_range.peak_db <= 0.0
    assert report.stereo_analysis is not None
    assert len(report.sections) >= 1


@pytest.mark.asyncio
async def test_metadata_extractor_agent(synthetic_stereo_wav: str):
    """Test metadata extraction from an analysis report."""
    analysis_agent = AudioAnalysisAgent()
    report = await analysis_agent.analyze_audio(synthetic_stereo_wav, "test_meta_job")

    meta_agent = MetadataExtractorAgent()
    metadata = meta_agent.extract_metadata(report)

    assert metadata["file_id"] == "test_meta_job"
    assert "bpm" in metadata
    assert "sample_rate" in metadata
    assert "sections" in metadata
    assert metadata["bpm"] == report.bpm


@pytest.mark.asyncio
async def test_stem_separator_agent_fallback_and_mock(tmp_path, synthetic_stereo_wav: str):
    """Test StemSeparatorAgent initialization and separation execution."""
    agent = StemSeparatorAgent(output_dir=str(tmp_path / "stems"))

    # Test file not found error handling
    result_missing = await agent.separate_stems("/non/existent/path.wav", "job_none")
    assert result_missing is None

    # Test separation with mocked Demucs runner
    mock_collection = StemCollection(
        vocals=AudioStem(
            name="Vocals",
            file_path=synthetic_stereo_wav,
            stem_type="vocals",
            duration=3.0,
            sample_rate=44100,
        ),
        drums=AudioStem(
            name="Drums",
            file_path=synthetic_stereo_wav,
            stem_type="drums",
            duration=3.0,
            sample_rate=44100,
        ),
        bass=AudioStem(
            name="Bass",
            file_path=synthetic_stereo_wav,
            stem_type="bass",
            duration=3.0,
            sample_rate=44100,
        ),
        other=AudioStem(
            name="Other",
            file_path=synthetic_stereo_wav,
            stem_type="other",
            duration=3.0,
            sample_rate=44100,
        ),
    )

    with patch.object(agent, "separate_stems", AsyncMock(return_value=mock_collection)):
        collection = await agent.separate_stems(synthetic_stereo_wav, "mock_job")
        assert collection is not None
        assert collection.vocals.stem_type == "vocals"
        assert collection.drums.stem_type == "drums"
