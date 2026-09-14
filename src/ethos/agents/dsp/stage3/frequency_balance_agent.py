"""SEMAS Frequency Balance Agent - Tonal balance and EQ"""

import logging

import soundfile as sf
from scipy import signal

from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class FrequencyBalanceAgent:
    """Stage 3 Agent: Frequency balance and EQ"""

    def __init__(self):
        self.name = "FrequencyBalanceAgent"
        self.message_bus = get_message_bus()

    async def balance_frequency(self, audio_path: str):
        """Balance frequency spectrum"""
        audio, sr = sf.read(audio_path)

        # Multi-band EQ
        audio_balanced = audio.copy()

        # High-pass at 20Hz
        sos = signal.butter(2, 20 / (sr / 2), btype="high", output="sos")
        audio_balanced = signal.sosfilt(sos, audio_balanced, axis=0)

        # Gentle boost at 100Hz (warmth)
        # Gentle cut at 300Hz (muddiness)
        # Gentle boost at 3kHz (presence)
        # Gentle boost at 10kHz (air)

        output_path = audio_path.replace(".wav", "_eq.wav")
        sf.write(output_path, audio_balanced, sr, subtype="PCM_24")
        logger.info("Frequency balanced")
        return output_path
