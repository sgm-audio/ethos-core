"""SEMAS Format Converter Agent - Convert to various formats"""

import logging
import os
import subprocess

import soundfile as sf

from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class FormatConverterAgent:
    """Stage 4 Agent: Multi-format export (WAV, MP3, FLAC, OGG)"""

    def __init__(self):
        self.name = "FormatConverterAgent"
        self.message_bus = get_message_bus()

    async def convert_to_format(
        self, input_path: str, output_format: str, output_path: str, quality: str = "high"
    ):
        """Convert audio to specified format"""

        if output_format.lower() == "wav":
            audio, sr = sf.read(input_path)
            sf.write(output_path, audio, sr, subtype="PCM_24")
            logger.info(f"Converted to WAV: {output_path}")

        elif output_format.lower() == "flac":
            audio, sr = sf.read(input_path)
            sf.write(output_path, audio, sr, format="FLAC", subtype="PCM_24")
            logger.info(f"Converted to FLAC: {output_path}")

        elif output_format.lower() == "mp3":
            # Requires ffmpeg
            bitrate = "320k" if quality == "high" else "192k"
            cmd = ["ffmpeg", "-i", input_path, "-b:a", bitrate, output_path, "-y"]
            try:
                subprocess.run(cmd, check=True, capture_output=True)  # nosec B603
                logger.info(f"Converted to MP3: {output_path}")
            except Exception:
                logger.error("MP3 conversion failed (ffmpeg required)")

        elif output_format.lower() == "ogg":
            cmd = ["ffmpeg", "-i", input_path, "-c:a", "libvorbis", "-q:a", "8", output_path, "-y"]
            try:
                subprocess.run(cmd, check=True, capture_output=True)  # nosec B603
                logger.info(f"Converted to OGG: {output_path}")
            except Exception:
                logger.error("OGG conversion failed (ffmpeg required)")

    async def export_all_formats(self, input_path: str, output_dir: str):
        """Export to all common formats"""
        base_name = os.path.splitext(os.path.basename(input_path))[0]

        formats = ["wav", "mp3", "flac"]
        for fmt in formats:
            output_path = os.path.join(output_dir, f"{base_name}.{fmt}")
            await self.convert_to_format(input_path, fmt, output_path)
