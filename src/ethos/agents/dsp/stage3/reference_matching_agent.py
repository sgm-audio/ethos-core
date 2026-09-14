"""SEMAS Reference Matching Agent - Match reference track characteristics"""

import logging

import numpy as np
import soundfile as sf

from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class ReferenceMatchingAgent:
    """Stage 3 Agent: Reference track matching"""

    def __init__(self):
        self.name = "ReferenceMatchingAgent"
        self.message_bus = get_message_bus()

    async def match_reference(self, audio_path: str, reference_path: str):
        """Match spectral and dynamic characteristics of reference"""
        audio, sr = sf.read(audio_path)
        ref_audio, ref_sr = sf.read(reference_path)

        # Analyze reference
        ref_rms = np.sqrt(np.mean(ref_audio**2))
        ref_peak = np.max(np.abs(ref_audio))
        20 * np.log10(ref_peak / (ref_rms + 1e-10))

        # Match characteristics
        audio_rms = np.sqrt(np.mean(audio**2))
        if audio_rms > 0:
            audio_matched = audio * (ref_rms / audio_rms)
        else:
            audio_matched = audio

        output_path = audio_path.replace(".wav", "_matched.wav")
        sf.write(output_path, audio_matched, sr, subtype="PCM_24")
        logger.info("Matched to reference")
        return output_path
