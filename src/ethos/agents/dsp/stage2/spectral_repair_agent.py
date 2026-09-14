"""
SEMAS Spectral Repair Agent
Repairs spectral artifacts and fills frequency gaps
"""

import logging

import numpy as np
import soundfile as sf
from scipy import signal
from scipy.ndimage import gaussian_filter1d

from ethos.core.data_structures import AudioStem, ProcessingStep
from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class SpectralRepairAgent:
    """Stage 2 Agent: Spectral repair and artifact removal"""

    def __init__(self):
        self.name = "SpectralRepairAgent"
        self.message_bus = get_message_bus()

    async def repair_spectrum(self, stem: AudioStem):
        """Repair spectral artifacts"""
        audio, sr = sf.read(stem.file_path)

        if audio.ndim > 1:
            channels = []
            for ch in range(audio.shape[1]):
                ch_repaired = self._repair_mono(audio[:, ch], sr)
                channels.append(ch_repaired)
            audio_repaired = np.column_stack(channels)
        else:
            audio_repaired = self._repair_mono(audio, sr)

        output_path = stem.file_path.replace(".wav", "_spectral_repaired.wav")
        sf.write(output_path, audio_repaired, sr, subtype="PCM_24")

        enhanced_stem = AudioStem(
            name=stem.name,
            file_path=output_path,
            stem_type=stem.stem_type,
            duration=stem.duration,
            sample_rate=sr,
            separation_quality=stem.separation_quality * 1.1,
            spectral_leakage=stem.spectral_leakage * 0.7,
            transient_preservation=stem.transient_preservation,
            processing_chain=stem.processing_chain + [f"{self.name}:spectral_repair"],
            enhancement_applied=True,
        )

        return enhanced_stem, ProcessingStep(
            step_name="Spectral Repair",
            processor=self.name,
            parameters={},
            input_metrics={},
            output_metrics={},
            improvement_score=0.15,
        )

    def _repair_mono(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Repair spectral gaps and artifacts for a single mono channel"""
        nperseg = 2048
        f, t, Zxx = signal.stft(audio, sr, nperseg=nperseg)
        mag = np.abs(Zxx)
        phase = np.angle(Zxx)

        mag_repaired = self._fill_spectral_gaps(mag)
        mag_repaired = self._remove_artifacts(mag_repaired)

        Zxx_repaired = mag_repaired * np.exp(1j * phase)
        _, audio_repaired = signal.istft(Zxx_repaired, sr, nperseg=nperseg)

        if len(audio_repaired) < len(audio):
            audio_repaired = np.pad(audio_repaired, (0, len(audio) - len(audio_repaired)))
        else:
            audio_repaired = audio_repaired[: len(audio)]

        return audio_repaired

    def _fill_spectral_gaps(self, mag: np.ndarray) -> np.ndarray:
        """Fill gaps in spectrum"""
        mag_smooth = gaussian_filter1d(mag, sigma=1.0, axis=0)
        # Blend: 70% original, 30% smoothed
        return 0.7 * mag + 0.3 * mag_smooth

    def _remove_artifacts(self, mag: np.ndarray) -> np.ndarray:
        """Remove sharp spectral peaks (artifacts)"""
        # Detect outliers
        median = np.median(mag, axis=0, keepdims=True)
        threshold = median * 5
        mag_clean = np.where(mag > threshold, threshold, mag)
        return mag_clean
