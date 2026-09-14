"""SEMAS Tempo Map Agent - Generate tempo maps"""

import logging

from ethos.core.data_structures import AudioAnalysisReport
from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class TempoMapAgent:
    """Stage 4 Agent: Tempo map generation"""

    def __init__(self):
        self.name = "TempoMapAgent"
        self.message_bus = get_message_bus()

    async def create_tempo_map(self, analysis: AudioAnalysisReport) -> list[tuple[float, float]]:
        """Create tempo map (time, BPM pairs)"""

        # For Suno tracks, tempo is usually constant
        # But we create a map for compatibility

        tempo_map = [(0.0, analysis.bpm)]

        # Add tempo points at section boundaries if needed
        for section in analysis.sections:
            tempo_map.append((section.start_time, analysis.bpm))

        logger.info(f"Created tempo map with {len(tempo_map)} points")
        return tempo_map

    async def export_tempo_map_to_txt(self, tempo_map: list[tuple[float, float]], output_path: str):
        """Export tempo map to text file"""
        with open(output_path, "w") as f:
            f.write("# SEMAS Tempo Map\n")
            f.write("# Format: Time(seconds) BPM\n")
            for time, bpm in tempo_map:
                f.write(f"{time:.3f} {bpm:.2f}\n")

        logger.info(f"Tempo map exported to: {output_path}")
