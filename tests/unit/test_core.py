"""
Unit tests for ethos.core subsystem:
- Configuration validation
- Ontology & goal satisfaction calculations
- Dataclasses & schemas
- Message bus asynchronous event routing
"""

import asyncio

import pytest

from ethos.core.audio_ontology import AudioAttribute as AliasedAttribute
from ethos.core.config import (
    EnhancementProfile,
    TargetFormat,
    WorkflowConfig,
)
from ethos.core.data_structures import (
    AudioAnalysisReport,
    ProcessingStage,
    Section,
    SEMASJob,
)
from ethos.core.message_bus import MessageBus, MessagePriority
from ethos.core.ontology import (
    AgentAction,
    AudioAttribute,
    AudioOntologyManager,
    AudioState,
    create_clarity_goal,
    create_warmth_goal,
)


def test_config_defaults_and_validation():
    """Verify default configurations and type coercions."""
    config = WorkflowConfig()
    assert config.audio.sample_rate == 44100
    assert config.audio.channels == 2
    assert config.enhancement_profile == EnhancementProfile.BALANCED
    assert config.target_format == TargetFormat.STREAMING
    assert ".wav" in config.paths.audio_extensions


def test_audio_ontology_and_goals():
    """Test ontology manager reasoning, correlation, and goal satisfaction scoring."""
    ontology = AudioOntologyManager()

    state = AudioState()
    state.set_attribute(AudioAttribute.CLARITY, 0.8, confidence=0.95)
    state.set_attribute(AudioAttribute.WARMTH, 0.7, confidence=0.90)
    state.set_attribute(AudioAttribute.MUD, 0.2, confidence=0.85)

    goals = [
        create_clarity_goal(target=0.8, priority=1.0),
        create_warmth_goal(target=0.7, priority=0.8),
    ]

    satisfaction = ontology.estimate_satisfaction_score(state, goals)
    assert satisfaction >= 0.95

    # Check attribute correlation
    mud_clarity_corr = ontology.get_attribute_correlation(
        AudioAttribute.CLARITY, AudioAttribute.MUD
    )
    assert mud_clarity_corr < 0.0

    # Test action impact prediction
    action = AgentAction(
        agent_id="EQAgent",
        action_type="eq_boost",
        parameters={"freq": 3000, "gain": 2.0},
        expected_impact={AudioAttribute.CLARITY: 0.1},
    )
    new_state = ontology.predict_action_impact(action, state)
    assert new_state.get_attribute(AudioAttribute.CLARITY) > state.get_attribute(
        AudioAttribute.CLARITY
    )


def test_audio_ontology_alias_compatibility():
    """Verify audio_ontology compatibility module correctly aliases ontology symbols."""
    assert AliasedAttribute.CLARITY == AudioAttribute.CLARITY
    assert AliasedAttribute.PUNCH == AudioAttribute.PUNCH


def test_data_structures_instantiation():
    """Verify audio data structures and job model integrity."""
    section = Section(name="Verse", start_time=0.0, end_time=15.5)
    assert section.name == "Verse"

    report = AudioAnalysisReport(
        file_id="track_123",
        file_path="/tmp/audio.wav",
        duration=180.0,
        sample_rate=44100,
        bit_depth=24,
        channels=2,
        bpm=120.0,
        bpm_confidence=0.92,
        key="C Minor",
        key_confidence=0.88,
        time_signature="4/4",
        sections=[section],
    )
    assert report.bpm == 120.0
    assert len(report.sections) == 1

    job = SEMASJob(
        job_id="job_001",
        input_file="/tmp/in.wav",
        output_directory="/tmp/out",
        current_stage=ProcessingStage.ANALYSIS,
    )
    assert job.status == "queued"
    assert job.current_stage == ProcessingStage.ANALYSIS


@pytest.mark.asyncio
async def test_message_bus_exact_and_wildcard_pub_sub():
    """Verify MessageBus async publishing, exact topic matching, and wildcard matching."""
    bus = MessageBus()
    received_exact = []
    received_wildcard = []

    def on_exact(msg):
        received_exact.append(msg)

    async def on_wildcard(msg):
        received_wildcard.append(msg)

    bus.subscribe("audio.stage1.complete", on_exact)
    bus.subscribe("audio.*", on_wildcard)

    bus_task = asyncio.create_task(bus.start())

    await bus.publish(
        topic="audio.stage1.complete",
        payload={"result": "ok"},
        sender="test_runner",
        priority=MessagePriority.HIGH,
    )

    # Allow delivery loop to process
    await asyncio.sleep(0.15)
    await bus.stop()
    bus_task.cancel()

    assert len(received_exact) == 1
    assert received_exact[0].payload["result"] == "ok"
    assert len(received_wildcard) == 1

    # Check history
    history = bus.get_history(topic="audio.stage1.complete")
    assert len(history) == 1
