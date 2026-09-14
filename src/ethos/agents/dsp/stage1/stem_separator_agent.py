"""
SEMAS Stem Separator Agent
Separates audio into stems using Demucs (vocals, drums, bass, other)
"""

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from ethos.core.data_structures import AudioStem, DrumKitStems, StemCollection, VocalStems
from ethos.core.message_bus import MessagePriority, get_message_bus

logger = logging.getLogger(__name__)


class StemSeparatorAgent:
    """
    Stage 1 Agent: Stem separation using Demucs
    Input: Audio file path
    Output: StemCollection with 4 primary stems
    """

    def __init__(self, model_name: str = "htdemucs", output_dir: str | None = None):
        self.name = "StemSeparatorAgent"
        self.model_name = model_name
        self.output_dir = output_dir or os.path.abspath(os.path.join("output", "stems"))
        self.message_bus = get_message_bus()

        # Subscribe to events
        self.message_bus.subscribe("analysis.complete", self._on_analysis_complete)

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        # Check Demucs availability
        self._check_demucs()

    def _check_demucs(self):
        """Check if Demucs is installed"""
        try:
            result = subprocess.run(
                ["python", "-m", "demucs", "--help"], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                logger.info("Demucs found and ready")
                self.demucs_available = True
            else:
                logger.warning("Demucs not found. Install with: pip install demucs")
                self.demucs_available = False
        except Exception as e:
            logger.warning(f"Demucs check failed: {e}")
            self.demucs_available = False

    async def _on_analysis_complete(self, message):
        """Handle analysis completion - start stem separation"""
        report = message.payload.get("report")
        file_id = message.payload.get("file_id")

        if not report:
            return

        logger.info(f"Starting stem separation for: {report.file_path}")

        # Separate stems
        stem_collection = await self.separate_stems(report.file_path, file_id)

        if stem_collection:
            # Publish results
            await self.message_bus.publish(
                topic="stems.separated",
                payload={"stems": stem_collection, "file_id": file_id},
                sender=self.name,
                priority=MessagePriority.HIGH,
            )

    async def separate_stems(self, input_file: str, file_id: str) -> StemCollection | None:
        """Separate audio into stems using Demucs"""

        if not self.demucs_available:
            logger.error("Demucs not available - cannot separate stems")
            return None

        if not os.path.exists(input_file):
            logger.error(f"Input file not found: {input_file}")
            return None

        logger.info(f"Separating stems with {self.model_name}...")

        start_time = datetime.now()

        # Create output directory for this file
        file_output_dir = os.path.join(self.output_dir, file_id)
        os.makedirs(file_output_dir, exist_ok=True)

        # Run Demucs
        try:
            command = [
                "python",
                "-m",
                "demucs",
                "--two-stems=vocals",  # Faster for 4-stem separation
                "-n",
                self.model_name,
                "-o",
                file_output_dir,
                input_file,
            ]

            logger.info(f"Running: {' '.join(command)}")

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"Demucs failed: {result.stderr}")
                return None

            logger.info("Demucs separation complete")

        except subprocess.TimeoutExpired:
            logger.error("Demucs timeout (>10 minutes)")
            return None
        except Exception as e:
            logger.error(f"Demucs error: {e}")
            return None

        # Locate separated stems
        # Demucs creates: output_dir/model_name/filename/vocals.wav, drums.wav, etc.
        input_basename = Path(input_file).stem
        stems_dir = os.path.join(file_output_dir, self.model_name, input_basename)

        if not os.path.exists(stems_dir):
            logger.error(f"Stems directory not found: {stems_dir}")
            return None

        # Build AudioStem objects
        stem_files = {
            "vocals": os.path.join(stems_dir, "vocals.wav"),
            "drums": os.path.join(stems_dir, "drums.wav"),
            "bass": os.path.join(stems_dir, "bass.wav"),
            "other": os.path.join(stems_dir, "other.wav"),
        }

        # Verify all stems exist
        for _stem_name, stem_path in stem_files.items():
            if not os.path.exists(stem_path):
                logger.error(f"Missing stem: {stem_path}")
                return None

        # Get stem info
        import soundfile as sf

        stems = {}
        for stem_name, stem_path in stem_files.items():
            info = sf.info(stem_path)

            stems[stem_name] = AudioStem(
                name=stem_name,
                file_path=stem_path,
                stem_type=stem_name,
                duration=info.duration,
                sample_rate=info.samplerate,
                separation_quality=0.85,  # Demucs typical quality
                spectral_leakage=0.1,
                transient_preservation=0.9,
                processing_chain=[f"demucs_{self.model_name}"],
                enhancement_applied=False,
            )

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        # Create StemCollection
        stem_collection = StemCollection(
            vocals=stems["vocals"],
            drums=stems["drums"],
            bass=stems["bass"],
            other=stems["other"],
            drum_kit=None,  # Will be populated by sub-separator if needed
            vocal_layers=None,
            separation_model=f"demucs-{self.model_name}",
            separation_timestamp=datetime.now(),
            total_separation_time=processing_time,
        )

        logger.info(f"Stem separation complete in {processing_time:.1f}s")

        return stem_collection

    async def separate_drum_kit(self, drum_stem_path: str) -> DrumKitStems | None:
        """
        Separate drum stem into individual components
        Note: This is a placeholder - would use specialized drum separation model
        """

        logger.info("Drum kit separation not yet implemented")
        logger.info("Would separate into: kick, snare, hihat, toms, cymbals, room")

        # In production, would use:
        # - Specialized drum separation model (e.g., DrumSep)
        # - Or transient detection + frequency analysis (like Lua version)

        return None

    async def separate_vocal_layers(self, vocal_stem_path: str) -> VocalStems | None:
        """
        Separate vocals into lead/backing/harmony
        Note: This is a placeholder - would use specialized vocal separation model
        """

        logger.info("Vocal layer separation not yet implemented")
        logger.info("Would separate into: lead, backing, harmony")

        return None

    def get_model_info(self) -> dict[str, str]:
        """Get information about the separation model"""
        return {
            "model_name": self.model_name,
            "type": "demucs",
            "stems": "4 (vocals, drums, bass, other)",
            "quality": "high",
            "speed": "medium",
        }
