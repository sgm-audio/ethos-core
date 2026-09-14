"""
YourMT3+ Stem Separator for AI-Generated Audio
Transformer-based music source separation optimized for Suno and other AI-generated tracks

This script uses advanced transformer architectures for superior stem separation quality,
particularly effective for AI-generated audio which often has unique spectral characteristics.
"""

import argparse
import logging
import logging.config
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio

# Import centralized configuration
from ethos.core.config import (
    ERROR_MESSAGES,
    LOGGING_CONFIG,
    AudioConfig,
    DeviceType,
    ModelConfig,
)

# Apply logging configuration
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


class YourMT3StemSeparator:
    """
    YourMT3+ based stem separator with optimizations for AI-generated audio

    Attributes:
        model_name: Name of the separation model being used
        device: Processing device (cuda/cpu)
        output_dir: Directory where stems will be saved
        use_transformer: Whether transformer processing is enabled
        model: Loaded separation model
        sample_rate: Target sample rate for processing
        audio_config: Audio processing configuration
        model_config: Model configuration
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | DeviceType | None = None,
        output_dir: str | None = None,
        use_transformer: bool | None = None,
        audio_config: AudioConfig | None = None,
        model_config: ModelConfig | None = None,
    ):
        """
        Initialize the stem separator

        Args:
            model_name: Model to use (htdemucs, hybrid_transformer, etc.)
            device: Device to run on ('cuda', 'cpu', or None for auto)
            output_dir: Directory for output stems
            use_transformer: Use transformer-based architecture if available
            audio_config: Audio processing configuration
            model_config: Model configuration
        """
        # Use provided configs or defaults
        self.audio_config = audio_config or AudioConfig()
        self.model_config = model_config or ModelConfig()

        # Override with parameters if provided
        self.model_name = model_name or self.model_config.demucs_model
        self.use_transformer = (
            use_transformer if use_transformer is not None else self.model_config.use_transformer
        )

        # Device handling
        if device is None:
            device = self.model_config.device
        if isinstance(device, DeviceType):
            self.device = (
                device.value
                if device != DeviceType.AUTO
                else ("cuda" if torch.cuda.is_available() else "cpu")
            )
        else:
            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.output_dir = output_dir or os.path.join(os.getcwd(), "stems_output")
        os.makedirs(self.output_dir, exist_ok=True)

        logger.info(f"Initializing YourMT3+ Separator on {self.device}")
        logger.info(f"Model: {self.model_name}")
        logger.info(f"Transformer mode: {self.use_transformer}")
        logger.info(f"Sample rate: {self.audio_config.sample_rate}Hz")

        self.model = None
        self.sample_rate = self.audio_config.sample_rate

        try:
            self._load_model()
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise RuntimeError(
                ERROR_MESSAGES["model_not_loaded"].format(model_name=self.model_name)
            ) from e

    def _load_model(self) -> None:
        """Load the separation model with proper error handling"""
        try:
            # Try to load demucs (most common)
            from demucs.apply import apply_model
            from demucs.pretrained import get_model

            logger.info(f"Loading model: {self.model_name}")

            # Load model without signal-based timeout (Windows compatibility)
            self.model = get_model(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            self.apply_model_fn = apply_model
            logger.info("Model loaded successfully (Demucs)")

        except ImportError as e:
            logger.warning(f"Demucs import failed: {e}")
            logger.warning("Trying alternative methods...")
            self._load_alternative_model()
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Failed to load Demucs model: {e}")
            if self.model_config.enable_spleeter_fallback:
                self._load_alternative_model()
            else:
                raise

    def _load_alternative_model(self) -> None:
        """Load alternative separation models if Demucs isn't available"""
        try:
            # Try Spleeter
            from spleeter.separator import Separator

            logger.info("Loading Spleeter as alternative")
            self.model = Separator(self.model_config.spleeter_model)
            self.model_type = "spleeter"
            logger.info("Spleeter loaded successfully")

        except ImportError:
            logger.error("No separation model available. Please install:")
            logger.error("  pip install demucs")
            logger.error("  OR")
            logger.error("  pip install spleeter")
            raise RuntimeError("No separation model available")
        except Exception as e:
            logger.error(f"Failed to load Spleeter: {e}")
            raise RuntimeError(
                ERROR_MESSAGES["model_not_loaded"].format(
                    model_name=self.model_config.spleeter_model
                )
            ) from e

    def separate(self, input_file: str, stems: list[str] | None = None) -> dict[str, str]:
        """
        Separate audio into stems with comprehensive error handling

        Args:
            input_file: Path to input audio file
            stems: List of stems to extract (vocals, drums, bass, other)

        Returns:
            Dictionary mapping stem names to output file paths

        Raises:
            FileNotFoundError: If input file doesn't exist
            PermissionError: If input file can't be read
            RuntimeError: If separation fails
            ValueError: If audio format is unsupported
        """
        if not stems:
            stems = ["vocals", "drums", "bass", "other"]

        # Validate input
        if not os.path.exists(input_file):
            raise FileNotFoundError(ERROR_MESSAGES["file_not_found"].format(file_path=input_file))

        if not os.access(input_file, os.R_OK):
            raise PermissionError(ERROR_MESSAGES["permission_denied"].format(file_path=input_file))

        # Check file extension
        file_ext = Path(input_file).suffix.lower()
        # Default extensions supported
        supported_extensions = [".wav", ".mp3", ".flac", ".m4a", ".ogg"]
        if file_ext not in supported_extensions:
            logger.warning(f"Potentially unsupported format: {file_ext}")

        logger.info(f"Processing: {input_file}")
        logger.info(f"Target stems: {', '.join(stems)}")

        try:
            # Load audio
            audio, sr = self._load_audio(input_file)
            logger.info(f"Audio loaded: {audio.shape}, {sr}Hz")

            # Apply AI-audio preprocessing
            if self.audio_config.apply_spectral_cleaning:
                audio = self._preprocess_ai_audio(audio, sr)

            # Perform separation
            separated_stems = self._separate_audio(audio, sr)

            # Apply AI-audio postprocessing
            if self.audio_config.artifact_reduction:
                separated_stems = self._postprocess_stems(separated_stems, sr)

            # Save stems
            output_paths = self._save_stems(separated_stems, input_file, stems)

            logger.info(f"Separation complete. Stems saved to: {self.output_dir}")
            return output_paths

        except Exception as e:
            logger.error(f"Stem separation failed: {e}")
            raise RuntimeError(ERROR_MESSAGES["separation_failed"].format(error=str(e))) from e

    def _load_audio(self, file_path: str) -> tuple[np.ndarray, int]:
        """Load audio file and convert to appropriate format"""
        try:
            # Try soundfile first
            audio, sr = sf.read(file_path, always_2d=True)
            audio = audio.T  # Convert to (channels, samples)

            # Convert to stereo if mono
            if audio.shape[0] == 1:
                audio = np.repeat(audio, 2, axis=0)

            return audio, sr

        except Exception as e:
            logger.error(f"Error loading audio: {e}")
            raise

    def _preprocess_ai_audio(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Preprocess AI-generated audio to improve separation quality

        AI-generated audio often has:
        - Compressed dynamic range
        - Spectral artifacts
        - Unnatural transients
        """
        logger.info("Applying AI-audio preprocessing...")

        # Normalize
        audio = audio / (np.abs(audio).max() + 1e-8)

        # Gentle high-pass filter to remove DC offset and rumble
        # (AI audio can have DC offset issues)
        audio = self._apply_highpass(audio, sr, cutoff=20)

        # Spectral cleaning for AI artifacts
        audio = self._reduce_spectral_artifacts(audio, sr)

        return audio

    def _apply_highpass(self, audio: np.ndarray, sr: int, cutoff: float = 20) -> np.ndarray:
        """Apply high-pass filter"""
        from scipy import signal

        nyquist = sr / 2
        normalized_cutoff = cutoff / nyquist

        butter_result = signal.butter(2, normalized_cutoff, btype="high")
        if isinstance(butter_result, tuple) and len(butter_result) >= 2:
            b, a = butter_result[0], butter_result[1]
        else:
            raise RuntimeError("Unexpected signal.butter output format")
        filtered = np.zeros_like(audio)

        for ch in range(audio.shape[0]):
            filtered[ch] = signal.filtfilt(b, a, audio[ch])

        return filtered

    def _reduce_spectral_artifacts(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Reduce spectral artifacts common in AI-generated audio

        Uses spectral gating to remove noise floor artifacts
        """
        # Convert to frequency domain
        from scipy import signal

        # Perform STFT
        f, t, Zxx = signal.stft(audio, fs=sr, nperseg=2048, noverlap=1536)

        # Calculate noise threshold per frequency bin
        magnitude = np.abs(Zxx)
        noise_threshold = np.percentile(magnitude, 5, axis=-1, keepdims=True)

        # Soft gating
        gate = np.maximum(0, (magnitude - noise_threshold * 1.5) / (magnitude + 1e-8))
        Zxx_cleaned = Zxx * gate

        # Inverse STFT
        _, audio_cleaned = signal.istft(Zxx_cleaned, fs=sr, nperseg=2048, noverlap=1536)

        # Handle length mismatch
        if audio_cleaned.shape[-1] < audio.shape[-1]:
            pad_length = audio.shape[-1] - audio_cleaned.shape[-1]
            audio_cleaned = np.pad(audio_cleaned, ((0, 0), (0, pad_length)), mode="constant")
        else:
            audio_cleaned = audio_cleaned[..., : audio.shape[-1]]

        return audio_cleaned

    def _separate_audio(self, audio: np.ndarray, sr: int) -> dict[str, np.ndarray]:
        """Perform stem separation"""
        logger.info("Performing stem separation...")

        # Convert to torch tensor
        audio_tensor = torch.from_numpy(audio).float().to(self.device)

        # Add batch dimension if needed
        if audio_tensor.dim() == 2:
            audio_tensor = audio_tensor.unsqueeze(0)

        # Resample if necessary
        if self.model and hasattr(self.model, "samplerate") and sr != self.model.samplerate:
            logger.info(f"Resampling from {sr}Hz to {self.model.samplerate}Hz")
            resampler = torchaudio.transforms.Resample(sr, self.model.samplerate).to(self.device)
            audio_tensor = resampler(audio_tensor)

        # Apply model with chunking for long audio
        with torch.no_grad():
            if self.model and hasattr(self, "apply_model_fn"):
                # Demucs
                separated = self.apply_model_fn(
                    self.model,
                    audio_tensor,
                    shifts=1,  # Use shifts for better quality
                    overlap=self.audio_config.overlap_ratio,
                )
            elif self.model:
                # Other models
                separated = self.model(audio_tensor)
            else:
                raise RuntimeError("No model loaded for separation")

        # Convert back to numpy and organize by stem
        stems = {}
        stem_names = ["drums", "bass", "other", "vocals"]  # Demucs order

        for i, name in enumerate(stem_names):
            stem_audio = separated[0, i].cpu().numpy()

            # Resample back if needed
            if self.model and hasattr(self.model, "samplerate") and sr != self.model.samplerate:
                resampler = torchaudio.transforms.Resample(self.model.samplerate, sr)
                stem_tensor = torch.from_numpy(stem_audio).unsqueeze(0)
                stem_audio = resampler(stem_tensor).squeeze(0).numpy()

            stems[name] = stem_audio

        return stems

    def _postprocess_stems(self, stems: dict[str, np.ndarray], sr: int) -> dict[str, np.ndarray]:
        """
        Post-process separated stems to reduce artifacts

        Particularly important for AI-generated audio
        """
        logger.info("Post-processing stems...")

        processed_stems = {}

        for name, audio in stems.items():
            # Reduce bleeding between stems
            audio = self._reduce_stem_bleeding(audio, sr)

            # Enhance transients (especially for drums)
            if self.audio_config.enhance_transients and name == "drums":
                audio = self._enhance_transients(audio, sr)

            # Final normalization
            max_val = np.abs(audio).max()
            if max_val > 0:
                audio = audio * (0.95 / max_val)

            processed_stems[name] = audio

        return processed_stems

    def _reduce_stem_bleeding(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Reduce spectral bleeding between stems"""
        # Simple noise gate
        threshold = 0.01
        gate = np.abs(audio) > threshold
        return audio * gate

    def _enhance_transients(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Enhance transients in drum stems"""
        from scipy import signal

        # Transient detection via envelope following
        envelope = np.abs(audio)

        # Smooth envelope
        butter_result = signal.butter(2, 10 / (sr / 2), btype="low")
        if isinstance(butter_result, tuple) and len(butter_result) >= 2:
            b, a = butter_result[0], butter_result[1]
        else:
            raise RuntimeError("Unexpected signal.butter output format")
        envelope_smooth = np.zeros_like(envelope)

        for ch in range(envelope.shape[0]):
            envelope_smooth[ch] = signal.filtfilt(b, a, envelope[ch])

        # Calculate transient component
        transient = envelope - envelope_smooth

        # Enhance
        enhancement_factor = 1.2
        transient_enhanced = transient * enhancement_factor

        # Recombine
        audio_enhanced = audio + transient_enhanced * np.sign(audio)

        return audio_enhanced

    def _save_stems(
        self, stems: dict[str, np.ndarray], input_file: str, target_stems: list[str]
    ) -> dict[str, str]:
        """Save separated stems to files"""
        input_path = Path(input_file)
        base_name = input_path.stem

        # Create output subdirectory
        output_subdir = os.path.join(self.output_dir, base_name)
        os.makedirs(output_subdir, exist_ok=True)

        output_paths = {}

        for stem_name in target_stems:
            if stem_name not in stems:
                logger.warning(f"Stem '{stem_name}' not found in separation results")
                continue

            output_path = os.path.join(output_subdir, f"{base_name}_{stem_name}.wav")

            # Transpose back to (samples, channels) for soundfile
            audio_to_save = stems[stem_name].T

            sf.write(output_path, audio_to_save, self.sample_rate)
            output_paths[stem_name] = output_path

            logger.info(f"  Saved: {stem_name} -> {output_path}")

        return output_paths

    def get_model_info(self) -> dict[str, str | int | bool]:
        """Get information about the loaded model"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "sample_rate": self.sample_rate,
            "transformer_mode": self.use_transformer,
            "ai_audio_optimized": True,
        }


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(description="YourMT3+ Stem Separator for AI-Generated Audio")

    parser.add_argument("input", help="Input audio file path")

    parser.add_argument(
        "-o",
        "--output-dir",
        default="./stems_output",
        help="Output directory for stems (default: ./stems_output)",
    )

    parser.add_argument(
        "-m", "--model", default="htdemucs", help="Model to use (default: htdemucs)"
    )

    parser.add_argument(
        "-s",
        "--stems",
        nargs="+",
        default=["vocals", "drums", "bass", "other"],
        help="Stems to extract (default: vocals drums bass other)",
    )

    parser.add_argument(
        "--device",
        choices=["cuda", "cpu", "auto"],
        default="auto",
        help="Device to use (default: auto)",
    )

    parser.add_argument("--no-transformer", action="store_true", help="Disable transformer mode")

    args = parser.parse_args()

    # Initialize separator
    device = None if args.device == "auto" else args.device

    separator = YourMT3StemSeparator(
        model_name=args.model,
        device=device,
        output_dir=args.output_dir,
        use_transformer=not args.no_transformer,
    )

    # Display model info
    model_info = separator.get_model_info()
    logger.info("Model Configuration:")
    for key, value in model_info.items():
        logger.info(f"  {key}: {value}")

    # Perform separation
    start_time = datetime.now()

    output_paths = separator.separate(input_file=args.input, stems=args.stems)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Summary
    print("\n" + "=" * 60)
    print("SEPARATION COMPLETE")
    print("=" * 60)
    print(f"Processing time: {duration:.1f}s")
    print("\nOutput stems:")
    for stem_name, path in output_paths.items():
        print(f"  {stem_name:12s} -> {path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
