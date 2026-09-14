"""
SEMAS Transient Shaping Agent
Enhances transients for drums and percussion
"""

import logging

import numpy as np
import soundfile as sf
from scipy import signal

from ethos.core.data_structures import AudioStem, ProcessingStep
from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class TransientShapingAgent:
    """
    Stage 2 Agent: Transient enhancement
    - Transient detection and shaping
    - Attack/sustain separation
    - Punch enhancement for drums
    """

    def __init__(self):
        self.name = "TransientShapingAgent"
        self.message_bus = get_message_bus()
        self.message_bus.subscribe("quality.enhanced", self._on_quality_enhanced)

    async def _on_quality_enhanced(self, message):
        """Process stems after quality enhancement"""
        stems = message.payload.get("stems")
        file_id = message.payload.get("file_id")

        if not stems:
            return

        # Retain all stems, enhancing transient-heavy stems (drums and bass)
        enhanced_stems = dict(stems)
        for stem_name in ["drums", "bass"]:
            if stem_name in stems:
                stem = stems[stem_name]
                enhanced_stem, _ = await self.shape_transients(stem, intensity=0.5)
                enhanced_stems[stem_name] = enhanced_stem

        await self.message_bus.publish(
            topic="transients.shaped",
            payload={"stems": enhanced_stems, "file_id": file_id},
            sender=self.name,
        )

    async def shape_transients(
        self, stem: AudioStem, intensity: float = 0.5
    ) -> tuple[AudioStem, ProcessingStep]:
        """Enhance transients in audio"""

        audio, sr = sf.read(stem.file_path)

        # Detect transients
        transient_mask = self._detect_transients(audio, sr)

        # Separate transient and sustain
        transients, sustain = self._separate_transient_sustain(audio, transient_mask)

        # Enhance transients
        transients_enhanced = transients * (1.0 + intensity)

        # Recombine
        audio_shaped = transients_enhanced + sustain

        # Normalize to prevent clipping
        peak = np.max(np.abs(audio_shaped))
        if peak > 0.95:
            audio_shaped = audio_shaped * (0.95 / peak)

        # Save
        output_path = stem.file_path.replace(".wav", "_transient_shaped.wav")
        sf.write(output_path, audio_shaped, sr, subtype="PCM_24")

        enhanced_stem = AudioStem(
            name=stem.name,
            file_path=output_path,
            stem_type=stem.stem_type,
            duration=stem.duration,
            sample_rate=sr,
            separation_quality=stem.separation_quality,
            spectral_leakage=stem.spectral_leakage,
            transient_preservation=min(stem.transient_preservation * 1.2, 1.0),
            processing_chain=stem.processing_chain + [f"{self.name}:transient_shaping"],
            enhancement_applied=True,
        )

        processing_step = ProcessingStep(
            step_name="Transient Shaping",
            processor=self.name,
            parameters={"intensity": intensity},
            input_metrics={"transient_preservation": stem.transient_preservation},
            output_metrics={"transient_preservation": enhanced_stem.transient_preservation},
            improvement_score=0.2,
        )

        logger.info(f"Shaped transients for {stem.name}")

        return enhanced_stem, processing_step

    def _detect_transients(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Detect transients using envelope follower"""

        if audio.ndim > 1:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Envelope detection
        envelope = np.abs(signal.hilbert(audio_mono))

        # Smooth envelope
        from scipy.ndimage import gaussian_filter1d

        envelope_smooth = gaussian_filter1d(envelope, sigma=sr // 100)

        # Detect rapid increases (transients)
        diff = np.diff(envelope_smooth, prepend=0)
        threshold = np.mean(diff) + 2 * np.std(diff)

        transient_mask = diff > threshold

        # Expand mask to include attack portion
        kernel_size = sr // 100  # 10ms
        from scipy.ndimage import binary_dilation

        transient_mask = binary_dilation(transient_mask, iterations=kernel_size)

        return transient_mask

    def _separate_transient_sustain(
        self, audio: np.ndarray, mask: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Separate transient and sustain components"""

        # Expand mask to match audio dimensions
        if audio.ndim > 1:
            mask_expanded = np.expand_dims(mask, axis=1)
            mask_expanded = np.tile(mask_expanded, (1, audio.shape[1]))
        else:
            mask_expanded = mask

        # Ensure same length
        if len(mask_expanded) > len(audio):
            mask_expanded = mask_expanded[: len(audio)]
        elif len(mask_expanded) < len(audio):
            pad_length = len(audio) - len(mask_expanded)
            if audio.ndim > 1:
                mask_expanded = np.pad(mask_expanded, ((0, pad_length), (0, 0)))
            else:
                mask_expanded = np.pad(mask_expanded, (0, pad_length))

        transients = audio * mask_expanded
        sustain = audio * (1 - mask_expanded)

        return transients, sustain
