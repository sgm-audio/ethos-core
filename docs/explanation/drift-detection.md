# Drift Detection & Safe Mode

## The Problem

Neural RL agents can propose extreme or dangerous DSP parameters when they encounter audio that differs significantly from their training distribution. An unchecked EQ agent might propose +18 dB boosts that cause clipping, or a dynamics agent might suggest a 30:1 compression ratio that destroys dynamics.

## ConceptDriftDetector

The `ConceptDriftDetector` continuously monitors for two types of drift:

### Audio Data Drift

Detects out-of-distribution input audio characteristics:

| Condition | Severity | Threshold |
|-----------|----------|-----------|
| Excessive clipping | 0.8 | Peak > 0.1 dBFS |
| Hyper-compression | 0.7 | LUFS > -5.0 |
| Non-standard sample rate | 0.5 | Not 44.1/48/88.2/96 kHz |
| Near-zero dynamic range | 0.6 | Dynamic range < 2.0 dB |

### RL Concept Drift

Detects unreliable neural policy outputs:

| Condition | Severity | Threshold |
|-----------|----------|-----------|
| Low Critic confidence | 0.75 | Confidence < 0.65 |
| Extreme EQ gain | 0.85 | Gain > ±12 dB |
| Extreme compression ratio | 0.8 | Ratio > 16:1 |

## DriftType Enum

```python
class DriftType(Enum):
    NO_DRIFT = "no_drift"
    DATA_DRIFT = "audio_data_drift"
    CONCEPT_DRIFT = "rl_concept_drift"
    CONFIDENCE_DRIFT = "critic_confidence_drift"
```

## Safe Mode

When drift severity ≥ 0.7, Safe Mode automatically replaces neural proposals with conservative deterministic DSP heuristics:

| Agent Type | Safe Fallback |
|------------|---------------|
| **EQ agents** | 1.5 dB presence boost at 3.5 kHz (Q=0.707) |
| **Dynamics agents** | 2.5:1 compression at -14 dBFS, 30ms attack, 100ms release |
| **Other agents** | Passthrough (no processing) |

These fallbacks are musically conservative and acoustically safe — they will never damage audio quality.

## Integration with HGOCoordinator

Safe Mode is checked as the first gate in `HGOCoordinator.resolve_conflicts()`:

```python
def resolve_conflicts(self, proposals, conflicts, current_state, critic_confidence=0.85):
    # Concept drift & safety gate
    drift_report = self.drift_detector.check_rl_concept_drift(
        critic_confidence=critic_confidence,
        proposals=proposals,
        current_state=current_state,
    )
    if drift_report.safe_mode_activated:
        # Replace all neural proposals with deterministic heuristics
        safe_proposals = [
            self.drift_detector.get_safe_fallback_action(p.agent_id)
            for p in proposals
        ]
        return CoordinationDecision(approved_proposals=safe_proposals, ...)
```

## Monitoring

Drift events are logged with severity and tracked in `drift_detector.drift_history` for post-hoc analysis.
