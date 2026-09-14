"""
Dynamics/Compression Reinforcement Learning Agent for MAAPS

The Dynamics agent learns to adjust compression and dynamics processing through RL.
It "fights" with the EQ agent - both trying to optimize audio quality, requiring
the HGO coordinator to mediate conflicts.

This is the SECOND action agent - now the agents compete!
"""

import copy
import logging
from dataclasses import dataclass

import numpy as np
import ray
import torch
import torch.nn as nn
import torch.optim as optim

from ethos.core.audio_ontology import (
    AgentAction,
    AudioAttribute,
    AudioOntologyManager,
    AudioState,
)

logger = logging.getLogger(__name__)


@dataclass
class DynamicsSettings:
    """Settings for dynamics processing."""

    threshold: float  # dB (-60 to 0)
    ratio: float  # Compression ratio (1.0 to 20.0)
    attack: float  # Attack time in ms (0.1 to 100)
    release: float  # Release time in ms (10 to 1000)
    knee: float  # Knee width in dB (0 to 20)
    makeup_gain: float  # Makeup gain in dB (0 to 30)
    dry_wet: float  # Mix (0 to 1)

    def to_vector(self) -> np.ndarray:
        """Convert to normalized vector."""
        return np.array(
            [
                (self.threshold + 60) / 60,  # Normalize to [0, 1]
                np.log10(self.ratio) / np.log10(20),  # Log scale
                np.log10(self.attack) / np.log10(100),  # Log scale
                np.log10(self.release) / np.log10(1000),  # Log scale
                self.knee / 20,
                self.makeup_gain / 30,
                self.dry_wet,
            ]
        )

    @staticmethod
    def from_vector(vector: np.ndarray) -> "DynamicsSettings":
        """Create DynamicsSettings from vector."""
        return DynamicsSettings(
            threshold=vector[0] * 60 - 60,
            ratio=10 ** (vector[1] * np.log10(20)),
            attack=10 ** (vector[2] * np.log10(100)),
            release=10 ** (vector[3] * np.log10(1000)),
            knee=vector[4] * 20,
            makeup_gain=vector[5] * 30,
            dry_wet=np.clip(vector[6], 0, 1),
        )


class DynamicsActorNetwork(nn.Module):
    """Actor network for dynamics control policy."""

    def __init__(self, state_dim: int, action_dim: int = 7, hidden_dim: int = 256):
        super().__init__()

        self.network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, action_dim),
            nn.Tanh(),  # Output in [-1, 1]
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        return self.network(state)


