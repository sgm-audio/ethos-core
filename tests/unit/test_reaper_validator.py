"""
Gate 4 Validator: REAPER .RPP Project & DSP Chunk Schema Validator.
Validates syntax, chunk nesting, GUID formats, and visual asset exports.
"""

import os
import re

import pytest

from ethos.agents.dsp.stage1.audio_analysis_agent import AudioAnalysisAgent
from ethos.agents.dsp.stage4.daw_generator_agent import DAWGeneratorAgent
from ethos.core.data_structures import StemCollection


@pytest.mark.asyncio
async def test_reaper_rpp_syntax_and_structure(
    tmp_path, mock_stem_collection: StemCollection, synthetic_stereo_wav: str
):
    """
    Validate Cockos REAPER project chunk hierarchy, token nesting,
    and associated visual SVG curve artifacts.
    """
    analysis_agent = AudioAnalysisAgent()
    report = await analysis_agent.analyze_audio(synthetic_stereo_wav, "reaper_val_test")

    agent = DAWGeneratorAgent()
    stems = {
        "vocals": mock_stem_collection.vocals,
        "drums": mock_stem_collection.drums,
        "bass": mock_stem_collection.bass,
        "other": mock_stem_collection.other,
    }

    rpp_path = str(tmp_path / "validated_session.RPP")
    await agent.generate_reaper_project(stems, report, rpp_path)

    assert os.path.exists(rpp_path)
    with open(rpp_path, encoding="utf-8") as f:
        content = f.read()

    # 1. Root Project Tag Validation
    assert content.startswith("<REAPER_PROJECT")
    assert content.strip().endswith(">")

    # 2. Chunk Tag Balance
    # In REAPER RPP: '<TAG ...\n' opens a chunk, and a standalone '>' closes it.
    # Single-line tags like '<MARKER ... >' have both on the same line.
    lines = content.splitlines()
    open_chunks = 0
    close_chunks = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("<") and not stripped.endswith(">"):
            open_chunks += 1  # Multi-line chunk open
        elif stripped.startswith("<") and stripped.endswith(">"):
            pass  # Single-line tag, balanced on same line
        elif stripped == ">":
            close_chunks += 1  # Multi-line chunk close
    assert open_chunks == close_chunks, (
        f"Mismatched chunks: {open_chunks} opens vs {close_chunks} closes"
    )

    # 3. Master Track Validation
    assert "<MASTER_TRACK" in content

    # 4. Track Count & Names
    for stem_name in ["Vocals", "Drums", "Bass", "Other"]:
        assert f'NAME "{stem_name}"' in content

    # 5. GUID Format Validation {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}
    guid_pattern = (
        r"\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}"
    )
    guids = re.findall(guid_pattern, content)
    assert len(guids) >= 4, "Tracks must have valid unique GUID identifiers"

    # 6. Tempo consistency
    tempo_match = re.search(r"TEMPO\s+([\d.]+)", content)
    assert tempo_match is not None
    assert float(tempo_match.group(1)) == report.bpm

    # 7. User-Facing Visual Curve Artifacts
    eq_svg_path = rpp_path.replace(".RPP", "_eq_curve.svg")
    dyn_svg_path = rpp_path.replace(".RPP", "_dynamics_curve.svg")
    assert os.path.exists(eq_svg_path)
    assert os.path.exists(dyn_svg_path)

    with open(eq_svg_path, encoding="utf-8") as f:
        eq_svg = f.read()
    assert "<svg" in eq_svg and "</svg>" in eq_svg
    assert "ETHOS Dynamic EQ Curve" in eq_svg

    with open(dyn_svg_path, encoding="utf-8") as f:
        dyn_svg = f.read()
    assert "<svg" in dyn_svg and "</svg>" in dyn_svg
    assert "Ratio:" in dyn_svg
