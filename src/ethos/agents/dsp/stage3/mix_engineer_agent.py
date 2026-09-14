"""
SEMAS Mix Engineer Agent
Automated mixing: balance, panning, EQ, compression
"""

import logging

import numpy as np
import soundfile as sf

from ethos.core.data_structures import AudioStem, MixParameters
from ethos.core.message_bus import MessagePriority, get_message_bus

logger = logging.getLogger(__name__)


class MixEngineerAgent:
    """
    Stage 3 Agent: Automated mixing
    - Stem balancing (volume levels)
    - Panning decisions
    - EQ for frequency separation
    - Bus routing
    """

    def __init__(self):
        self.name = "MixEngineerAgent"
        self.message_bus = get_message_bus()

        # Genre-specific mix templates
        self.mix_templates = {
            "Pop": {"vocals": 0, "drums": -3, "bass": -6, "other": -9},
            "Electronic": {"vocals": -3, "drums": 0, "bass": -3, "other": -6},
            "Ballad": {"vocals": 0, "drums": -6, "bass": -9, "other": -3},
            "Rock": {"vocals": 0, "drums": -3, "bass": -6, "other": -6},
        }

        self.message_bus.subscribe("stereo.enhanced", self._on_stereo_enhanced)

    async def _on_stereo_enhanced(self, message):
        """Mix stems after all enhancements"""
        stems = message.payload.get("stems")
        file_id = message.payload.get("file_id")

        # Get analysis report for genre
        # For now, default to Pop
        genre = "Pop"

        logger.info(f"Mixing stems for {file_id} ({genre})")

        mix_params = await self.create_mix(stems, genre)

        await self.message_bus.publish(
            topic="mix.created",
            payload={"mix_parameters": mix_params, "stems": stems, "file_id": file_id},
            sender=self.name,
            priority=MessagePriority.HIGH,
        )

    async def create_mix(self, stems: dict[str, AudioStem], genre: str) -> MixParameters:
        """Create balanced mix"""

        # Get mix template
        levels = self.mix_templates.get(genre, self.mix_templates["Pop"])

        # Pan positions
        pans = {
            "vocals": 0.0,  # Center
            "drums": 0.0,  # Center
            "bass": 0.0,  # Center
            "other": 0.0,  # Center (instruments will be in stereo already)
        }

        # Bus routing
        bus_routing = {
            "master": ["vocals", "drums", "bass", "other"],
            "rhythm": ["drums", "bass"],
            "melodic": ["vocals", "other"],
        }

        # Send effects (reverb, delay)
        send_effects = {
            "reverb": {
                "vocals": 0.3,  # 30% send
                "drums": 0.1,
                "bass": 0.05,
                "other": 0.2,
            },
            "delay": {"vocals": 0.2, "other": 0.15},
        }

        mix_params = MixParameters(
            stem_levels=levels, stem_pans=pans, bus_routing=bus_routing, send_effects=send_effects
        )

        logger.info(f"Created {genre} mix: {levels}")

        return mix_params

    async def apply_mix_to_stems(
        self, stems: dict[str, AudioStem], mix_params: MixParameters
    ) -> dict[str, np.ndarray]:
        """Apply mix parameters to stems"""

        processed_stems = {}

        for stem_name, stem in stems.items():
            audio, sr = sf.read(stem.file_path)

            # Apply level
            level_db = mix_params.stem_levels.get(stem_name, 0.0)
            level_linear = 10 ** (level_db / 20)
            audio = audio * level_linear

            # Apply pan (if stereo)
            if audio.ndim == 2 and stem_name in mix_params.stem_pans:
                pan = mix_params.stem_pans[stem_name]
                audio = self._apply_pan(audio, pan)

            processed_stems[stem_name] = audio

        return processed_stems

    def _apply_pan(self, audio: np.ndarray, pan: float) -> np.ndarray:
        """Apply panning (-1 = left, 0 = center, 1 = right)"""

        if audio.ndim == 1:
            # Mono to stereo with pan
            left_gain = np.sqrt((1 - pan) / 2)
            right_gain = np.sqrt((1 + pan) / 2)
            left = audio * left_gain
            right = audio * right_gain
            return np.column_stack([left, right])
        else:
            # Stereo panning
            left_gain = np.sqrt((1 - pan) / 2)
            right_gain = np.sqrt((1 + pan) / 2)
            audio[:, 0] *= left_gain
            audio[:, 1] *= right_gain
            return audio

    async def render_mix(self, processed_stems: dict[str, np.ndarray], output_path: str, sr: int):
        """Sum stems and render final mix"""

        # Find longest stem
        max_length = max(len(audio) for audio in processed_stems.values())

        # Pad all stems to same length
        for stem_name in processed_stems:
            audio = processed_stems[stem_name]
            if len(audio) < max_length:
                if audio.ndim == 1:
                    processed_stems[stem_name] = np.pad(audio, (0, max_length - len(audio)))
                else:
                    processed_stems[stem_name] = np.pad(
                        audio, ((0, max_length - len(audio)), (0, 0))
                    )

        # Sum all stems
        mix = np.zeros((max_length, 2))  # Stereo output
        for _stem_name, audio in processed_stems.items():
            if audio.ndim == 1:
                # Mono to stereo
                audio = np.column_stack([audio, audio])
            mix += audio

        # Normalize to -1 dB peak
        peak = np.max(np.abs(mix))
        if peak > 0:
            target_peak = 10 ** (-1.0 / 20)  # -1 dB
            mix = mix * (target_peak / peak)

        # Write
        sf.write(output_path, mix, sr, subtype="PCM_24")
        logger.info(f"Mix rendered to: {output_path}")
