"""
EQ Reinforcement Learning Agent for MAAPS

The EQ agent learns to adjust equalization bands through reinforcement learning.
It receives feedback from the Critic agent and explores parameter space to
maximize user satisfaction.

This is the FIRST action agent - it learns by randomly adjusting EQ until the Critic smiles.
"""

import copy
import logging
from dataclasses import dataclass

import numpy as np
import ray
import torch
import torch.nn as nn
import torch.optim as optim
from scipy import signal

from ethos.core.audio_ontology import (
    AgentAction,
    AudioAttribute,
    AudioOntologyManager,
    AudioState,
)

logger = logging.getLogger(__name__)


@dataclass
class EQBandSettings:
    """Settings for one EQ band."""

    frequency: float  # Center frequency in Hz
    gain: float  # Gain in dB (-20 to +20)
    q_factor: float  # Q factor (bandwidth), 0.1 to 10.0
    band_type: str = "peak"  # "peak", "lowshelf", "highshelf", "lowpass", "highpass"


@dataclass
class EQState:
    """Complete EQ state."""

    bands: list[EQBandSettings]

    def to_vector(self) -> np.ndarray:
        """Convert to flat vector for RL."""
        vector = []
        for band in self.bands:
            vector.extend(
                [
                    np.log10(band.frequency) / 5.0,  # Normalize log freq
                    band.gain / 20.0,  # Normalize to [-1, 1]
                    np.log10(band.q_factor) / 2.0,  # Normalize log Q
                ]
            )
        return np.array(vector)

    @staticmethod
    def from_vector(vector: np.ndarray, num_bands: int = 8) -> "EQState":
        """Create EQState from vector."""
        bands = []
        vector = vector.reshape(num_bands, 3)
        for _i, (freq_norm, gain_norm, q_norm) in enumerate(vector):
            bands.append(
                EQBandSettings(
                    frequency=10 ** (freq_norm * 5.0),
                    gain=gain_norm * 20.0,
                    q_factor=10 ** (q_norm * 2.0),
                )
            )
        return EQState(bands)


