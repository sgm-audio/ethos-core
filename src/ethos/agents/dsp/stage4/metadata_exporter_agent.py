"""SEMAS Metadata Exporter Agent - Export metadata to JSON/XML"""

import json
import logging

from ethos.core.data_structures import AudioAnalysisReport, SEMASJob
from ethos.core.message_bus import get_message_bus

logger = logging.getLogger(__name__)


class MetadataExporterAgent:
    """Stage 4 Agent: Metadata export"""

    def __init__(self):
        self.name = "MetadataExporterAgent"
        self.message_bus = get_message_bus()

    async def export_to_json(self, job: SEMASJob, output_path: str):
        """Export complete SEMAS job data to JSON"""

        job_data = {
            "job_id": job.job_id,
            "input_file": job.input_file,
            "enhancement_profile": job.enhancement_profile,
            "target_format": job.target_format,
            "status": job.status,
            "total_processing_time": job.total_processing_time,
            "analysis": {
                "bpm": job.analysis_report.bpm if job.analysis_report else None,
                "key": job.analysis_report.key if job.analysis_report else None,
                "genre": job.analysis_report.genre if job.analysis_report else None,
            }
            if job.analysis_report
            else {},
            "stems": {
                "vocals": job.stem_collection.vocals.file_path if job.stem_collection else None,
                "drums": job.stem_collection.drums.file_path if job.stem_collection else None,
                "bass": job.stem_collection.bass.file_path if job.stem_collection else None,
                "other": job.stem_collection.other.file_path if job.stem_collection else None,
            }
            if job.stem_collection
            else {},
        }

        with open(output_path, "w") as f:
            json.dump(job_data, f, indent=2)

        logger.info(f"Metadata exported to: {output_path}")

    async def export_to_xml(self, analysis: AudioAnalysisReport, output_path: str):
        """Export analysis to XML"""
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<semas_analysis>
  <file_id>{analysis.file_id}</file_id>
  <bpm>{analysis.bpm}</bpm>
  <key>{analysis.key}</key>
  <genre>{analysis.genre}</genre>
  <duration>{analysis.duration}</duration>
  <sections>
"""
        for section in analysis.sections:
            xml += f"""    <section name="{section.name}" start="{section.start_time}" end="{section.end_time}"/>\n"""

        xml += """  </sections>
</semas_analysis>
"""
        with open(output_path, "w") as f:
            f.write(xml)

        logger.info(f"XML exported to: {output_path}")
