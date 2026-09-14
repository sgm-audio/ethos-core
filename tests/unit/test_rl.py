"""
Unit tests for Reinforcement Learning MAAPS agents:
- CriticAgent & CriticNetwork
- DynamicsRLAgent & DynamicsActorNetwork
- EQRLAgent & ActorNetwork
- HGOCoordinator (conflict resolution)
"""

import numpy as np
import torch

from ethos.agents.rl.critic_agent import CriticAgent, CriticNetwork
from ethos.agents.rl.dynamics_rl_agent import DynamicsActorNetwork, DynamicsSettings
from ethos.agents.rl.eq_rl_agent import ActorNetwork as EQActorNetwork
from ethos.agents.rl.hgo_coordinator import AgentProposal, ConflictType, HGOCoordinator
from ethos.core.ontology import (
    AgentAction,
    AudioAttribute,
    AudioState,
    create_clarity_goal,
    create_warmth_goal,
)


def test_critic_network_forward_pass():
    """Verify Critic neural network accepts audio features and ontology state."""
    net = CriticNetwork(audio_feature_dim=128, ontology_dim=20, hidden_dim=64)
    audio_feat = torch.randn(2, 128)
    ontology_state = torch.randn(2, 20)

    satisfaction, attr_scores = net(audio_feat, ontology_state)
    assert satisfaction.shape == (2, 1)
    # Sigmoid output in [0, 1]
    assert (satisfaction >= 0.0).all() and (satisfaction <= 1.0).all()
    assert len(attr_scores) > 0


def test_critic_agent_evaluation():
    """Verify CriticAgent evaluation logic and satisfaction scoring."""
    # Obtain underlying un-wrapped class to test without starting a Ray cluster
    critic_cls = getattr(CriticAgent, "__ray_metadata__", None)
    cls = critic_cls.modified_class if critic_cls else CriticAgent
    agent = cls()

    state = AudioState()
    state.set_attribute(AudioAttribute.CLARITY, 0.75)
    state.set_attribute(AudioAttribute.WARMTH, 0.65)

    goals = [
        create_clarity_goal(target=0.8, priority=1.0),
        create_warmth_goal(target=0.7, priority=0.8),
    ]

    audio = np.sin(2 * np.pi * 440.0 * np.linspace(0, 1, 44100)).astype(np.float32)
    eval_result = agent.evaluate(audio, state, goals)
    assert 0.0 <= eval_result.satisfaction_score <= 1.0
    assert -1.0 <= eval_result.reward <= 1.0
    assert eval_result.confidence > 0.0


def test_dynamics_policy_network():
    """Verify Dynamics policy network output dimensions and settings mapping."""
    policy = DynamicsActorNetwork(state_dim=30, action_dim=7, hidden_dim=64)
    state_tensor = torch.randn(1, 30)
    actions = policy(state_tensor)
    # Should predict normalized compression parameters
    assert actions.shape == (1, 7)

    settings = DynamicsSettings(
        threshold=-18.0,
        ratio=3.5,
        attack=15.0,
        release=120.0,
        knee=6.0,
        makeup_gain=3.0,
        dry_wet=0.8,
    )
    vec = settings.to_vector()
    assert len(vec) == 7


def test_eq_policy_network():
    """Verify EQ policy network parameter shapes."""
    num_bands = 5
    action_dim = num_bands * 3
    policy = EQActorNetwork(state_dim=30, action_dim=action_dim, hidden_dim=64)
    state_tensor = torch.randn(1, 30)
    band_params = policy(state_tensor)
    assert band_params.shape == (1, action_dim)


def test_hgo_coordinator_conflict_detection():
    """Verify HGO coordinator detects conflicts and resolves compromises."""
    hgo_cls = getattr(HGOCoordinator, "__ray_metadata__", None)
    cls = hgo_cls.modified_class if hgo_cls else HGOCoordinator
    coordinator = cls()

    # EQ action affecting CLARITY and HARSHNESS
    eq_action = AgentAction(
        agent_id="EQAgent",
        action_type="eq_boost",
        parameters={"freq": 4000.0, "gain": 4.0},
        expected_impact={AudioAttribute.CLARITY: 0.25, AudioAttribute.HARSHNESS: 0.20},
    )
    prop_eq = AgentProposal(
        agent_id="EQAgent",
        action=eq_action,
        predicted_impact=eq_action.expected_impact,
        predicted_satisfaction=0.75,
        confidence=0.9,
    )

    # Dynamics action affecting PUNCH and COMPRESSION
    dyn_action = AgentAction(
        agent_id="DynamicsAgent",
        action_type="compress",
        parameters={"ratio": 4.0, "threshold": -15.0},
        expected_impact={AudioAttribute.PUNCH: 0.15, AudioAttribute.COMPRESSION: 0.30},
    )
    prop_dyn = AgentProposal(
        agent_id="DynamicsAgent",
        action=dyn_action,
        predicted_impact=dyn_action.expected_impact,
        predicted_satisfaction=0.80,
        confidence=0.85,
    )

    state = AudioState()
    [create_clarity_goal(0.8, 1.0)]

    conflicts = coordinator.detect_conflicts([prop_eq, prop_dyn], state)
    assert isinstance(conflicts, list)
    for c in conflicts:
        assert c.conflict_type in [
            ConflictType.NO_CONFLICT,
            ConflictType.PARAMETER_CONFLICT,
            ConflictType.GOAL_CONFLICT,
        ]
