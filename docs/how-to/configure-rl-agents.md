# Configure RL Agents

## Overview

ETHOS uses a Reinforcement Learning multi-agent system for intelligent audio mastering:

- **CriticAgent** — Evaluates audio quality via neural network scoring
- **EQRLAgent** — Learns optimal EQ parameters through policy gradient
- **DynamicsRLAgent** — Learns compression/dynamics parameters
- **HGOCoordinator** — Mediates conflicts between competing agents

## Goal Hierarchy

The HGO Coordinator resolves conflicts using a priority-ordered goal hierarchy:

```python
from ethos.core.audio_ontology import (
    create_clarity_goal,
    create_warmth_goal,
    create_punch_goal,
)

goals = [
    create_clarity_goal(target=0.8, priority=1.0),   # Highest priority
    create_warmth_goal(target=0.7, priority=0.8),
    create_punch_goal(target=0.6, priority=0.6),
]
```

## Drift Detection Settings

The `ConceptDriftDetector` monitors for out-of-distribution behavior:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_critic_confidence` | `0.65` | Minimum Critic evaluation confidence |
| `max_eq_gain_db` | `12.0` | Maximum allowed EQ gain (±dB) |
| `max_compression_ratio` | `16.0` | Maximum compression ratio |

```python
from ethos.agents.rl.drift_detector import ConceptDriftDetector

detector = ConceptDriftDetector(
    min_critic_confidence=0.70,
    max_eq_gain_db=10.0,
    max_compression_ratio=12.0,
)
```

## Safe Mode

When drift is detected, the system automatically engages **Safe Mode**:

- **EQ agents** → Conservative 1.5 dB presence boost at 3.5 kHz
- **Dynamics agents** → Transparent 2.5:1 bus compression at -14 dBFS
- **Other agents** → Passthrough (no processing)

Safe Mode ensures musically safe output even when neural policies are unreliable.

## Monitoring Agent Performance

```python
coordinator = HGOCoordinator(goal_hierarchy=goals)
stats = coordinator.get_statistics()
# Returns: total_coordinations, total_conflicts, conflict_rate
```