class DynamicsCriticNetwork(nn.Module):
    """Critic network for Q-value estimation."""

    def __init__(self, state_dim: int, action_dim: int = 7, hidden_dim: int = 256):
        super().__init__()

        # Twin critics
        self.q1 = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

        self.q2 = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(
        self, state: torch.Tensor, action: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        x = torch.cat([state, action], dim=-1)
        return self.q1(x), self.q2(x)

    def q1_forward(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        x = torch.cat([state, action], dim=-1)
        return self.q1(x)


class DynamicsReplayBuffer:
    """Replay buffer for dynamics agent."""

    def __init__(self, max_size: int = 100000):
        self.max_size = max_size
        self.buffer = []
        self.position = 0

    def add(self, state, action, reward, next_state, done):
        if len(self.buffer) < self.max_size:
            self.buffer.append(None)
        self.buffer[self.position] = (state, action, reward, next_state, done)
        self.position = (self.position + 1) % self.max_size

    def sample(self, batch_size: int):
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)
        batch = [self.buffer[idx] for idx in indices]

        states = np.array([item[0] for item in batch])
        actions = np.array([item[1] for item in batch])
        rewards = np.array([item[2] for item in batch])
        next_states = np.array([item[3] for item in batch])
        dones = np.array([item[4] for item in batch])

        return states, actions, rewards, next_states, dones

    def size(self):
        return len(self.buffer)


@ray.remote
class DynamicsRLAgent:
    """
    Dynamics/Compression agent using TD3 reinforcement learning.
    Learns to adjust compression parameters to maximize Critic satisfaction.

    This agent will compete with the EQ agent - both trying to improve audio,
    potentially conflicting. The HGO coordinator will mediate.
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        device: str = "cpu",
        learning_rate: float = 3e-4,
        gamma: float = 0.99,
        tau: float = 0.005,
        policy_noise: float = 0.2,
        noise_clip: float = 0.5,
        policy_delay: int = 2,
        exploration_noise: float = 0.1,
    ):
        """
        Initialize Dynamics RL agent.

        Args:
            sample_rate: Audio sample rate
            device: "cpu" or "cuda"
            learning_rate: Learning rate
            gamma: Discount factor
            tau: Target network update rate
            policy_noise: Noise for target policy smoothing
            noise_clip: Max noise clip
            policy_delay: Delay for policy updates
            exploration_noise: Exploration noise std
        """
        self.sample_rate = sample_rate
        self.device = torch.device(device)

        # RL hyperparameters
        self.gamma = gamma
        self.tau = tau
        self.policy_noise = policy_noise
        self.noise_clip = noise_clip
        self.policy_delay = policy_delay
        self.exploration_noise = exploration_noise

        # State/action dimensions
        # State: ontology vector (20) + current dynamics settings (7)
        self.state_dim = 20 + 7
        # Action: dynamics adjustments (7 parameters)
        self.action_dim = 7

        # Initialize networks
        self.actor = DynamicsActorNetwork(self.state_dim, self.action_dim).to(self.device)
        self.actor_target = copy.deepcopy(self.actor)
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=learning_rate)

        self.critic = DynamicsCriticNetwork(self.state_dim, self.action_dim).to(self.device)
        self.critic_target = copy.deepcopy(self.critic)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=learning_rate)

        # Replay buffer
        self.replay_buffer = DynamicsReplayBuffer()

        # Current dynamics settings
        self.current_dynamics = self._initialize_dynamics()

        # Training stats
        self.total_steps = 0
        self.training_history = []

        # Ontology
        self.ontology = AudioOntologyManager()

        logger.info("Dynamics RL agent initialized")

    def _initialize_dynamics(self) -> DynamicsSettings:
        """Initialize with default/neutral dynamics settings."""
        return DynamicsSettings(
            threshold=-20.0,
            ratio=2.0,
            attack=10.0,
            release=100.0,
            knee=5.0,
            makeup_gain=0.0,
            dry_wet=0.5,
        )

    def apply_compressor(self, audio: np.ndarray, settings: DynamicsSettings) -> np.ndarray:
        """
        Apply compression to audio.

        Simple feed-forward compressor implementation.

        Args:
            audio: Input audio (mono)
            settings: Compression settings

        Returns:
            Compressed audio
        """
        # Convert to dB
        epsilon = 1e-10
        audio_abs = np.abs(audio) + epsilon
        audio_db = 20 * np.log10(audio_abs)

        # Compute gain reduction
        gain_reduction = np.zeros_like(audio_db)

        # Knee processing
        for i, db in enumerate(audio_db):
            if db < settings.threshold - settings.knee / 2:
                # Below knee, no compression
                gain_reduction[i] = 0
            elif db > settings.threshold + settings.knee / 2:
                # Above knee, full compression
                over = db - settings.threshold
                gain_reduction[i] = over * (1 - 1 / settings.ratio)
            else:
                # In knee, smooth transition
                over = db - (settings.threshold - settings.knee / 2)
                gain_reduction[i] = over**2 / (2 * settings.knee) * (1 - 1 / settings.ratio)

        # Simple envelope follower for attack/release
        envelope = np.zeros_like(gain_reduction)
        for i in range(1, len(gain_reduction)):
            if gain_reduction[i] > envelope[i - 1]:
                # Attack
                attack_coef = 1 - np.exp(-1000 / (settings.attack * self.sample_rate))
                envelope[i] = envelope[i - 1] + attack_coef * (gain_reduction[i] - envelope[i - 1])
            else:
                # Release
                release_coef = 1 - np.exp(-1000 / (settings.release * self.sample_rate))
                envelope[i] = envelope[i - 1] + release_coef * (gain_reduction[i] - envelope[i - 1])

        # Apply gain reduction
        gain_linear = 10 ** (-(envelope - settings.makeup_gain) / 20)
        compressed = audio * gain_linear

        # Dry/wet mix
        output = settings.dry_wet * compressed + (1 - settings.dry_wet) * audio

        return output

    def select_action(
        self, audio_state: AudioState, add_noise: bool = True
    ) -> tuple[np.ndarray, DynamicsSettings]:
        """
        Select dynamics adjustment action.

        Args:
            audio_state: Current ontology state
            add_noise: Add exploration noise

        Returns:
            action: Action vector
            new_dynamics: New dynamics settings
        """
        # Construct state
        ontology_vector = audio_state.to_vector()
        dynamics_vector = self.current_dynamics.to_vector()
        state = np.concatenate([ontology_vector, dynamics_vector])

        # Get action from policy
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        self.actor.eval()
        with torch.no_grad():
            action = self.actor(state_tensor).cpu().numpy()[0]

        # Add exploration noise
        if add_noise:
            noise = np.random.normal(0, self.exploration_noise, size=action.shape)
            action = np.clip(action + noise, -1, 1)

        # Convert action to dynamics adjustments
        current_vector = self.current_dynamics.to_vector()
        new_vector = np.clip(current_vector + action * 0.1, 0, 1)  # Small adjustments
        new_dynamics = DynamicsSettings.from_vector(new_vector)

        return action, new_dynamics

    def train_step(self, batch_size: int = 256) -> dict | None:
        """
        Perform one training step.

        Args:
            batch_size: Batch size

        Returns:
            Training metrics
        """
        if self.replay_buffer.size() < batch_size:
            return None

        # Sample batch
        states, actions, rewards, next_states, dones = self.replay_buffer.sample(batch_size)

        # Convert to tensors
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.FloatTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).unsqueeze(-1).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).unsqueeze(-1).to(self.device)

        # Update critic
        with torch.no_grad():
            # Target policy smoothing
            noise = (torch.randn_like(actions) * self.policy_noise).clamp(
                -self.noise_clip, self.noise_clip
            )
            next_actions = (self.actor_target(next_states) + noise).clamp(-1, 1)

            # Compute target Q
            target_q1, target_q2 = self.critic_target(next_states, next_actions)
            target_q = torch.min(target_q1, target_q2)
            target_q = rewards + (1 - dones) * self.gamma * target_q

        # Current Q estimates
        current_q1, current_q2 = self.critic(states, actions)

        # Critic loss
        critic_loss = nn.MSELoss()(current_q1, target_q) + nn.MSELoss()(current_q2, target_q)

        # Optimize critic
        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        self.critic_optimizer.step()

        # Delayed policy update
        actor_loss = None
        if self.total_steps % self.policy_delay == 0:
            # Compute actor loss
            actor_loss = -self.critic.q1_forward(states, self.actor(states)).mean()

            # Optimize actor
            self.actor_optimizer.zero_grad()
            actor_loss.backward()
            self.actor_optimizer.step()

            # Update target networks
            self._update_target_networks()

        self.total_steps += 1

        metrics = {
            "critic_loss": critic_loss.item(),
            "actor_loss": actor_loss.item() if actor_loss is not None else None,
            "total_steps": self.total_steps,
        }

        self.training_history.append(metrics)
        return metrics

    def _update_target_networks(self):
        """Soft update of target networks."""
        for param, target_param in zip(self.actor.parameters(), self.actor_target.parameters()):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)

        for param, target_param in zip(self.critic.parameters(), self.critic_target.parameters()):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)

    def store_experience(
        self,
        state: AudioState,
        action: np.ndarray,
        reward: float,
        next_state: AudioState,
        done: bool,
    ):
        """Store experience in replay buffer."""
        state_vector = np.concatenate([state.to_vector(), self.current_dynamics.to_vector()])
        next_state_vector = np.concatenate(
            [next_state.to_vector(), self.current_dynamics.to_vector()]
        )

        self.replay_buffer.add(state_vector, action, reward, next_state_vector, done)

    def process_audio(
        self, audio: np.ndarray, audio_state: AudioState
    ) -> tuple[np.ndarray, AgentAction]:
        """
        Process audio with dynamics.

        Args:
            audio: Input audio
            audio_state: Current ontology state

        Returns:
            processed_audio: Output audio
            action: Action taken
        """
        # Select action
        action_vector, new_dynamics = self.select_action(audio_state, add_noise=True)

        # Apply dynamics
        processed_audio = self.apply_compressor(audio, new_dynamics)

        # Update current dynamics
        self.current_dynamics = new_dynamics

        # Create action object
        action = AgentAction(
            agent_id="dynamics_rl_agent",
            action_type="dynamics_adjustment",
            parameters={
                "threshold": new_dynamics.threshold,
                "ratio": new_dynamics.ratio,
                "attack": new_dynamics.attack,
                "release": new_dynamics.release,
                "knee": new_dynamics.knee,
                "makeup_gain": new_dynamics.makeup_gain,
                "dry_wet": new_dynamics.dry_wet,
            },
            confidence=0.8,
        )

        return processed_audio, action

    def save_model(self, path: str):
        """Save model checkpoint."""
        torch.save(
            {
                "actor_state_dict": self.actor.state_dict(),
                "actor_target_state_dict": self.actor_target.state_dict(),
                "critic_state_dict": self.critic.state_dict(),
                "critic_target_state_dict": self.critic_target.state_dict(),
                "actor_optimizer": self.actor_optimizer.state_dict(),
                "critic_optimizer": self.critic_optimizer.state_dict(),
                "total_steps": self.total_steps,
            },
            path,
        )
        logger.info(f"Saved Dynamics RL model to {path}")

    def load_model(self, path: str):
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.device, weights_only=True)
        self.actor.load_state_dict(checkpoint["actor_state_dict"])
        self.actor_target.load_state_dict(checkpoint["actor_target_state_dict"])
        self.critic.load_state_dict(checkpoint["critic_state_dict"])
        self.critic_target.load_state_dict(checkpoint["critic_target_state_dict"])
        self.actor_optimizer.load_state_dict(checkpoint["actor_optimizer"])
        self.critic_optimizer.load_state_dict(checkpoint["critic_optimizer"])
        self.total_steps = checkpoint["total_steps"]
        logger.info(f"Loaded Dynamics RL model from {path}")


if __name__ == "__main__":
    # Example usage
    import ray

    ray.init(ignore_reinit_error=True)

    # Create Dynamics agent
    dynamics_agent = DynamicsRLAgent.remote()

    # Test with dummy audio
    dummy_audio = np.random.randn(44100)
    dummy_state = AudioState()
    dummy_state.set_attribute(AudioAttribute.PUNCH, 0.5)

    processed, action = ray.get(dynamics_agent.process_audio.remote(dummy_audio, dummy_state))
    print(f"Processed audio shape: {processed.shape}")
    print(f"Action: {action.action_type}")

    ray.shutdown()
