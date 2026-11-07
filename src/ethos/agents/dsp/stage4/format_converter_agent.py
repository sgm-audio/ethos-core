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
        """Convert audio to a supported format or raise an actionable error."""
        output_format = output_format.lower()
        supported = {"wav", "flac", "mp3", "ogg"}
        if output_format not in supported:
            raise ValueError(
                f"Unsupported output format {output_format!r}; choose from {sorted(supported)}"
            )
        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"Audio input does not exist: {input_path}")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        if output_format in {"wav", "flac"}:
            audio, sr = sf.read(input_path)
            sf.write(
                output_path,
                audio,
                sr,
                format="WAV" if output_format == "wav" else "FLAC",
                subtype="PCM_24",
            )
        else:
            if output_format == "mp3":
                bitrate = "320k" if quality == "high" else "192k"
                cmd = ["ffmpeg", "-i", input_path, "-b:a", bitrate, output_path, "-y"]
            else:
                cmd = [
                    "ffmpeg",
                    "-i",
                    input_path,
                    "-c:a",
                    "libvorbis",
                    "-q:a",
                    "8",
                    output_path,
                    "-y",
                ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)  # nosec B603
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"Converting to {output_format} requires ffmpeg on PATH"
                ) from exc
            except subprocess.CalledProcessError as exc:
                detail = exc.stderr.decode(errors="replace") if exc.stderr else str(exc)
                raise RuntimeError(f"ffmpeg failed to convert audio: {detail[-1000:]}") from exc

        if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError(f"Audio conversion produced no output file: {output_path}")
        logger.info("Converted to %s: %s", output_format.upper(), output_path)
        return output_path

    async def export_all_formats(self, input_path: str, output_dir: str):
        """Export to all common formats"""
        base_name = os.path.splitext(os.path.basename(input_path))[0]

        formats = ["wav", "mp3", "flac"]
        for fmt in formats:
            output_path = os.path.join(output_dir, f"{base_name}.{fmt}")
            await self.convert_to_format(input_path, fmt, output_path)
