"""SEMAS Loudness Optimizer Agent - LUFS optimization"""

import logging

import numpy as np
import soundfile as sf

from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class LoudnessOptimizerAgent:
    """Stage 3 Agent: LUFS loudness optimization"""

    def __init__(self):
        self.name = "LoudnessOptimizerAgent"
        self.message_bus = get_message_bus()

    async def optimize_loudness(self, audio_path: str, target_lufs: float = -14.0):
        """Optimize to target LUFS"""
        audio, sr = sf.read(audio_path)
        rms = np.sqrt(np.mean(audio**2))
        current_lufs = 20 * np.log10(rms + 1e-10) - 23.0
        adjustment = target_lufs - current_lufs
        gain = 10 ** (adjustment / 20)
        audio_normalized = audio * gain
        output_path = audio_path.replace(".wav", "_loudness_optimized.wav")
        sf.write(output_path, audio_normalized, sr, subtype="PCM_24")
        logger.info(f"Loudness optimized: {current_lufs:.1f} -> {target_lufs:.1f} LUFS")
        return output_path
