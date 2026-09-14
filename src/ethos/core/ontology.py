"""
Audio Ontology for Multi-Agent Audio Processing System (MAAPS)

Defines the shared vocabulary and semantic understanding that agents use to
communicate about audio characteristics, goals, and transformations.

This ontology provides a common language for agents to reason about audio
quality attributes like "Clarity," "Warmth," "Mud," "Punch," etc.
"""

from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np


class AudioAttribute(Enum):
    """Core audio quality attributes in the ontology."""

    # Frequency Domain
    CLARITY = auto()  # High-frequency definition, articulation
    WARMTH = auto()  # Low-mid frequency richness
    BRIGHTNESS = auto()  # High-frequency presence
    MUD = auto()  # Low-mid frequency buildup (negative)
    HARSHNESS = auto()  # Upper-mid harshness (negative)
    THINNESS = auto()  # Lack of low-frequency content (negative)

    # Dynamics
    PUNCH = auto()  # Transient impact and attack
    COMPRESSION = auto()  # Dynamic range reduction
    EXPANSION = auto()  # Dynamic range increase
    SUSTAIN = auto()  # Note/sound length
    DENSITY = auto()  # Harmonic/sonic fullness

    # Spatial
    WIDTH = auto()  # Stereo width
    DEPTH = auto()  # Front-to-back dimension
    HEIGHT = auto()  # Vertical spatial dimension

    # Tonal Balance
    BALANCE = auto()  # Overall frequency balance
    PRESENCE = auto()  # Mid-range presence (vocal/lead focus)
    AIR = auto()  # Ultra-high frequency extension

    # Artifacts
    DISTORTION = auto()  # Harmonic/inharmonic distortion (negative)
    NOISE = auto()  # Background noise level (negative)
    CLIPPING = auto()  # Digital clipping (negative)


class FrequencyBand(Enum):
    """Standard frequency bands for audio processing."""

    SUB_BASS = (20, 60)  # Sub-bass
    BASS = (60, 250)  # Bass
    LOW_MID = (250, 500)  # Low-mids
    MID = (500, 2000)  # Mids
    HIGH_MID = (2000, 6000)  # High-mids
    PRESENCE = (6000, 12000)  # Presence
    BRILLIANCE = (12000, 20000)  # Brilliance/Air

    def __init__(self, low: float, high: float):
        self.low_freq = low
        self.high_freq = high


@dataclass
class AudioGoal:
    """
    Represents a target audio quality state.
    Used by agents to understand desired outcomes.
    """

    attribute: AudioAttribute
    target_value: float  # 0.0 to 1.0 (0 = none, 1 = maximum)
    priority: float = 0.5  # 0.0 to 1.0 (importance weight)
    tolerance: float = 0.1  # Acceptable deviation from target

    def is_satisfied(self, current_value: float) -> bool:
        """Check if current value satisfies the goal."""
        return abs(current_value - self.target_value) <= self.tolerance

    def distance_from_target(self, current_value: float) -> float:
        """Calculate normalized distance from target."""
        return abs(current_value - self.target_value)


@dataclass
class AudioState:
    """
    Represents the current state of audio in terms of ontology attributes.
    This is what the Critic agent evaluates.
    """

    attributes: dict[AudioAttribute, float] = field(default_factory=dict)
    confidence: dict[AudioAttribute, float] = field(default_factory=dict)
    timestamp: float | None = None

    def get_attribute(self, attr: AudioAttribute, default: float = 0.5) -> float:
        """Get attribute value with default."""
        return self.attributes.get(attr, default)

    def set_attribute(self, attr: AudioAttribute, value: float, confidence: float = 1.0):
        """Set attribute value with confidence."""
        self.attributes[attr] = np.clip(value, 0.0, 1.0)
        self.confidence[attr] = np.clip(confidence, 0.0, 1.0)

    def get_confidence(self, attr: AudioAttribute) -> float:
        """Get confidence in attribute measurement."""
        return self.confidence.get(attr, 0.0)

    def to_vector(self, attributes: list[AudioAttribute] | None = None) -> np.ndarray:
        """Convert state to feature vector for ML models."""
        if attributes is None:
            attributes = list(AudioAttribute)
        return np.array([self.get_attribute(attr) for attr in attributes])


