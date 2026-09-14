"""
Unit tests for Stage 3 DSP Mixing & Mastering Agents:
- MixEngineerAgent
- MasteringAgent
- LoudnessOptimizerAgent
- FrequencyBalanceAgent
- GenreOptimizerAgent
- ReferenceMatchingAgent
"""

import os

import numpy as np
import pytest
import soundfile as sf

from ethos.agents.dsp.stage3.frequency_balance_agent import FrequencyBalanceAgent
from ethos.agents.dsp.stage3.genre_optimizer_agent import GenreOptimizerAgent
from ethos.agents.dsp.stage3.loudness_optimizer_agent import LoudnessOptimizerAgent
from ethos.agents.dsp.stage3.mastering_agent import MasteringAgent
from ethos.agents.dsp.stage3.mix_engineer_agent import MixEngineerAgent
from ethos.agents.dsp.stage3.reference_matching_agent import ReferenceMatchingAgent
from ethos.core.data_structures import MasteringParameters, StemCollection


@pytest.mark.asyncio
async def test_mix_engineer_agent(tmp_path, mock_stem_collection: StemCollection):
    """Test mix parameter generation, stem processing, and multi-track mix bounce."""
    agent = MixEngineerAgent()
    stems = {
        "vocals": mock_stem_collection.vocals,
        "drums": mock_stem_collection.drums,
        "bass": mock_stem_collection.bass,
        "other": mock_stem_collection.other,
    }

    # Test create_mix
    mix_params = await agent.create_mix(stems, "Pop")
    assert "vocals" in mix_params.stem_levels
    assert "drums" in mix_params.stem_levels

    # Test apply_mix_to_stems
    processed = await agent.apply_mix_to_stems(stems, mix_params)
    assert len(processed) == 4

    # Test render_mix
    out_mix = str(tmp_path / "final_mix.wav")
    await agent.render_mix(processed, out_mix, sr=44100)
    assert os.path.exists(out_mix)
    audio, sr = sf.read(out_mix)
    assert sr == 44100
    assert audio.ndim == 2
    assert np.max(np.abs(audio)) <= 1.0


@pytest.mark.asyncio
async def test_mastering_agent(tmp_path, synthetic_stereo_wav: str):
    """Test mastering chain: EQ, dynamic compression, limiting, and loudness target."""
    agent = MasteringAgent()
    out_master = str(tmp_path / "mastered.wav")

    params = MasteringParameters(
        target_lufs=-14.0,
        true_peak_limit=-1.0,
        eq_curve=[],
        compression_ratio=2.5,
        compression_threshold=-12.0,
    )

    await agent.master_audio(synthetic_stereo_wav, out_master, params)
    assert os.path.exists(out_master)
    audio, sr = sf.read(out_master)
    assert len(audio) > 0
    assert np.max(np.abs(audio)) <= 1.0


@pytest.mark.asyncio
async def test_loudness_and_frequency_balance(mock_stem_collection: StemCollection):
    """Test loudness optimizer and frequency balance agent processing."""
    loudness_agent = LoudnessOptimizerAgent()
    opt_path = await loudness_agent.optimize_loudness(
        mock_stem_collection.vocals.file_path, target_lufs=-16.0
    )
    assert os.path.exists(opt_path)

    freq_agent = FrequencyBalanceAgent()
    bal_path = await freq_agent.balance_frequency(mock_stem_collection.other.file_path)
    assert os.path.exists(bal_path)


@pytest.mark.asyncio
async def test_genre_and_reference_matching(
    mock_stem_collection: StemCollection, synthetic_stereo_wav: str
):
    """Test genre optimization and reference matching."""
    genre_agent = GenreOptimizerAgent()
    genre_path = await genre_agent.optimize_for_genre(
        mock_stem_collection.drums.file_path, genre="Rock"
    )
    assert os.path.exists(genre_path)

    ref_agent = ReferenceMatchingAgent()
    matched_path = await ref_agent.match_reference(
        mock_stem_collection.vocals.file_path, synthetic_stereo_wav
    )
    assert os.path.exists(matched_path)
