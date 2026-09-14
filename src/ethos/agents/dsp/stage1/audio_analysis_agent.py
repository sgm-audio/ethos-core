"""
SEMAS Audio Analysis Agent
Performs comprehensive audio analysis: tempo, key, structure, frequency, dynamics
"""

import logging

import numpy as np
import soundfile as sf
from scipy import signal
from scipy.fft import fft

from ethos.core.data_structures import (
    AudioAnalysisReport,
    AudioIssue,
    DynamicRange,
    FrequencyAnalysis,
    Section,
    StereoAnalysis,
)
from ethos.core.message_bus import MessagePriority, get_message_bus

logger = logging.getLogger(__name__)


class AudioAnalysisAgent:
    """
    Stage 1 Agent: Comprehensive audio analysis
    Produces: AudioAnalysisReport with tempo, key, structure, frequency, dynamics
    """

    def __init__(self):
        self.name = "AudioAnalysisAgent"
        self.message_bus = get_message_bus()

        # Subscribe to events
        self.message_bus.subscribe("suno.import.complete", self._on_audio_imported)

    async def _on_audio_imported(self, message):
        """Handle new audio file import"""
        file_path = message.payload.get("file_path")
        file_id = message.payload.get("file_id")

        logger.info(f"Analyzing audio: {file_path}")

        # Perform analysis
        report = await self.analyze_audio(file_path, file_id)

        # Publish results
        await self.message_bus.publish(
            topic="analysis.complete",
            payload={"report": report, "file_id": file_id},
            sender=self.name,
            priority=MessagePriority.HIGH,
        )

    async def analyze_audio(self, file_path: str, file_id: str) -> AudioAnalysisReport:
        """Perform comprehensive audio analysis"""

        # Load audio
        audio, sample_rate = sf.read(file_path)

        # Handle mono/stereo
        if audio.ndim == 1:
            audio = np.expand_dims(audio, axis=1)
            channels = 1
        else:
            channels = audio.shape[1]

        duration = len(audio) / sample_rate

        logger.info(f"Loaded audio: {duration:.2f}s, {sample_rate}Hz, {channels}ch")

        # Perform all analysis
        bpm, bpm_confidence = self._detect_tempo(audio, sample_rate)
        key, key_confidence = self._detect_key(audio, sample_rate)
        time_signature = self._detect_time_signature(audio, sample_rate, bpm)
        sections = self._detect_structure(audio, sample_rate, bpm)
        freq_analysis = self._analyze_frequency(audio, sample_rate)
        dynamics = self._analyze_dynamics(audio, sample_rate)
        stereo = self._analyze_stereo(audio, sample_rate) if channels == 2 else None
        quality_score, issues = self._analyze_quality(audio, sample_rate)
        genre, subgenre, mood, energy = self._classify_genre_mood(audio, sample_rate, bpm)

        # Build report
        report = AudioAnalysisReport(
            file_id=file_id,
            file_path=file_path,
            duration=duration,
            sample_rate=sample_rate,
            bit_depth=16,  # soundfile default
            channels=channels,
            bpm=bpm,
            bpm_confidence=bpm_confidence,
            key=key,
            key_confidence=key_confidence,
            time_signature=time_signature,
            sections=sections,
            frequency_analysis=freq_analysis,
            dynamic_range=dynamics,
            stereo_analysis=stereo if stereo else self._get_default_stereo(),
            overall_quality_score=quality_score,
            detected_issues=issues,
            genre=genre,
            subgenre=subgenre,
            mood=mood,
            energy_level=energy,
        )

        logger.info(f"Analysis complete: {bpm:.1f}BPM, {key}, {genre}")

        return report

    def _detect_tempo(self, audio: np.ndarray, sr: int) -> tuple[float, float]:
        """Detect tempo using onset detection and autocorrelation"""

        # Convert to mono for tempo detection
        if audio.ndim > 1:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Onset detection using spectral flux
        hop_length = 512
        n_fft = 2048

        # Compute spectrogram
        f, t, Sxx = signal.spectrogram(audio_mono, sr, nperseg=n_fft, noverlap=n_fft - hop_length)

        # Spectral flux
        flux = np.diff(Sxx, axis=1)
        flux = np.sum(np.maximum(flux, 0), axis=0)

        # Find peaks (onsets)
        from scipy.signal import find_peaks

        peaks, _ = find_peaks(flux, distance=sr // hop_length // 4, prominence=np.mean(flux))

        if len(peaks) < 2:
            return 120.0, 0.3  # Default

        # Calculate inter-onset intervals
        onset_times = peaks * hop_length / sr
        intervals = np.diff(onset_times)

        # Remove outliers
        intervals = intervals[(intervals > 0.2) & (intervals < 2.0)]

        if len(intervals) == 0:
            return 120.0, 0.3

        # Estimate tempo from median interval
        median_interval = np.median(intervals)
        bpm = 60.0 / median_interval

        # Adjust to common range
        while bpm < 60:
            bpm *= 2
        while bpm > 180:
            bpm /= 2

        # Confidence based on interval consistency
        confidence = 1.0 - (np.std(intervals) / np.mean(intervals))
        confidence = np.clip(confidence, 0.0, 1.0)

        return float(bpm), float(confidence)

    def _detect_key(self, audio: np.ndarray, sr: int) -> tuple[str, float]:
        """Detect musical key using chroma features"""

        # Convert to mono
        if audio.ndim > 1:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Compute chromagram
        chroma = self._compute_chroma(audio_mono, sr)

        # Average over time
        chroma_mean = np.mean(chroma, axis=1)

        # Key profiles (Krumhansl-Schmuckler)
        major_profile = np.array(
            [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
        )
        minor_profile = np.array(
            [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
        )

        # Test all keys
        keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        best_correlation = -1
        best_key = "C"
        best_mode = "major"

        for i in range(12):
            # Rotate profile
            major_rot = np.roll(major_profile, i)
            minor_rot = np.roll(minor_profile, i)

            # Calculate correlation
            corr_major = np.corrcoef(chroma_mean, major_rot)[0, 1]
            corr_minor = np.corrcoef(chroma_mean, minor_rot)[0, 1]

            if corr_major > best_correlation:
                best_correlation = corr_major
                best_key = keys[i]
                best_mode = "major"

            if corr_minor > best_correlation:
                best_correlation = corr_minor
                best_key = keys[i]
                best_mode = "minor"

        key_string = f"{best_key} {best_mode}"
        confidence = (best_correlation + 1) / 2  # Normalize to 0-1

        return key_string, float(confidence)

    def _compute_chroma(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Compute chromagram"""

        hop_length = 512
        n_fft = 2048

        # STFT
        f, t, Zxx = signal.stft(audio, sr, nperseg=n_fft, noverlap=n_fft - hop_length)
        magnitude = np.abs(Zxx)

        # Map frequencies to chroma bins
        chroma = np.zeros((12, magnitude.shape[1]))

        for i, freq in enumerate(f):
            if freq < 20:
                continue
            # Calculate chroma bin (0-11)
            chroma_bin = int(np.round(12 * np.log2(freq / 440.0))) % 12
            chroma[chroma_bin, :] += magnitude[i, :]

        return chroma

    def _detect_time_signature(self, audio: np.ndarray, sr: int, bpm: float) -> str:
        """Detect time signature (4/4, 3/4, etc.)"""

        # Simple heuristic: analyze beat strength patterns
        # For now, default to 4/4 (most common in pop/AI music)
        return "4/4"

    def _detect_structure(self, audio: np.ndarray, sr: int, bpm: float) -> list[Section]:
        """Detect song structure (intro, verse, chorus, etc.)"""

        duration = len(audio) / sr

        # Simple structure detection based on energy and spectral changes
        # For Suno tracks, typical structure is: Intro -> Verse -> Chorus -> Verse -> Chorus -> Outro

        sections = []

        # Compute energy envelope
        hop_length = 512
        frame_length = 2048
        energy = self._compute_energy_envelope(audio, sr, hop_length, frame_length)

        # Detect major changes
        change_points = self._detect_structural_changes(energy, sr, hop_length)

        # Add start and end
        change_points = [0.0] + change_points + [duration]

        # Label sections
        section_labels = self._label_sections(change_points, bpm)

        for i in range(len(change_points) - 1):
            start_time = change_points[i]
            end_time = change_points[i + 1]

            # Convert to bars (assuming 4/4)
            beats_per_bar = 4
            start_bar = int(start_time * bpm / 60.0 / beats_per_bar)
            end_bar = int(end_time * bpm / 60.0 / beats_per_bar)

            sections.append(
                Section(
                    name=section_labels[i],
                    start_time=start_time,
                    end_time=end_time,
                    start_bar=start_bar,
                    end_bar=end_bar,
                    confidence=0.7,
                )
            )

        return sections

    def _compute_energy_envelope(
        self, audio: np.ndarray, sr: int, hop_length: int, frame_length: int
    ) -> np.ndarray:
        """Compute energy envelope"""

        if audio.ndim > 1:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Frame-based energy
        n_frames = (len(audio_mono) - frame_length) // hop_length + 1
        energy = np.zeros(n_frames)

        for i in range(n_frames):
            start = i * hop_length
            end = start + frame_length
            frame = audio_mono[start:end]
            energy[i] = np.sum(frame**2)

        return energy

    def _detect_structural_changes(
        self, energy: np.ndarray, sr: int, hop_length: int
    ) -> list[float]:
        """Detect structural change points"""

        # Smooth energy
        from scipy.ndimage import gaussian_filter1d

        energy_smooth = gaussian_filter1d(energy, sigma=20)

        # Find large changes
        diff = np.abs(np.diff(energy_smooth))
        threshold = np.mean(diff) + np.std(diff)

        from scipy.signal import find_peaks

        peaks, _ = find_peaks(diff, height=threshold, distance=sr // hop_length * 2)

        # Convert to time
        change_points = [(p * hop_length) / sr for p in peaks]

        return change_points

    def _label_sections(self, change_points: list[float], bpm: float) -> list[str]:
        """Label sections based on position and duration"""

        labels = []
        n_sections = len(change_points) - 1

        # Typical Suno structure
        if n_sections <= 2:
            labels = ["Intro", "Main"]
        elif n_sections == 3:
            labels = ["Intro", "Verse", "Chorus"]
        elif n_sections == 4:
            labels = ["Intro", "Verse", "Chorus", "Outro"]
        elif n_sections == 5:
            labels = ["Intro", "Verse 1", "Chorus", "Verse 2", "Outro"]
        elif n_sections == 6:
            labels = ["Intro", "Verse 1", "Chorus 1", "Verse 2", "Chorus 2", "Outro"]
        else:
            # More complex structure
            labels = ["Intro"]
            for i in range(1, n_sections - 1):
                if i % 2 == 1:
                    labels.append(f"Verse {(i + 1) // 2}")
                else:
                    labels.append(f"Chorus {i // 2}")
            labels.append("Outro")

        return labels

    def _analyze_frequency(self, audio: np.ndarray, sr: int) -> FrequencyAnalysis:
        """Analyze frequency spectrum"""

        if audio.ndim > 1:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Compute FFT
        n_fft = 8192
        spectrum = np.abs(fft(audio_mono[:n_fft]))
        frequencies = np.fft.fftfreq(n_fft, 1 / sr)[: n_fft // 2]
        spectrum = spectrum[: n_fft // 2]

        # Spectral features
        spectral_centroid = np.sum(frequencies * spectrum) / np.sum(spectrum)

        # Spectral rolloff (95% energy)
        cumsum = np.cumsum(spectrum)
        rolloff_idx = np.where(cumsum >= 0.95 * cumsum[-1])[0][0]
        spectral_rolloff = frequencies[rolloff_idx]

        # Spectral flatness
        geometric_mean = np.exp(np.mean(np.log(spectrum + 1e-10)))
        arithmetic_mean = np.mean(spectrum)
        spectral_flatness = geometric_mean / arithmetic_mean

        # Band energy
        def band_energy(f_low, f_high):
            mask = (frequencies >= f_low) & (frequencies <= f_high)
            band_power = np.sum(spectrum[mask])
            return 20 * np.log10(band_power + 1e-10)

        return FrequencyAnalysis(
            spectrum=spectrum,
            frequencies=frequencies,
            spectral_centroid=float(spectral_centroid),
            spectral_rolloff=float(spectral_rolloff),
            spectral_flatness=float(spectral_flatness),
            sub_bass=band_energy(20, 60),
            bass=band_energy(60, 250),
            low_mids=band_energy(250, 500),
            mids=band_energy(500, 2000),
            upper_mids=band_energy(2000, 4000),
            presence=band_energy(4000, 8000),
            brilliance=band_energy(8000, 20000),
        )

    def _analyze_dynamics(self, audio: np.ndarray, sr: int) -> DynamicRange:
        """Analyze dynamic range"""

        # Peak
        peak_db = 20 * np.log10(np.max(np.abs(audio)) + 1e-10)

        # RMS
        rms = np.sqrt(np.mean(audio**2))
        rms_db = 20 * np.log10(rms + 1e-10)

        # LUFS (simplified - true LUFS requires K-weighting)
        # This is a simplified approximation
        lufs_integrated = rms_db - 23.0  # Approximate conversion
        lufs_short_term = lufs_integrated
        lufs_momentary = lufs_integrated

        # True peak
        true_peak_db = peak_db

        # Dynamic range (simplified DR meter)
        # True DR requires percentile analysis
        dynamic_range = peak_db - rms_db

        # Crest factor
        crest_factor = peak_db - rms_db

        return DynamicRange(
            peak_db=float(peak_db),
            rms_db=float(rms_db),
            lufs_integrated=float(lufs_integrated),
            lufs_short_term=float(lufs_short_term),
            lufs_momentary=float(lufs_momentary),
            true_peak_db=float(true_peak_db),
            dynamic_range=float(dynamic_range),
            crest_factor=float(crest_factor),
        )

    def _analyze_stereo(self, audio: np.ndarray, sr: int) -> StereoAnalysis:
        """Analyze stereo field"""

        if audio.shape[1] != 2:
            return self._get_default_stereo()

        left = audio[:, 0]
        right = audio[:, 1]

        # Correlation
        correlation = np.corrcoef(left, right)[0, 1]

        # Width (based on mid/side energy ratio)
        mid = (left + right) / 2
        side = (left - right) / 2

        mid_energy = np.sum(mid**2)
        side_energy = np.sum(side**2)

        if mid_energy > 0:
            width = 100 * (side_energy / mid_energy)
        else:
            width = 100.0

        # Balance
        left_energy = np.sum(left**2)
        right_energy = np.sum(right**2)
        total_energy = left_energy + right_energy

        if total_energy > 0:
            balance = 100 * (right_energy - left_energy) / total_energy
        else:
            balance = 0.0

        # Mono compatibility
        mono_compatible = correlation > 0.5

        # Phase issues
        phase_issues = []
        if correlation < 0:
            phase_issues.append("Phase cancellation detected")
        if correlation < 0.3:
            phase_issues.append("Poor mono compatibility")

        return StereoAnalysis(
            correlation=float(correlation),
            width=float(width),
            balance=float(balance),
            mono_compatible=mono_compatible,
            phase_issues=phase_issues,
        )

    def _get_default_stereo(self) -> StereoAnalysis:
        """Default stereo analysis for mono files"""
        return StereoAnalysis(
            correlation=1.0, width=0.0, balance=0.0, mono_compatible=True, phase_issues=[]
        )

    def _analyze_quality(self, audio: np.ndarray, sr: int) -> tuple[float, list[AudioIssue]]:
        """Analyze audio quality and detect issues"""

        issues = []
        quality_score = 1.0

        # Check for clipping
        clipping_threshold = 0.99
        clipped_samples = np.sum(np.abs(audio) > clipping_threshold)
        if clipped_samples > 0:
            severity = min(clipped_samples / len(audio), 1.0)
            issues.append(
                AudioIssue(
                    issue_type="clipping",
                    severity=float(severity),
                    location=0.0,
                    description=f"{clipped_samples} clipped samples detected",
                    recommended_fix="Apply soft clipping or reduce gain",
                )
            )
            quality_score -= 0.3 * severity

        # Check for silence
        silence_threshold = 0.001
        silent_samples = np.sum(np.abs(audio) < silence_threshold)
        if silent_samples > len(audio) * 0.1:
            issues.append(
                AudioIssue(
                    issue_type="silence",
                    severity=0.3,
                    location=0.0,
                    description="Extended silence detected",
                    recommended_fix="Trim silence or check for dropouts",
                )
            )
            quality_score -= 0.1

        # Check for DC offset
        dc_offset = np.mean(audio)
        if abs(dc_offset) > 0.01:
            issues.append(
                AudioIssue(
                    issue_type="dc_offset",
                    severity=float(abs(dc_offset)),
                    location=0.0,
                    description=f"DC offset detected: {dc_offset:.4f}",
                    recommended_fix="Apply DC offset removal",
                )
            )
            quality_score -= 0.1

        quality_score = max(0.0, quality_score)

        return quality_score, issues

    def _classify_genre_mood(
        self, audio: np.ndarray, sr: int, bpm: float
    ) -> tuple[str, str, list[str], float]:
        """Classify genre, mood, and energy level"""

        # Simple heuristic-based classification
        # In production, would use trained ML model

        # Energy level (0-1)
        rms = np.sqrt(np.mean(audio**2))
        energy_level = min(rms * 10, 1.0)

        # Genre classification based on tempo and spectral features
        if bpm < 90:
            genre = "Ballad"
            subgenre = "Slow"
            mood = ["Melancholic", "Emotional"]
        elif bpm < 110:
            genre = "Pop"
            subgenre = "Midtempo"
            mood = ["Uplifting", "Emotional"]
        elif bpm < 130:
            genre = "Pop"
            subgenre = "Uptempo"
            mood = ["Energetic", "Happy"]
        else:
            genre = "Electronic"
            subgenre = "Dance"
            mood = ["Energetic", "Exciting"]

        return genre, subgenre, mood, float(energy_level)