@dataclass
class AgentAction:
    """
    Represents an action an agent can take (e.g., EQ adjustment, compression).
    """

    agent_id: str
    action_type: str  # "eq_adjustment", "compression", etc.
    parameters: dict[str, float]
    expected_impact: dict[AudioAttribute, float] = field(default_factory=dict)
    confidence: float = 1.0

    def estimate_impact_on_attribute(self, attr: AudioAttribute) -> float:
        """Estimate impact on specific attribute (-1.0 to 1.0)."""
        return self.expected_impact.get(attr, 0.0)


class AudioOntologyManager:
    """
    Manages the audio ontology and provides reasoning capabilities.
    Helps agents understand relationships between attributes and actions.
    """

    def __init__(self):
        # Define attribute relationships (correlations)
        # Positive correlation: increasing one tends to increase the other
        # Negative correlation: increasing one tends to decrease the other
        self.attribute_correlations = {
            (AudioAttribute.CLARITY, AudioAttribute.MUD): -0.8,
            (AudioAttribute.WARMTH, AudioAttribute.THINNESS): -0.7,
            (AudioAttribute.BRIGHTNESS, AudioAttribute.HARSHNESS): 0.6,
            (AudioAttribute.PUNCH, AudioAttribute.COMPRESSION): 0.5,
            (AudioAttribute.WIDTH, AudioAttribute.CLARITY): -0.3,
            (AudioAttribute.WARMTH, AudioAttribute.MUD): 0.4,
            (AudioAttribute.CLARITY, AudioAttribute.BRIGHTNESS): 0.7,
        }

        # Define frequency band -> attribute mappings
        self.frequency_attribute_map = {
            FrequencyBand.SUB_BASS: [AudioAttribute.WARMTH],
            FrequencyBand.BASS: [AudioAttribute.WARMTH, AudioAttribute.PUNCH],
            FrequencyBand.LOW_MID: [AudioAttribute.WARMTH, AudioAttribute.MUD],
            FrequencyBand.MID: [AudioAttribute.PRESENCE, AudioAttribute.CLARITY],
            FrequencyBand.HIGH_MID: [AudioAttribute.CLARITY, AudioAttribute.HARSHNESS],
            FrequencyBand.PRESENCE: [AudioAttribute.BRIGHTNESS, AudioAttribute.CLARITY],
            FrequencyBand.BRILLIANCE: [AudioAttribute.AIR, AudioAttribute.BRIGHTNESS],
        }

    def get_attribute_correlation(self, attr1: AudioAttribute, attr2: AudioAttribute) -> float:
        """Get correlation between two attributes."""
        key = (attr1, attr2) if (attr1, attr2) in self.attribute_correlations else (attr2, attr1)
        return self.attribute_correlations.get(key, 0.0)

    def get_conflicting_attributes(
        self, attr: AudioAttribute, threshold: float = 0.6
    ) -> list[AudioAttribute]:
        """Get attributes that conflict with the given attribute."""
        conflicts = []
        for (a1, a2), correlation in self.attribute_correlations.items():
            if correlation < -threshold:
                if a1 == attr:
                    conflicts.append(a2)
                elif a2 == attr:
                    conflicts.append(a1)
        return conflicts

    def get_synergistic_attributes(
        self, attr: AudioAttribute, threshold: float = 0.6
    ) -> list[AudioAttribute]:
        """Get attributes that work well together with the given attribute."""
        synergies = []
        for (a1, a2), correlation in self.attribute_correlations.items():
            if correlation > threshold:
                if a1 == attr:
                    synergies.append(a2)
                elif a2 == attr:
                    synergies.append(a1)
        return synergies

    def get_attributes_for_frequency_band(self, band: FrequencyBand) -> list[AudioAttribute]:
        """Get audio attributes affected by a frequency band."""
        return self.frequency_attribute_map.get(band, [])

    def get_frequency_bands_for_attribute(self, attr: AudioAttribute) -> list[FrequencyBand]:
        """Get frequency bands that affect an attribute."""
        bands = []
        for band, attributes in self.frequency_attribute_map.items():
            if attr in attributes:
                bands.append(band)
        return bands

    def estimate_satisfaction_score(
        self, current_state: AudioState, goals: list[AudioGoal]
    ) -> float:
        """
        Calculate overall satisfaction score (0.0 to 1.0).
        Used by Critic agent to evaluate audio quality.
        """
        if not goals:
            return 0.5

        total_weighted_satisfaction = 0.0
        total_weight = 0.0

        for goal in goals:
            current_value = current_state.get_attribute(goal.attribute)
            distance = goal.distance_from_target(current_value)

            # Convert distance to satisfaction (closer = better)
            satisfaction = 1.0 - min(distance / (goal.tolerance + 1e-6), 1.0)

            # Weight by priority
            weighted_satisfaction = satisfaction * goal.priority
            total_weighted_satisfaction += weighted_satisfaction
            total_weight += goal.priority

        # Normalize
        if total_weight > 0:
            return total_weighted_satisfaction / total_weight
        return 0.5

    def predict_action_impact(self, action: AgentAction, current_state: AudioState) -> AudioState:
        """
        Predict the resulting audio state after applying an action.
        Simple physics-based model for action consequences.
        """
        new_state = AudioState()
        new_state.attributes = current_state.attributes.copy()
        new_state.confidence = current_state.confidence.copy()

        # Apply direct impact
        for attr, impact in action.expected_impact.items():
            current_val = current_state.get_attribute(attr)
            new_val = np.clip(current_val + impact, 0.0, 1.0)
            new_state.set_attribute(attr, new_val, action.confidence)

        # Apply correlated effects
        for attr, impact in action.expected_impact.items():
            for other_attr in AudioAttribute:
                if other_attr != attr:
                    correlation = self.get_attribute_correlation(attr, other_attr)
                    if abs(correlation) > 0.3:
                        current_val = new_state.get_attribute(other_attr)
                        correlated_impact = impact * correlation * 0.3  # Damped correlation
                        new_val = np.clip(current_val + correlated_impact, 0.0, 1.0)
                        confidence = new_state.get_confidence(other_attr) * 0.9
                        new_state.set_attribute(other_attr, new_val, confidence)

        return new_state


