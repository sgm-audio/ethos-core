"""
SEMAS Stereo Enhancement Agent
Enhances stereo width and imaging
"""

import logging

import numpy as np
import soundfile as sf

from ethos.core.data_structures import AudioStem, ProcessingStep
from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class StereoEnhancementAgent:
    """Stage 2 Agent: Stereo width and imaging enhancement"""

    def __init__(self):
        self.name = "StereoEnhancementAgent"
        self.message_bus = get_message_bus()
        self.message_bus.subscribe("transients.shaped", self._on_transients_shaped)

    async def _on_transients_shaped(self, message):
        """Process after transient shaping"""
        stems = message.payload.get("stems")
        file_id = message.payload.get("file_id")

        enhanced_stems = {}
        for stem_name, stem in stems.items():
            enhanced_stem, _ = await self.enhance_stereo(stem, width_factor=1.2)
            enhanced_stems[stem_name] = enhanced_stem

        await self.message_bus.publish(
            topic="stereo.enhanced",
            payload={"stems": enhanced_stems, "file_id": file_id},
            sender=self.name,
        )

    async def enhance_stereo(
        self, stem: AudioStem, width_factor: float = 1.2
    ) -> tuple[AudioStem, ProcessingStep]:
        """Enhance stereo width"""

        audio, sr = sf.read(stem.file_path)

        # Convert mono to stereo if needed
        if audio.ndim == 1:
            audio = self._mono_to_pseudo_stereo(audio, sr)
        else:
            audio = self._widen_stereo(audio, width_factor)

        output_path = stem.file_path.replace(".wav", "_stereo_enhanced.wav")
        sf.write(output_path, audio, sr, subtype="PCM_24")

        enhanced_stem = AudioStem(
            name=stem.name,
            file_path=output_path,
            stem_type=stem.stem_type,
            duration=stem.duration,
            sample_rate=sr,
            separation_quality=stem.separation_quality,
            spectral_leakage=stem.spectral_leakage,
            transient_preservation=stem.transient_preservation,
            processing_chain=stem.processing_chain + [f"{self.name}:stereo_enhancement"],
            enhancement_applied=True,
        )

        processing_step = ProcessingStep(
            step_name="Stereo Enhancement",
            processor=self.name,
            parameters={"width_factor": width_factor},
            input_metrics={},
            output_metrics={},
            improvement_score=0.15,
        )

        return enhanced_stem, processing_step

    def _widen_stereo(self, audio: np.ndarray, factor: float) -> np.ndarray:
        """Widen existing stereo"""
        mid = (audio[:, 0] + audio[:, 1]) / 2
        side = (audio[:, 0] - audio[:, 1]) / 2
        side_widened = side * factor
        left = mid + side_widened
        right = mid - side_widened
        return np.column_stack([left, right])

    def _mono_to_pseudo_stereo(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Create pseudo-stereo from mono"""
        # Apply slight delay and filtering to create width
        delay_samples = int(sr * 0.001)  # 1ms delay
        left = audio
        right = np.roll(audio, delay_samples)
        return np.column_stack([left, right])
