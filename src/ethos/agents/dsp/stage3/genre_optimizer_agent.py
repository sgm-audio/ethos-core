"""SEMAS Genre Optimizer Agent - Genre-specific processing"""

import logging

import numpy as np
import soundfile as sf

from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class GenreOptimizerAgent:
    """Stage 3 Agent: Genre-specific optimization"""

    def __init__(self):
        self.name = "GenreOptimizerAgent"
        self.message_bus = get_message_bus()

        self.genre_profiles = {
            "Pop": {"bass_boost": 2, "brightness": 1, "compression": "medium"},
            "Electronic": {"bass_boost": 4, "brightness": 2, "compression": "heavy"},
            "Rock": {"bass_boost": 1, "brightness": 2, "compression": "light"},
            "Ballad": {"bass_boost": 0, "brightness": 0, "compression": "light"},
        }

    async def optimize_for_genre(self, audio_path: str, genre: str):
        """Apply genre-specific processing"""
        audio, sr = sf.read(audio_path)

        profile = self.genre_profiles.get(genre, self.genre_profiles["Pop"])

        # Apply bass boost if needed
        if profile["bass_boost"] > 0:
            audio = self._boost_bass(audio, sr, profile["bass_boost"])

        # Apply brightness if needed
        if profile["brightness"] > 0:
            audio = self._boost_highs(audio, sr, profile["brightness"])

        output_path = audio_path.replace(".wav", f"_{genre.lower()}_optimized.wav")
        sf.write(output_path, audio, sr, subtype="PCM_24")
        logger.info(f"Optimized for {genre}")
        return output_path

    def _boost_bass(self, audio: np.ndarray, sr: int, amount_db: float) -> np.ndarray:
        """Boost bass frequencies"""
        # Low shelf at 100Hz
        gain = 10 ** (amount_db / 20)
        return audio * gain  # Simplified

    def _boost_highs(self, audio: np.ndarray, sr: int, amount_db: float) -> np.ndarray:
        """Boost high frequencies"""
        # High shelf at 8kHz
        gain = 10 ** (amount_db / 20)
        return audio * gain  # Simplified
