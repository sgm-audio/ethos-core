"""
ETHOS ML Ops & Drift Detection Engine
Monitors Audio Data Drift and RL Concept Drift (Critic confidence & extreme proposals).
Provides automatic fallback to deterministic DSP heuristics (Safe Mode).
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ethos.core.audio_ontology import AgentAction, AudioAttribute, AudioState

logger = logging.getLogger(__name__)


class DriftType(Enum):
    NO_DRIFT = "no_drift"
    DATA_DRIFT = "audio_data_drift"
    CONCEPT_DRIFT = "rl_concept_drift"
    CONFIDENCE_DRIFT = "critic_confidence_drift"


@dataclass
class DriftReport:
    drift_type: DriftType
    severity: float  # 0.0 to 1.0
    reason: str
    metrics: dict[str, Any] = field(default_factory=dict)
    safe_mode_activated: bool = False


class ConceptDriftDetector:
    """
    Monitors input audio distributions, Critic evaluation confidence, and
    RL agent proposal extremities to prevent out-of-distribution hallucinations.
    """

    def __init__(
        self,
        min_critic_confidence: float = 0.65,
        max_eq_gain_db: float = 12.0,
        max_compression_ratio: float = 16.0,
    ):
        self.min_critic_confidence = min_critic_confidence
        self.max_eq_gain_db = max_eq_gain_db
        self.max_compression_ratio = max_compression_ratio
        self.safe_mode_active = False
        self.drift_history: list[DriftReport] = []

    def check_audio_data_drift(
        self,
        peak_db: float,
        lufs: float,
        sample_rate: int,
        dynamic_range_db: float,
    ) -> DriftReport:
        """
        Detect out-of-distribution audio input characteristics (e.g. clipping,
        extreme brickwall squashing, abnormal sample rates).
        """
        reasons = []
        severity = 0.0

        if peak_db > 0.1:
            reasons.append(f"Excessive clipping: peak {peak_db:.2f} dBFS")
            severity = max(severity, 0.8)
        if lufs > -5.0:
            reasons.append(f"Hyper-compressed signal: {lufs:.1f} LUFS")
            severity = max(severity, 0.7)
        if sample_rate not in (44100, 48000, 88200, 96000):
            reasons.append(f"Non-standard sample rate: {sample_rate} Hz")
            severity = max(severity, 0.5)
        if dynamic_range_db < 2.0:
            reasons.append(f"Near-zero dynamic range: {dynamic_range_db:.1f} dB")
            severity = max(severity, 0.6)

        if reasons:
            report = DriftReport(
                drift_type=DriftType.DATA_DRIFT,
                severity=severity,
                reason=" | ".join(reasons),
                metrics={
                    "peak_db": peak_db,
                    "lufs": lufs,
                    "sample_rate": sample_rate,
                    "dynamic_range": dynamic_range_db,
                },
                safe_mode_activated=severity >= 0.7,
            )
            if report.safe_mode_activated:
                self.safe_mode_active = True
                logger.warning("Audio Data Drift triggered Safe Mode: %s", report.reason)
            self.drift_history.append(report)
            return report

        return DriftReport(
            drift_type=DriftType.NO_DRIFT, severity=0.0, reason="Nominal distribution"
        )

    def check_rl_concept_drift(
        self,
        critic_confidence: float,
        proposals: list[Any],
        current_state: AudioState,
    ) -> DriftReport:
        """
        Evaluate if Critic agent is uncertain or if EQ/Dynamics agents
        propose wild, unnatural acoustic interventions (> ±12 dB, extreme ratios).
        """
        reasons = []
        severity = 0.0

        # Check Critic confidence
        if critic_confidence < self.min_critic_confidence:
            reasons.append(
                f"Critic confidence {critic_confidence:.2f} below threshold {self.min_critic_confidence:.2f}"
            )
            severity = max(severity, 0.75)

        # Inspect parameter boundaries in proposals
        for prop in proposals:
            action = getattr(prop, "action", prop)
            params = getattr(action, "parameters", {})

            # EQ gain inspection
            gain = params.get("gain")
            if gain is not None and abs(gain) > self.max_eq_gain_db:
                reasons.append(
                    f"Extreme EQ gain proposal ({gain:.1f} dB > {self.max_eq_gain_db} dB limit) by {getattr(prop, 'agent_id', 'agent')}"
                )
                severity = max(severity, 0.85)

            # Compression ratio inspection
            ratio = params.get("ratio")
            if ratio is not None and ratio > self.max_compression_ratio:
                reasons.append(
                    f"Extreme compression ratio ({ratio:.1f}:1 > {self.max_compression_ratio}:1 limit)"
                )
                severity = max(severity, 0.8)

        if reasons:
            drift_type = (
                DriftType.CONFIDENCE_DRIFT
                if critic_confidence < self.min_critic_confidence
                else DriftType.CONCEPT_DRIFT
            )
            report = DriftReport(
                drift_type=drift_type,
                severity=severity,
                reason=" | ".join(reasons),
                metrics={"critic_confidence": critic_confidence, "proposals_count": len(proposals)},
                safe_mode_activated=True,
            )
            self.safe_mode_active = True
            self.drift_history.append(report)
            logger.warning("RL Concept Drift detected: %s. Safe Mode ENGAGED.", report.reason)
            return report

        return DriftReport(
            drift_type=DriftType.NO_DRIFT, severity=0.0, reason="Policies within nominal bounds"
        )

    def get_safe_fallback_action(self, agent_id: str) -> AgentAction:
        """
        Generates conservative, deterministic DSP heuristic fallback action (Safe Mode).
        Ensures acoustic musicality when neural policies exhibit drift.
        """
        if "eq" in agent_id.lower():
            # Conservative musical tilt: gentle 1.5 dB presence boost, gentle 1.0 dB mud reduction
            return AgentAction(
                agent_id=agent_id,
                action_type="safe_mode_parametric_eq",
                parameters={"freq": 3500.0, "gain": 1.5, "q": 0.707},
                expected_impact={AudioAttribute.CLARITY: 0.1, AudioAttribute.HARSHNESS: 0.0},
                confidence=1.0,
            )
        elif "dynamic" in agent_id.lower():
            # Transparent 2.5:1 gentle bus compressor with slow attack
            return AgentAction(
                agent_id=agent_id,
                action_type="safe_mode_compression",
                parameters={
                    "ratio": 2.5,
                    "threshold": -14.0,
                    "attack": 30.0,
                    "release": 100.0,
                    "makeup_gain": 1.0,
                },
                expected_impact={AudioAttribute.PUNCH: 0.1, AudioAttribute.COMPRESSION: 0.15},
                confidence=1.0,
            )
        else:
            return AgentAction(
                agent_id=agent_id,
                action_type="safe_mode_passthrough",
                parameters={},
                confidence=1.0,
            )
