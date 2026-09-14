"""
SEMAS Dynamic Enhancement Agent
Intelligent compression and expansion
"""

import logging

import numpy as np
import soundfile as sf

from ethos.core.data_structures import AudioStem, ProcessingStep
from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class DynamicEnhancementAgent:
    """Stage 2 Agent: Dynamic range optimization"""

    def __init__(self):
        self.name = "DynamicEnhancementAgent"
        self.message_bus = get_message_bus()

    async def enhance_dynamics(
        self, stem: AudioStem, compression_ratio: float = 3.0, threshold_db: float = -20.0
    ):
        """Apply intelligent compression/expansion"""
        audio, sr = sf.read(stem.file_path)

        # Apply compression
        audio_compressed = self._compress(audio, ratio=compression_ratio, threshold_db=threshold_db)

        # Apply gentle expansion for dynamics
        audio_enhanced = self._expand(audio_compressed, ratio=1.5, threshold_db=-40.0)

        # Makeup gain
        input_rms = np.sqrt(np.mean(audio**2))
        output_rms = np.sqrt(np.mean(audio_enhanced**2))
        if output_rms > 0:
            makeup_gain = input_rms / output_rms
            audio_enhanced *= makeup_gain

        output_path = stem.file_path.replace(".wav", "_dynamic_enhanced.wav")
        sf.write(output_path, audio_enhanced, sr, subtype="PCM_24")

        enhanced_stem = AudioStem(
            name=stem.name,
            file_path=output_path,
            stem_type=stem.stem_type,
            duration=stem.duration,
            sample_rate=sr,
            separation_quality=stem.separation_quality,
            spectral_leakage=stem.spectral_leakage,
            transient_preservation=stem.transient_preservation,
            processing_chain=stem.processing_chain + [f"{self.name}:dynamic_enhancement"],
            enhancement_applied=True,
        )

        return enhanced_stem, ProcessingStep(
            step_name="Dynamic Enhancement",
            processor=self.name,
            parameters={"compression_ratio": compression_ratio, "threshold_db": threshold_db},
            input_metrics={},
            output_metrics={},
            improvement_score=0.2,
        )

    def _compress(self, audio: np.ndarray, ratio: float, threshold_db: float) -> np.ndarray:
        """Apply compression"""
        threshold_lin = 10 ** (threshold_db / 20)

        audio_compressed = audio.copy()
        mask = np.abs(audio) > threshold_lin

        # Apply compression to samples above threshold
        sign = np.sign(audio)
        abs_audio = np.abs(audio)

        compressed_value = threshold_lin + (abs_audio - threshold_lin) / ratio
        audio_compressed = np.where(mask, sign * compressed_value, audio)

        return audio_compressed

    def _expand(self, audio: np.ndarray, ratio: float, threshold_db: float) -> np.ndarray:
        """Apply expansion (inverse of compression)"""
        threshold_lin = 10 ** (threshold_db / 20)

        audio_expanded = audio.copy()
        mask = np.abs(audio) < threshold_lin

        # Apply expansion to samples below threshold
        sign = np.sign(audio)
        abs_audio = np.abs(audio)

        expanded_value = abs_audio / ratio
        audio_expanded = np.where(mask, sign * expanded_value, audio)

        return audio_expanded
