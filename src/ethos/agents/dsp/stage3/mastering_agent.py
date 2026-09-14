"""
SEMAS Mastering Agent
Final mastering chain: EQ, compression, limiting
"""

import logging

import numpy as np
import soundfile as sf
from scipy import signal

from ethos.core.data_structures import MasteringParameters
from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class MasteringAgent:
    """Stage 3 Agent: Final mastering"""

    def __init__(self):
        self.name = "MasteringAgent"
        self.message_bus = get_message_bus()
        self.message_bus.subscribe("mix.created", self._on_mix_created)

    async def _on_mix_created(self, message):
        """Master the mix"""
        file_id = message.payload.get("file_id")

        mastering_params = MasteringParameters(
            target_lufs=-14.0,
            true_peak_limit=-1.0,
            eq_curve=[],
            compression_ratio=2.5,
            compression_threshold=-10.0,
        )

        await self.message_bus.publish(
            topic="mastering.complete",
            payload={"mastering_params": mastering_params, "file_id": file_id},
            sender=self.name,
        )

    async def master_audio(self, audio_path: str, output_path: str, params: MasteringParameters):
        """Apply mastering chain"""
        audio, sr = sf.read(audio_path)

        # 1. EQ
        audio = self._apply_mastering_eq(audio, sr)

        # 2. Compression
        audio = self._apply_compression(
            audio, params.compression_ratio, params.compression_threshold
        )

        # 3. Limiting
        audio = self._apply_limiter(audio, params.true_peak_limit)

        # 4. Final loudness normalization
        audio = self._normalize_loudness(audio, params.target_lufs)

        sf.write(output_path, audio, sr, subtype="PCM_24")
        logger.info(f"Mastering complete: {output_path}")

    def _apply_mastering_eq(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Apply mastering EQ curve"""
        # High-pass at 30Hz
        sos = signal.butter(2, 30 / (sr / 2), btype="high", output="sos")
        audio = signal.sosfilt(sos, audio, axis=0)

        # Gentle high shelf +1dB at 10kHz
        # (simplified - real implementation would use biquad filters)

        return audio

    def _apply_compression(
        self, audio: np.ndarray, ratio: float, threshold_db: float
    ) -> np.ndarray:
        """Mastering compression"""
        threshold = 10 ** (threshold_db / 20)
        mask = np.abs(audio) > threshold
        sign = np.sign(audio)
        abs_audio = np.abs(audio)
        compressed = threshold + (abs_audio - threshold) / ratio
        return np.where(mask, sign * compressed, audio)

    def _apply_limiter(self, audio: np.ndarray, ceiling_db: float) -> np.ndarray:
        """Brick-wall limiter"""
        ceiling = 10 ** (ceiling_db / 20)
        return np.clip(audio, -ceiling, ceiling)

    def _normalize_loudness(self, audio: np.ndarray, target_lufs: float) -> np.ndarray:
        """Normalize to target LUFS"""
        # Simplified LUFS calculation
        rms = np.sqrt(np.mean(audio**2))
        current_lufs = 20 * np.log10(rms + 1e-10) - 23.0

        adjustment = target_lufs - current_lufs
        gain = 10 ** (adjustment / 20)

        return audio * gain
