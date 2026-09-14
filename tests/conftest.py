"""
Pytest global fixtures for ETHOS Core test suite.
Provides synthetic audio generation, mock stem collections, and test clients.
"""

from collections.abc import Generator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from ethos.agents.dsp.orchestrator import SEMASOrchestrator
from ethos.core.data_structures import AudioStem, StemCollection


@pytest.fixture
def synthetic_stereo_wav(tmp_path: Path) -> Generator[str, None, None]:
    """
    Generate a 3-second 44.1kHz synthetic musical stereo audio track.
    Contains 440Hz base tone + 880Hz harmonic + transient click for testing.
    """
    sr = 44100
    duration = 3.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    # Base sine tone (A4, 440Hz)
    tone = 0.3 * np.sin(2 * np.pi * 440 * t)
    # First harmonic (880Hz)
    tone += 0.15 * np.sin(2 * np.pi * 880 * t)
    # Second harmonic (1320Hz)
    tone += 0.08 * np.sin(2 * np.pi * 1320 * t)

    # Add a transient pulse at 1.0s
    pulse_idx = int(1.0 * sr)
    pulse_len = int(0.01 * sr)
    tone[pulse_idx : pulse_idx + pulse_len] += 0.4

    # Stereo array
    stereo = np.column_stack([tone, tone * 0.95])

    file_path = str(tmp_path / "synthetic_test_track.wav")
    sf.write(file_path, stereo, sr, subtype="PCM_16")

    yield file_path


@pytest.fixture
def synthetic_mono_wav(tmp_path: Path) -> Generator[str, None, None]:
    """Generate a 2-second 44.1kHz mono audio track."""
    sr = 44100
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    mono = 0.25 * np.sin(2 * np.pi * 220 * t)

    file_path = str(tmp_path / "synthetic_mono_track.wav")
    sf.write(file_path, mono, sr, subtype="PCM_16")

    yield file_path


@pytest.fixture
def mock_stem_collection(tmp_path: Path, synthetic_stereo_wav: str) -> StemCollection:
    """Provide a complete 4-stem StemCollection fixture using synthetic audio."""
    vocals_path = str(tmp_path / "vocals.wav")
    drums_path = str(tmp_path / "drums.wav")
    bass_path = str(tmp_path / "bass.wav")
    other_path = str(tmp_path / "other.wav")

    # Read base synthetic audio and write separate stems
    audio, sr = sf.read(synthetic_stereo_wav)
    sf.write(vocals_path, audio * 0.8, sr)
    sf.write(drums_path, audio * 0.7, sr)
    sf.write(bass_path, audio * 0.6, sr)
    sf.write(other_path, audio * 0.5, sr)

    duration = len(audio) / sr

    vocals = AudioStem(
        name="Vocals", file_path=vocals_path, stem_type="vocals", duration=duration, sample_rate=sr
    )
    drums = AudioStem(
        name="Drums", file_path=drums_path, stem_type="drums", duration=duration, sample_rate=sr
    )
    bass = AudioStem(
        name="Bass", file_path=bass_path, stem_type="bass", duration=duration, sample_rate=sr
    )
    other = AudioStem(
        name="Other", file_path=other_path, stem_type="other", duration=duration, sample_rate=sr
    )

    return StemCollection(vocals=vocals, drums=drums, bass=bass, other=other)


@pytest.fixture
def orchestrator() -> SEMASOrchestrator:
    """Fixture providing an initialized SEMASOrchestrator."""
    return SEMASOrchestrator()
