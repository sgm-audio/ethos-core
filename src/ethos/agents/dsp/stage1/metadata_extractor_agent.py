"""
SEMAS Metadata Extractor Agent
Extracts and enriches metadata from audio and analysis reports
"""

import logging

from ethos.core.data_structures import AudioAnalysisReport, Section
from ethos.core.message_bus import MessagePriority, get_message_bus

logger = logging.getLogger(__name__)


class MetadataExtractorAgent:
    """
    Stage 1 Agent: Metadata extraction and enrichment
    Creates markers, extracts tags, generates descriptions
    """

    def __init__(self):
        self.name = "MetadataExtractorAgent"
        self.message_bus = get_message_bus()

        # Subscribe to analysis completion
        self.message_bus.subscribe("analysis.complete", self._on_analysis_complete)

    async def _on_analysis_complete(self, message):
        """Handle analysis completion - extract metadata"""
        report = message.payload.get("report")
        file_id = message.payload.get("file_id")

        if not report:
            return

        logger.info(f"Extracting metadata for: {report.file_path}")

        # Extract metadata
        metadata = self.extract_metadata(report)

        # Publish results
        await self.message_bus.publish(
            topic="metadata.extracted",
            payload={"metadata": metadata, "file_id": file_id, "report": report},
            sender=self.name,
            priority=MessagePriority.NORMAL,
        )

    def extract_metadata(self, report: AudioAnalysisReport) -> dict:
        """Extract comprehensive metadata from analysis report"""

        metadata = {
            "file_id": report.file_id,
            "file_path": report.file_path,
            "duration": report.duration,
            "duration_formatted": self._format_duration(report.duration),
            # Musical
            "bpm": report.bpm,
            "key": report.key,
            "time_signature": report.time_signature,
            # Genre/Mood
            "genre": report.genre,
            "subgenre": report.subgenre,
            "mood": report.mood,
            "energy_level": report.energy_level,
            # Technical
            "sample_rate": report.sample_rate,
            "bit_depth": report.bit_depth,
            "channels": report.channels,
            "format": self._get_audio_format(report.file_path),
            # Quality
            "overall_quality": report.overall_quality_score,
            "quality_grade": self._get_quality_grade(report.overall_quality_score),
            "issues_count": len(report.detected_issues),
            # Dynamics
            "loudness_lufs": report.dynamic_range.lufs_integrated,
            "dynamic_range_db": report.dynamic_range.dynamic_range,
            "peak_db": report.dynamic_range.peak_db,
            # Frequency
            "spectral_centroid": report.frequency_analysis.spectral_centroid,
            "bass_heavy": report.frequency_analysis.bass > report.frequency_analysis.mids,
            "bright": report.frequency_analysis.brilliance > report.frequency_analysis.mids,
            # Structure
            "sections": [self._section_to_dict(s) for s in report.sections],
            "markers": self._generate_markers(report.sections, report.bpm),
            # Timestamps
            "analysis_timestamp": report.analysis_timestamp.isoformat(),
            # Tags
            "tags": self._generate_tags(report),
        }

        logger.info(
            f"Metadata extracted: {metadata['genre']}, {metadata['bpm']} BPM, {len(metadata['sections'])} sections"
        )

        return metadata

    def _format_duration(self, duration_seconds: float) -> str:
        """Format duration as MM:SS"""
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _get_audio_format(self, file_path: str) -> str:
        """Get audio format from file extension"""
        return file_path.split(".")[-1].upper()

    def _get_quality_grade(self, score: float) -> str:
        """Convert quality score to letter grade"""
        if score >= 0.9:
            return "A"
        elif score >= 0.8:
            return "B"
        elif score >= 0.7:
            return "C"
        elif score >= 0.6:
            return "D"
        else:
            return "F"

    def _section_to_dict(self, section: Section) -> dict:
        """Convert Section object to dictionary"""
        return {
            "name": section.name,
            "start_time": section.start_time,
            "end_time": section.end_time,
            "start_bar": section.start_bar,
            "end_bar": section.end_bar,
            "duration": section.end_time - section.start_time,
            "confidence": section.confidence,
        }

    def _generate_markers(self, sections: list[Section], bpm: float) -> list[dict]:
        """Generate DAW markers from sections"""

        markers = []

        for i, section in enumerate(sections):
            # Region marker for section
            markers.append(
                {
                    "type": "region",
                    "name": section.name,
                    "time": section.start_time,
                    "end_time": section.end_time,
                    "color": self._get_section_color(section.name),
                    "id": i,
                }
            )

            # Point marker at section start
            markers.append(
                {
                    "type": "marker",
                    "name": f"{section.name} Start",
                    "time": section.start_time,
                    "color": self._get_section_color(section.name),
                    "id": i * 1000,
                }
            )

        # Add end marker
        if sections:
            markers.append(
                {
                    "type": "marker",
                    "name": "End",
                    "time": sections[-1].end_time,
                    "color": "gray",
                    "id": 9999,
                }
            )

        return markers

    def _get_section_color(self, section_name: str) -> str:
        """Get color for section type"""

        section_lower = section_name.lower()

        if "intro" in section_lower:
            return "green"
        elif "verse" in section_lower:
            return "blue"
        elif "chorus" in section_lower:
            return "red"
        elif "bridge" in section_lower:
            return "purple"
        elif "outro" in section_lower:
            return "orange"
        else:
            return "gray"

    def _generate_tags(self, report: AudioAnalysisReport) -> list[str]:
        """Generate descriptive tags from analysis"""

        tags = []

        # Genre tags
        tags.append(report.genre)
        if report.subgenre:
            tags.append(report.subgenre)

        # Mood tags
        tags.extend(report.mood)

        # Tempo tags
        if report.bpm < 80:
            tags.append("Slow")
        elif report.bpm < 100:
            tags.append("Moderate")
        elif report.bpm < 130:
            tags.append("Upbeat")
        else:
            tags.append("Fast")

        # Energy tags
        if report.energy_level > 0.7:
            tags.append("High Energy")
        elif report.energy_level < 0.3:
            tags.append("Low Energy")

        # Dynamic tags
        if report.dynamic_range.dynamic_range > 10:
            tags.append("Dynamic")
        elif report.dynamic_range.dynamic_range < 5:
            tags.append("Compressed")

        # Frequency tags
        if report.frequency_analysis.bass > report.frequency_analysis.mids + 3:
            tags.append("Bass Heavy")
        if report.frequency_analysis.brilliance > report.frequency_analysis.mids + 3:
            tags.append("Bright")

        # Key tag
        tags.append(report.key)

        # Quality tags
        if report.overall_quality_score > 0.8:
            tags.append("High Quality")
        if len(report.detected_issues) > 0:
            tags.append("Has Issues")

        return tags

    def create_project_description(self, report: AudioAnalysisReport, metadata: dict) -> str:
        """Create human-readable project description"""

        desc = f"""SEMAS Project: {report.file_id}

Musical Information:
- Tempo: {report.bpm:.1f} BPM
- Key: {report.key}
- Time Signature: {report.time_signature}
- Duration: {metadata["duration_formatted"]}

Genre & Mood:
- Genre: {report.genre} / {report.subgenre}
- Mood: {", ".join(report.mood)}
- Energy Level: {report.energy_level:.0%}

Technical Specs:
- Sample Rate: {report.sample_rate} Hz
- Bit Depth: {report.bit_depth} bit
- Channels: {report.channels}
- Format: {metadata["format"]}

Dynamics:
- LUFS: {report.dynamic_range.lufs_integrated:.1f}
- Peak: {report.dynamic_range.peak_db:.1f} dB
- Dynamic Range: {report.dynamic_range.dynamic_range:.1f} dB

Structure:
"""

        for section in report.sections:
            desc += f"- {section.name}: {section.start_time:.1f}s - {section.end_time:.1f}s\n"

        if report.detected_issues:
            desc += f"\nQuality Issues ({len(report.detected_issues)}):\n"
            for issue in report.detected_issues:
                desc += f"- {issue.issue_type}: {issue.description}\n"

        desc += f"\nQuality Score: {metadata['quality_grade']} ({report.overall_quality_score:.0%})"

        return desc

    def export_metadata_to_json(self, metadata: dict, output_path: str):
        """Export metadata to JSON file"""

        import json

        try:
            with open(output_path, "w") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Metadata exported to: {output_path}")
        except Exception as e:
            logger.error(f"Failed to export metadata: {e}")
