"""
SEMAS Harmonic Enrichment Agent
Adds harmonic richness and warmth
"""

import logging

import numpy as np
import soundfile as sf
from scipy import signal

from ethos.core.data_structures import AudioStem, ProcessingStep
from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class HarmonicEnrichmentAgent:
    """Stage 2 Agent: Harmonic enrichment and saturation"""

    def __init__(self):
        self.name = "HarmonicEnrichmentAgent"
        self.message_bus = get_message_bus()

    async def enrich_harmonics(self, stem: AudioStem, intensity: float = 0.3):
        """Add harmonic richness"""
        audio, sr = sf.read(stem.file_path)

        # Gentle tape saturation
        audio_saturated = np.tanh(audio * (1.0 + intensity)) / (1.0 + intensity)

        # Exciter effect (add harmonics in 2-10kHz range)
        audio_excited = self._exciter(audio, sr, intensity)

        # Blend
        audio_enriched = audio_saturated * 0.7 + audio_excited * 0.3

        output_path = stem.file_path.replace(".wav", "_harmonic_enriched.wav")
        sf.write(output_path, audio_enriched, sr, subtype="PCM_24")

        enhanced_stem = AudioStem(
            name=stem.name,
            file_path=output_path,
            stem_type=stem.stem_type,
            duration=stem.duration,
            sample_rate=sr,
            separation_quality=stem.separation_quality,
            spectral_leakage=stem.spectral_leakage,
            transient_preservation=stem.transient_preservation,
            processing_chain=stem.processing_chain + [f"{self.name}:harmonic_enrichment"],
            enhancement_applied=True,
        )

        return enhanced_stem, ProcessingStep(
            step_name="Harmonic Enrichment",
            processor=self.name,
            parameters={"intensity": intensity},
            input_metrics={},
            output_metrics={},
            improvement_score=0.2,
        )

    def _exciter(self, audio: np.ndarray, sr: int, intensity: float) -> np.ndarray:
        """Aural exciter effect"""
        # High-pass filter
        nyq = sr / 2
        hp = signal.butter(4, 2000 / nyq, btype="high", output="sos")
        high_freq = signal.sosfilt(hp, audio, axis=0)

        # Add harmonics
        excited = np.tanh(high_freq * 3) * intensity

        return audio + excited