# Convenience functions for creating common goals
def create_clarity_goal(target: float = 0.8, priority: float = 1.0) -> AudioGoal:
    """Create a goal to increase clarity."""
    return AudioGoal(AudioAttribute.CLARITY, target, priority)


def create_warmth_goal(target: float = 0.7, priority: float = 0.8) -> AudioGoal:
    """Create a goal to add warmth."""
    return AudioGoal(AudioAttribute.WARMTH, target, priority)


def create_reduce_mud_goal(target: float = 0.2, priority: float = 0.9) -> AudioGoal:
    """Create a goal to reduce mud."""
    return AudioGoal(AudioAttribute.MUD, target, priority)


def create_punch_goal(target: float = 0.8, priority: float = 0.9) -> AudioGoal:
    """Create a goal to increase punch."""
    return AudioGoal(AudioAttribute.PUNCH, target, priority)


def create_balanced_mix_goals() -> list[AudioGoal]:
    """Create a set of goals for a balanced mix."""
    return [
        create_clarity_goal(0.75, 1.0),
        create_warmth_goal(0.65, 0.8),
        create_reduce_mud_goal(0.25, 0.9),
        create_punch_goal(0.70, 0.85),
        AudioGoal(AudioAttribute.BALANCE, 0.80, 0.95),
        AudioGoal(AudioAttribute.WIDTH, 0.70, 0.7),
    ]


if __name__ == "__main__":
    # Example usage
    ontology = AudioOntologyManager()

    # Create current audio state
    state = AudioState()
    state.set_attribute(AudioAttribute.CLARITY, 0.4, confidence=0.9)
    state.set_attribute(AudioAttribute.WARMTH, 0.7, confidence=0.8)
    state.set_attribute(AudioAttribute.MUD, 0.6, confidence=0.85)

    # Create goals
    goals = [
        create_clarity_goal(0.8, 1.0),
        create_reduce_mud_goal(0.3, 0.9),
    ]

    # Evaluate satisfaction
    satisfaction = ontology.estimate_satisfaction_score(state, goals)
    print(f"Current satisfaction: {satisfaction:.2f}")

    # Check attribute relationships
    conflicts = ontology.get_conflicting_attributes(AudioAttribute.CLARITY)
    print(f"Attributes conflicting with CLARITY: {conflicts}")

    synergies = ontology.get_synergistic_attributes(AudioAttribute.CLARITY)
    print(f"Attributes synergistic with CLARITY: {synergies}")
