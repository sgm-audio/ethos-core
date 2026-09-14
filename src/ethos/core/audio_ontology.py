"""
Compatibility module alias for audio ontology.
Exposes all symbols from ethos.core.ontology for backwards compatibility.
"""

from ethos.core.ontology import (
    AgentAction,
    AudioAttribute,
    AudioGoal,
    AudioOntologyManager,
    AudioState,
    FrequencyBand,
    create_balanced_mix_goals,
    create_clarity_goal,
    create_punch_goal,
    create_reduce_mud_goal,
    create_warmth_goal,
)

__all__ = [
    "AudioAttribute",
    "FrequencyBand",
    "AudioGoal",
    "AudioState",
    "AgentAction",
    "AudioOntologyManager",
    "create_clarity_goal",
    "create_warmth_goal",
    "create_reduce_mud_goal",
    "create_punch_goal",
    "create_balanced_mix_goals",
]
