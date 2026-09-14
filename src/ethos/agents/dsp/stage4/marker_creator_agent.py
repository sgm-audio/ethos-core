"""SEMAS Marker Creator Agent - Create markers and regions"""

import logging

from ethos.core.data_structures import AudioAnalysisReport
from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class MarkerCreatorAgent:
    """Stage 4 Agent: Marker and region creation"""

    def __init__(self):
        self.name = "MarkerCreatorAgent"
        self.message_bus = get_message_bus()

    async def create_markers(self, analysis: AudioAnalysisReport) -> list[dict]:
        """Create markers from sections"""
        markers = []

        for i, section in enumerate(analysis.sections):
            # Region marker
            markers.append(
                {
                    "id": i,
                    "type": "region",
                    "name": section.name,
                    "start": section.start_time,
                    "end": section.end_time,
                    "color": self._get_color(section.name),
                }
            )

            # Point marker at start
            markers.append(
                {
                    "id": i + 1000,
                    "type": "marker",
                    "name": f"{section.name} Start",
                    "position": section.start_time,
                    "color": self._get_color(section.name),
                }
            )

        logger.info(f"Created {len(markers)} markers")
        return markers

    def _get_color(self, section_name: str) -> str:
        """Get color based on section type"""
        name_lower = section_name.lower()
        if "intro" in name_lower:
            return "green"
        elif "verse" in name_lower:
            return "blue"
        elif "chorus" in name_lower:
            return "red"
        elif "bridge" in name_lower:
            return "purple"
        elif "outro" in name_lower:
            return "orange"
        return "gray"

    async def export_markers_to_cue(self, markers: list[dict], output_path: str):
        """Export markers to CUE sheet format"""
        with open(output_path, "w") as f:
            f.write("REM SEMAS Generated Cue Sheet\n")
            for marker in markers:
                if marker["type"] == "marker":
                    mins = int(marker["position"] // 60)
                    secs = int(marker["position"] % 60)
                    frames = int((marker["position"] % 1) * 75)
                    f.write(f"  INDEX {marker['id']:02d} {mins:02d}:{secs:02d}:{frames:02d}\n")
        logger.info(f"Exported markers to: {output_path}")
