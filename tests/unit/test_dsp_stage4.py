"""
Unit tests for Stage 4 DSP Export Agents:
- DAWGeneratorAgent (REAPER RPP project generation)
- MarkerCreatorAgent
- FormatConverterAgent
- MetadataExporterAgent
- TempoMapAgent
- MIDIGeneratorAgent
"""

import json
import os

import pytest

from ethos.agents.dsp.stage1.audio_analysis_agent import AudioAnalysisAgent
from ethos.agents.dsp.stage4.daw_generator_agent import DAWGeneratorAgent
from ethos.agents.dsp.stage4.format_converter_agent import FormatConverterAgent
from ethos.agents.dsp.stage4.marker_creator_agent import MarkerCreatorAgent
from ethos.agents.dsp.stage4.metadata_exporter_agent import MetadataExporterAgent
from ethos.agents.dsp.stage4.midi_generator_agent import MIDIGeneratorAgent
from ethos.agents.dsp.stage4.tempo_map_agent import TempoMapAgent
from ethos.core.data_structures import SEMASJob, StemCollection


@pytest.mark.asyncio
async def test_daw_generator_agent_reaper(
    tmp_path, mock_stem_collection: StemCollection, synthetic_stereo_wav: str
):
    """Test generating REAPER project file with stems, tempo, and routing."""
    analysis_agent = AudioAnalysisAgent()
    report = await analysis_agent.analyze_audio(synthetic_stereo_wav, "daw_test")

    agent = DAWGeneratorAgent()
    stems = {
        "vocals": mock_stem_collection.vocals,
        "drums": mock_stem_collection.drums,
        "bass": mock_stem_collection.bass,
        "other": mock_stem_collection.other,
    }

    rpp_path = str(tmp_path / "test_project.RPP")
    daw_project = await agent.generate_reaper_project(stems, report, rpp_path)

    assert os.path.exists(rpp_path)
    assert daw_project.daw_type == "reaper"
    assert daw_project.tempo == report.bpm

    with open(rpp_path) as f:
        content = f.read()

    assert "<REAPER_PROJECT" in content
    assert "TEMPO" in content
    assert 'NAME "Vocals"' in content
    assert 'NAME "Drums"' in content
    assert "<MASTER_TRACK" in content


@pytest.mark.asyncio
async def test_marker_and_tempo_agents(synthetic_stereo_wav: str):
    """Test section marker creation and tempo map generation."""
    analysis_agent = AudioAnalysisAgent()
    report = await analysis_agent.analyze_audio(synthetic_stereo_wav, "marker_test")

    marker_agent = MarkerCreatorAgent()
    markers = await marker_agent.create_markers(report)
    assert len(markers) == len(report.sections) * 2

    tempo_agent = TempoMapAgent()
    tempo_map = await tempo_agent.create_tempo_map(report)
    assert tempo_map is not None
    assert len(tempo_map) >= 1
    assert tempo_map[0][1] == report.bpm


@pytest.mark.asyncio
async def test_metadata_exporter_and_format_converter(tmp_path, synthetic_stereo_wav: str):
    """Test exporting metadata JSON/XML and format conversion."""
    analysis_agent = AudioAnalysisAgent()
    report = await analysis_agent.analyze_audio(synthetic_stereo_wav, "meta_exp_test")

    job = SEMASJob(
        job_id="meta_exp_test",
        input_file=synthetic_stereo_wav,
        output_directory=str(tmp_path),
        enhancement_profile="balanced",
        target_format="wav",
        analysis_report=report,
    )

    meta_agent = MetadataExporterAgent()
    json_path = str(tmp_path / "metadata.json")
    await meta_agent.export_to_json(job, json_path)
    assert os.path.exists(json_path)

    with open(json_path) as f:
        data = json.load(f)
    assert data["job_id"] == "meta_exp_test"

    converter = FormatConverterAgent()
    flac_out = str(tmp_path / "converted.flac")
    await converter.convert_to_format(synthetic_stereo_wav, "flac", flac_out)
    assert os.path.exists(flac_out)


@pytest.mark.asyncio
async def test_midi_generator_agent(tmp_path):
    """Test click track MIDI generator."""
    agent = MIDIGeneratorAgent()
    midi_path = str(tmp_path / "click.mid")
    await agent.create_click_track_midi(bpm=120.0, duration=2.0, output_path=midi_path)
    assert os.path.exists(midi_path)