class ActorNetwork(nn.Module):
    """Actor network for policy (continuous action space)."""

    def __init__(
        self, state_dim: int, action_dim: int, hidden_dim: int = 256, max_action: float = 1.0
    ):
        super().__init__()

        self.max_action = max_action

        self.network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim),
            nn.Tanh(),  # Output in [-1, 1]
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Forward pass."""
        return self.network(state) * self.max_action


class CriticNetworkRL(nn.Module):
    """Critic network for Q-value estimation (TD3 style)."""

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 256):
        super().__init__()

        # Q1 architecture
        self.q1 = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

        # Q2 architecture (twin critic)
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
        """Forward pass, returns both Q values."""
        x = torch.cat([state, action], dim=-1)
        return self.q1(x), self.q2(x)

    def q1_forward(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """Forward pass for Q1 only."""
        x = torch.cat([state, action], dim=-1)
        return self.q1(x)


class ReplayBuffer:
    """Experience replay buffer for RL training."""

    def __init__(self, max_size: int = 100000):
        self.max_size = max_size
        self.buffer = []
        self.position = 0

    def add(self, state, action, reward, next_state, done):
        """Add experience to buffer."""
        if len(self.buffer) < self.max_size:
            self.buffer.append(None)
        self.buffer[self.position] = (state, action, reward, next_state, done)
        self.position = (self.position + 1) % self.max_size

    def sample(self, batch_size: int):
        """Sample batch from buffer."""
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)
        batch = [self.buffer[idx] for idx in indices]

        states = np.array([item[0] for item in batch])
        actions = np.array([item[1] for item in batch])
        rewards = np.array([item[2] for item in batch])
        next_states = np.array([item[3] for item in batch])
        dones = np.array([item[4] for item in batch])

        return states, actions, rewards, next_states, dones

    def size(self):
        """Get buffer size."""
        return len(self.buffer)


@ray.remote
class EQRLAgent:
    """
    EQ agent using TD3 (Twin Delayed DDPG) reinforcement learning.
    Learns to adjust EQ bands to maximize Critic satisfaction.
    """

    def __init__(
        self,
        num_bands: int = 8,
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
        Initialize EQ RL agent.

        Args:
            num_bands: Number of EQ bands
            sample_rate: Audio sample rate
            device: "cpu" or "cuda"
            learning_rate: Learning rate
            gamma: Discount factor
            tau: Target network update rate
            policy_noise: Noise added to target policy
            noise_clip: Max noise
            policy_delay: Delay for policy updates
            exploration_noise: Exploration noise std
        """
        self.num_bands = num_bands
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
        # State: ontology vector (20) + current EQ settings (num_bands * 3)
        self.state_dim = 20 + (num_bands * 3)
        # Action: EQ adjustments (num_bands * 3: freq, gain, Q)
        self.action_dim = num_bands * 3

        # Initialize networks
        self.actor = ActorNetwork(self.state_dim, self.action_dim).to(self.device)
        self.actor_target = copy.deepcopy(self.actor)
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=learning_rate)

        self.critic = CriticNetworkRL(self.state_dim, self.action_dim).to(self.device)
        self.critic_target = copy.deepcopy(self.critic)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=learning_rate)

        # Replay buffer
        self.replay_buffer = ReplayBuffer()

        # Current EQ state
        self.current_eq = self._initialize_eq()

        # Training stats
        self.total_steps = 0
        self.training_history = []

        # Ontology
        self.ontology = AudioOntologyManager()

        logger.info(f"EQ RL agent initialized with {num_bands} bands")

    def _initialize_eq(self) -> EQState:
        """Initialize EQ with default flat settings."""
        # Standard frequency bands
        frequencies = [60, 120, 250, 500, 1000, 2000, 4000, 8000][: self.num_bands]

        bands = [EQBandSettings(frequency=freq, gain=0.0, q_factor=1.0) for freq in frequencies]

        return EQState(bands)

    def apply_eq(self, audio: np.ndarray, eq_state: EQState) -> np.ndarray:
        """
        Apply EQ to audio signal.

        Args:
            audio: Input audio (mono)
            eq_state: EQ settings

        Returns:
            Processed audio
        """
        processed = audio.copy()

        for band in eq_state.bands:
            if abs(band.gain) < 0.1:  # Skip near-zero gains
                continue

            # Design filter
            w0 = 2 * np.pi * band.frequency / self.sample_rate
            alpha = np.sin(w0) / (2 * band.q_factor)

            # Peak filter coefficients
            A = 10 ** (band.gain / 40)  # Convert dB to amplitude
            b0 = 1 + alpha * A
            b1 = -2 * np.cos(w0)
            b2 = 1 - alpha * A
            a0 = 1 + alpha / A
            a1 = -2 * np.cos(w0)
            a2 = 1 - alpha / A

            # Normalize
            b = np.array([b0, b1, b2]) / a0
            a = np.array([1, a1 / a0, a2 / a0])

            # Apply filter
            processed = signal.lfilter(b, a, processed)

        return processed

    def select_action(
        self, audio_state: AudioState, add_noise: bool = True
    ) -> tuple[np.ndarray, EQState]:
        """
        Select EQ adjustment action.

        Args:
            audio_state: Current ontology state
            add_noise: Add exploration noise

        Returns:
            action: Action vector
            new_eq_state: New EQ settings after action
        """
        # Construct state
        ontology_vector = audio_state.to_vector()
        eq_vector = self.current_eq.to_vector()
        state = np.concatenate([ontology_vector, eq_vector])

        # Get action from policy
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        self.actor.eval()
        with torch.no_grad():
            action = self.actor(state_tensor).cpu().numpy()[0]

        # Add exploration noise
        if add_noise:
            noise = np.random.normal(0, self.exploration_noise, size=action.shape)
            action = np.clip(action + noise, -1, 1)

        # Convert action to EQ adjustments
        # Action is delta to current EQ settings
        current_vector = self.current_eq.to_vector()
        new_vector = np.clip(current_vector + action * 0.1, -1, 1)  # Small adjustments
        new_eq_state = EQState.from_vector(new_vector, self.num_bands)

        return action, new_eq_state

    def train_step(self, batch_size: int = 256) -> dict | None:
        """
        Perform one training step using replay buffer.

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
        state_vector = np.concatenate([state.to_vector(), self.current_eq.to_vector()])
        next_state_vector = np.concatenate([next_state.to_vector(), self.current_eq.to_vector()])

        self.replay_buffer.add(state_vector, action, reward, next_state_vector, done)

    def process_audio(
        self, audio: np.ndarray, audio_state: AudioState
    ) -> tuple[np.ndarray, AgentAction]:
        """
        Process audio with EQ.

        Args:
            audio: Input audio
            audio_state: Current ontology state

        Returns:
            processed_audio: Output audio
            action: Action taken
        """
        # Select action
        action_vector, new_eq_state = self.select_action(audio_state, add_noise=True)

        # Apply EQ
        processed_audio = self.apply_eq(audio, new_eq_state)

        # Update current EQ
        self.current_eq = new_eq_state

        # Create action object
        action = AgentAction(
            agent_id="eq_rl_agent",
            action_type="eq_adjustment",
            parameters={
                f"band_{i}_{param}": value
                for i, band in enumerate(new_eq_state.bands)
                for param, value in [
                    ("freq", band.frequency),
                    ("gain", band.gain),
                    ("q", band.q_factor),
                ]
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
        logger.info(f"Saved EQ RL model to {path}")

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
        logger.info(f"Loaded EQ RL model from {path}")


if __name__ == "__main__":
    # Example usage
    import ray

    ray.init(ignore_reinit_error=True)

    # Create EQ agent
    eq_agent = EQRLAgent.remote(num_bands=8)

    # Test with dummy audio
    dummy_audio = np.random.randn(44100)
    dummy_state = AudioState()
    dummy_state.set_attribute(AudioAttribute.CLARITY, 0.5)

    processed, action = ray.get(eq_agent.process_audio.remote(dummy_audio, dummy_state))
    print(f"Processed audio shape: {processed.shape}")
    print(f"Action: {action.action_type}")

    ray.shutdown()
