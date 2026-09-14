"""
Unit tests for Stage 2 DSP Enhancement Agents:
- QualityEnhancementAgent
- TransientShapingAgent (verifying stems are retained)
- StereoEnhancementAgent (mono to stereo & widening)
- SpectralRepairAgent (multi-channel stereo safety)
- HarmonicEnrichmentAgent
- DynamicEnhancementAgent
"""

import os

import pytest
import soundfile as sf

from ethos.agents.dsp.stage2.dynamic_enhancement_agent import DynamicEnhancementAgent
from ethos.agents.dsp.stage2.harmonic_enrichment_agent import HarmonicEnrichmentAgent
from ethos.agents.dsp.stage2.quality_enhancement_agent import QualityEnhancementAgent
from ethos.agents.dsp.stage2.spectral_repair_agent import SpectralRepairAgent
from ethos.agents.dsp.stage2.stereo_enhancement_agent import StereoEnhancementAgent
from ethos.agents.dsp.stage2.transient_shaping_agent import TransientShapingAgent
from ethos.core.data_structures import AudioStem, StemCollection


@pytest.mark.asyncio
async def test_quality_enhancement_agent(mock_stem_collection: StemCollection):
    """Verify quality enhancement processing and artifact reduction."""
    agent = QualityEnhancementAgent()
    stem = mock_stem_collection.vocals

    enhanced_stem, step = await agent.enhance_stem(stem)
    assert os.path.exists(enhanced_stem.file_path)
    assert enhanced_stem.enhancement_applied is True
    assert step.improvement_score >= 0.0

    # Verify audio can be read
    audio, sr = sf.read(enhanced_stem.file_path)
    assert sr == 44100
    assert len(audio) > 0


@pytest.mark.asyncio
async def test_transient_shaping_agent_retains_all_stems(mock_stem_collection: StemCollection):
    """Verify TransientShapingAgent shapes transients without dropping vocal or other stems."""
    agent = TransientShapingAgent()
    stem = mock_stem_collection.drums

    enhanced_drum, step = await agent.shape_transients(stem, intensity=0.6)
    assert os.path.exists(enhanced_drum.file_path)
    assert enhanced_drum.enhancement_applied is True

    # Test event handler preserving all stems
    stems_dict = {
        "vocals": mock_stem_collection.vocals,
        "drums": mock_stem_collection.drums,
        "bass": mock_stem_collection.bass,
        "other": mock_stem_collection.other,
    }
    mock_msg = type("Message", (), {"payload": {"stems": stems_dict, "file_id": "test_job"}})()

    published_payload = None

    async def mock_publish(topic, payload, sender):
        nonlocal published_payload
        published_payload = payload

    agent.message_bus.publish = mock_publish
    await agent._on_quality_enhanced(mock_msg)

    assert published_payload is not None
    assert "vocals" in published_payload["stems"]
    assert "drums" in published_payload["stems"]
    assert "bass" in published_payload["stems"]
    assert "other" in published_payload["stems"]


@pytest.mark.asyncio
async def test_stereo_enhancement_agent(
    mock_stem_collection: StemCollection, synthetic_mono_wav: str
):
    """Verify stereo widening and mono to pseudo-stereo conversion."""
    agent = StereoEnhancementAgent()

    # Stereo stem widening
    enhanced_stereo, _ = await agent.enhance_stereo(mock_stem_collection.other, width_factor=1.3)
    assert os.path.exists(enhanced_stereo.file_path)

    # Mono stem conversion
    mono_stem = AudioStem(
        name="Lead",
        file_path=synthetic_mono_wav,
        stem_type="vocals",
        duration=2.0,
        sample_rate=44100,
    )
    enhanced_mono, _ = await agent.enhance_stereo(mono_stem, width_factor=1.2)
    assert os.path.exists(enhanced_mono.file_path)
    audio, _ = sf.read(enhanced_mono.file_path)
    assert audio.ndim == 2  # Converted to stereo


@pytest.mark.asyncio
async def test_spectral_repair_agent_stereo_and_mono(
    mock_stem_collection: StemCollection, synthetic_mono_wav: str
):
    """Verify SpectralRepairAgent handles both stereo and mono without broadcast errors."""
    agent = SpectralRepairAgent()

    # Stereo audio test
    stereo_stem = mock_stem_collection.drums
    enhanced_stereo, step = await agent.repair_spectrum(stereo_stem)
    assert os.path.exists(enhanced_stereo.file_path)
    assert step.improvement_score > 0.0

    # Mono audio test
    mono_stem = AudioStem(
        name="Bass", file_path=synthetic_mono_wav, stem_type="bass", duration=2.0, sample_rate=44100
    )
    enhanced_mono, _ = await agent.repair_spectrum(mono_stem)
    assert os.path.exists(enhanced_mono.file_path)


@pytest.mark.asyncio
async def test_harmonic_and_dynamic_enhancement(mock_stem_collection: StemCollection):
    """Verify harmonic enrichment and dynamic enhancement agents."""
    harmonic_agent = HarmonicEnrichmentAgent()
    enhanced_h, _ = await harmonic_agent.enrich_harmonics(mock_stem_collection.bass, intensity=0.4)
    assert os.path.exists(enhanced_h.file_path)

    dynamic_agent = DynamicEnhancementAgent()
    enhanced_d, _ = await dynamic_agent.enhance_dynamics(
        mock_stem_collection.drums, compression_ratio=3.0
    )
    assert os.path.exists(enhanced_d.file_path)
