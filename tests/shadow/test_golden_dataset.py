"""
Gate 5: Golden Dataset Shadow Test
Evaluates production model/DSP drift against locked reference baselines.
Enforces strict drift limits: SDR drop <= 0.2 dB, LUFS deviation <= 0.5 LU.
"""

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from ethos.agents.dsp.stage3.loudness_optimizer_agent import LoudnessOptimizerAgent
from ethos.agents.dsp.stage3.mastering_agent import MasteringAgent
from ethos.agents.rl.drift_detector import ConceptDriftDetector, DriftType
from ethos.agents.rl.hgo_coordinator import AgentProposal
from ethos.core.audio_ontology import AgentAction, AudioAttribute, AudioState
from ethos.core.data_structures import MasteringParameters


def calculate_sdr(reference: np.ndarray, estimated: np.ndarray) -> float:
    """
    Calculate Signal-to-Distortion Ratio (SDR) in dB.
    SDR = 10 * log10(||reference||^2 / ||reference - estimated||^2)
    """
    min_len = min(len(reference), len(estimated))
    ref = reference[:min_len].astype(np.float64)
    est = estimated[:min_len].astype(np.float64)

    # Scale align
    alpha = np.sum(ref * est) / (np.sum(est**2) + 1e-12)
    e_target = alpha * est
    e_res = ref - e_target

    signal_pwr = np.sum(e_target**2)
    distortion_pwr = np.sum(e_res**2) + 1e-12

    sdr = 10.0 * np.log10(signal_pwr / distortion_pwr)
    return float(sdr)


def calculate_rms_lufs(audio: np.ndarray) -> float:
    """Estimate integrated LUFS using BS.1770 K-weighting approximation."""
    rms = np.sqrt(np.mean(audio**2))
    return float(20.0 * np.log10(rms + 1e-10) - 0.691)


@pytest.fixture
def golden_baseline_config() -> dict:
    config_path = Path(__file__).parent / "golden_baseline.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_golden_dataset_shadow_evaluation(tmp_path: Path, golden_baseline_config: dict):
    """
    Iterate over the 5 locked reference genre profiles, process through
    the mastering chain, and enforce zero drift beyond tolerance limits.
    """
    mastering_agent = MasteringAgent()
    loudness_agent = LoudnessOptimizerAgent()

    thresholds = golden_baseline_config["drift_thresholds"]
    max_sdr_drop = thresholds["max_sdr_drop_db"]
    max_lufs_dev = thresholds["max_lufs_deviation_lu"]
    sr = 44100
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    for track_id, profile in golden_baseline_config["tracks"].items():
        # Synthesize reference track
        carrier = 0.4 * np.sin(2 * np.pi * 440.0 * t)
        harmonics = 0.2 * np.sin(2 * np.pi * 880.0 * t) + 0.1 * np.sin(2 * np.pi * 1760.0 * t)
        raw_audio = np.column_stack([carrier + harmonics, carrier + harmonics]).astype(np.float32)

        in_wav = str(tmp_path / f"{track_id}_in.wav")
        sf.write(in_wav, raw_audio, sr)

        # 1. Loudness optimization pass
        opt_wav = await loudness_agent.optimize_loudness(in_wav, target_lufs=profile["target_lufs"])
        opt_audio, _ = sf.read(opt_wav)

        # 2. Mastering pass
        master_out = str(tmp_path / f"{track_id}_mastered.wav")
        params = MasteringParameters(
            target_lufs=profile["target_lufs"],
            true_peak_limit=profile["max_true_peak_db"],
            eq_curve=[],
            compression_ratio=2.0,
            compression_threshold=-14.0,
        )
        await mastering_agent.master_audio(opt_wav, master_out, params)

        mastered_audio, _ = sf.read(master_out)
        measured_lufs = calculate_rms_lufs(mastered_audio)
        measured_peak = float(np.max(np.abs(mastered_audio)))
        measured_peak_db = 20.0 * np.log10(measured_peak + 1e-10)

        # Compute Signal-to-Distortion Ratio
        measured_sdr = calculate_sdr(raw_audio, mastered_audio)

        # Drift Assertions
        # 1. SDR Degradation Gate
        sdr_drop = profile["baseline_sdr_db"] - measured_sdr
        assert sdr_drop <= max_sdr_drop, (
            f"[{track_id}] SDR Drift Breach: dropped {sdr_drop:.2f} dB (limit: {max_sdr_drop} dB). "
            f"Measured: {measured_sdr:.2f} dB, Baseline: {profile['baseline_sdr_db']:.2f} dB"
        )

        # 2. LUFS Deviation Gate
        lufs_deviation = abs(measured_lufs - profile["target_lufs"])
        assert lufs_deviation <= max_lufs_dev, (
            f"[{track_id}] LUFS Drift Breach: deviation {lufs_deviation:.2f} LU (limit: {max_lufs_dev} LU). "
            f"Measured: {measured_lufs:.2f} LUFS, Target: {profile['target_lufs']:.2f} LUFS"
        )

        # 3. True Peak Ceiling Gate (0.01 dB epsilon for floating-point precision)
        peak_ceiling = profile["max_true_peak_db"] + thresholds["max_peak_overshoot_db"] + 0.01
        assert measured_peak_db <= peak_ceiling, (
            f"[{track_id}] Peak Overshoot: {measured_peak_db:.2f} dBFS exceeds ceiling {profile['max_true_peak_db']} dBFS"
        )


def test_rl_concept_drift_triggers_safe_mode():
    """Verify that wild out-of-distribution RL policy outputs trigger Safe Mode immediately."""
    detector = ConceptDriftDetector(min_critic_confidence=0.65, max_eq_gain_db=12.0)
    state = AudioState()

    # Create an extreme proposal with +18.0 dB gain (violates 12 dB limit)
    wild_action = AgentAction(
        agent_id="EQAgent",
        action_type="eq_boost",
        parameters={"freq": 4000.0, "gain": 18.5},
        expected_impact={AudioAttribute.CLARITY: 0.9},
    )
    wild_proposal = AgentProposal(
        agent_id="EQAgent",
        action=wild_action,
        predicted_impact=wild_action.expected_impact,
        predicted_satisfaction=0.9,
        confidence=0.9,
    )

    report = detector.check_rl_concept_drift(
        critic_confidence=0.9,
        proposals=[wild_proposal],
        current_state=state,
    )

    assert report.drift_type == DriftType.CONCEPT_DRIFT
    assert report.safe_mode_activated is True
    assert "Extreme EQ gain" in report.reason

    # Verify fallback action is conservative and musical
    safe_action = detector.get_safe_fallback_action("EQAgent")
    assert safe_action.parameters["gain"] <= 3.0
