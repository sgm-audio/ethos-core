"""
Critic Agent for Multi-Agent Audio Processing System (MAAPS)

The Critic is the evaluator that judges audio quality based on the ontology.
It predicts user satisfaction and provides reward signals for RL agents.

This is the FIRST agent to build - before the EQ and Dynamics agents can learn,
they need feedback from the Critic.
"""

import logging
from dataclasses import dataclass

import librosa
import numpy as np
import ray
import torch
import torch.nn as nn
import torch.optim as optim

from ethos.core.audio_ontology import AudioAttribute, AudioGoal, AudioOntologyManager, AudioState

logger = logging.getLogger(__name__)


@dataclass
class CriticEvaluation:
    """Result of critic evaluation."""

    satisfaction_score: float  # Overall score 0-1
    attribute_scores: dict[AudioAttribute, float]  # Individual attribute scores
    reward: float  # RL reward signal (-1 to 1)
    confidence: float  # Confidence in evaluation
    feedback: str  # Human-readable feedback


class CriticNetwork(nn.Module):
    """
    Neural network for audio quality evaluation.
    Takes audio features + ontology state -> satisfaction prediction.
    """

    def __init__(
        self,
        audio_feature_dim: int = 128,
        ontology_dim: int = 20,
        hidden_dim: int = 256,
        num_layers: int = 3,
    ):
        super().__init__()

        self.audio_feature_dim = audio_feature_dim
        self.ontology_dim = ontology_dim

        # Audio feature encoder
        self.audio_encoder = nn.Sequential(
            nn.Linear(audio_feature_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
        )

        # Ontology state encoder
        self.ontology_encoder = nn.Sequential(
            nn.Linear(ontology_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim // 2, hidden_dim // 4),
            nn.ReLU(),
        )

        # Combined evaluation network
        combined_dim = (hidden_dim // 2) + (hidden_dim // 4)
        self.evaluator = nn.Sequential(
            nn.Linear(combined_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid(),  # Output 0-1 satisfaction score
        )

        # Attribute-specific heads (optional, for detailed feedback)
        self.attribute_heads = nn.ModuleDict(
            {
                attr.name: nn.Sequential(
                    nn.Linear(combined_dim, 64), nn.ReLU(), nn.Linear(64, 1), nn.Sigmoid()
                )
                for attr in AudioAttribute
            }
        )

    def forward(
        self, audio_features: torch.Tensor, ontology_state: torch.Tensor
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """
        Forward pass.

        Args:
            audio_features: (batch, audio_feature_dim)
            ontology_state: (batch, ontology_dim)

        Returns:
            satisfaction_score: (batch, 1)
            attribute_scores: Dict of (batch, 1) for each attribute
        """
        # Encode audio features
        audio_encoded = self.audio_encoder(audio_features)

        # Encode ontology state
        ontology_encoded = self.ontology_encoder(ontology_state)

        # Combine
        combined = torch.cat([audio_encoded, ontology_encoded], dim=-1)

        # Overall satisfaction
        satisfaction = self.evaluator(combined)

        # Attribute-specific scores
        attribute_scores = {name: head(combined) for name, head in self.attribute_heads.items()}

        return satisfaction, attribute_scores


@ray.remote
class CriticAgent:
    """
    Ray actor for the Critic agent.
    Evaluates audio quality and provides rewards for RL training.
    """

    def __init__(
        self,
        model_path: str | None = None,
        device: str = "cpu",
        learning_rate: float = 1e-4,
        ontology: AudioOntologyManager | None = None,
    ):
        """
        Initialize Critic agent.

        Args:
            model_path: Path to pre-trained model (None to train from scratch)
            device: "cpu" or "cuda"
            learning_rate: Learning rate for training
            ontology: Ontology manager
        """
        self.device = torch.device(device)
        self.ontology = ontology or AudioOntologyManager()

        # Initialize network
        self.model = CriticNetwork().to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        self.criterion = nn.MSELoss()

        # Load pre-trained model if provided
        if model_path:
            self.load_model(model_path)

        # Training history
        self.training_history = []

        logger.info("Critic agent initialized")

    def extract_audio_features(self, audio: np.ndarray, sr: int = 44100) -> np.ndarray:
        """
        Extract audio features for the critic network.

        Args:
            audio: Audio signal (mono, normalized)
            sr: Sample rate

        Returns:
            Feature vector (128-dim)
        """
        # Extract spectral features
        spectral_centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr)[0]
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=audio, sr=sr)[0]
        zero_crossing_rate = librosa.feature.zero_crossing_rate(audio)[0]

        # Extract MFCCs
        mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=20)

        # Extract chroma
        chroma = librosa.feature.chroma_stft(y=audio, sr=sr)

        # Extract RMS energy
        rms = librosa.feature.rms(y=audio)[0]

        # Aggregate features
        features = np.concatenate(
            [
                np.mean(spectral_centroid, keepdims=True),
                np.std(spectral_centroid, keepdims=True),
                np.mean(spectral_rolloff, keepdims=True),
                np.std(spectral_rolloff, keepdims=True),
                np.mean(spectral_bandwidth, keepdims=True),
                np.std(spectral_bandwidth, keepdims=True),
                np.mean(zero_crossing_rate, keepdims=True),
                np.std(zero_crossing_rate, keepdims=True),
                np.mean(mfccs, axis=1),  # 20 dims
                np.std(mfccs, axis=1),  # 20 dims
                np.mean(chroma, axis=1),  # 12 dims
                np.std(chroma, axis=1),  # 12 dims
                np.mean(rms, keepdims=True),
                np.std(rms, keepdims=True),
            ]
        )

        # Pad to 128 dims if needed
        if len(features) < 128:
            features = np.pad(features, (0, 128 - len(features)), mode="constant")
        else:
            features = features[:128]

        return features

    def evaluate(
        self, audio: np.ndarray, current_state: AudioState, goals: list[AudioGoal], sr: int = 44100
    ) -> CriticEvaluation:
        """
        Evaluate audio quality.

        Args:
            audio: Audio signal
            current_state: Current ontology state
            goals: Target goals
            sr: Sample rate

        Returns:
            CriticEvaluation with scores and reward
        """
        # Extract features
        audio_features = self.extract_audio_features(audio, sr)
        ontology_vector = current_state.to_vector()

        # Prepare tensors
        audio_tensor = torch.FloatTensor(audio_features).unsqueeze(0).to(self.device)
        ontology_tensor = torch.FloatTensor(ontology_vector).unsqueeze(0).to(self.device)

        # Get prediction
        self.model.eval()
        with torch.no_grad():
            satisfaction_pred, attribute_preds = self.model(audio_tensor, ontology_tensor)

        satisfaction_score = satisfaction_pred.item()

        # Convert attribute predictions
        attribute_scores = {
            AudioAttribute[name]: pred.item() for name, pred in attribute_preds.items()
        }

        # Calculate reward signal for RL
        # Reward is based on satisfaction improvement and goal achievement
        goal_satisfaction = self.ontology.estimate_satisfaction_score(current_state, goals)
        reward = (satisfaction_score + goal_satisfaction) / 2.0
        reward = (reward - 0.5) * 2.0  # Scale to [-1, 1]

        # Generate feedback
        feedback = self._generate_feedback(satisfaction_score, attribute_scores, goals)

        return CriticEvaluation(
            satisfaction_score=satisfaction_score,
            attribute_scores=attribute_scores,
            reward=reward,
            confidence=0.8,  # TODO: Implement confidence estimation
            feedback=feedback,
        )

    def _generate_feedback(
        self,
        satisfaction: float,
        attribute_scores: dict[AudioAttribute, float],
        goals: list[AudioGoal],
    ) -> str:
        """Generate human-readable feedback."""
        feedback_parts = [f"Satisfaction: {satisfaction:.2f}"]

        # Find areas needing improvement
        issues = []
        for goal in goals:
            attr_score = attribute_scores.get(goal.attribute, 0.5)
            if abs(attr_score - goal.target_value) > goal.tolerance:
                if attr_score < goal.target_value:
                    issues.append(f"Need more {goal.attribute.name}")
                else:
                    issues.append(f"Too much {goal.attribute.name}")

        if issues:
            feedback_parts.append("Issues: " + ", ".join(issues))

        return " | ".join(feedback_parts)

    def train_step(
        self,
        audio_batch: list[np.ndarray],
        ontology_batch: list[AudioState],
        satisfaction_labels: list[float],
        sr: int = 44100,
    ) -> float:
        """
        Perform one training step.

        Args:
            audio_batch: List of audio samples
            ontology_batch: List of ontology states
            satisfaction_labels: Ground truth satisfaction scores (from user feedback)
            sr: Sample rate

        Returns:
            Loss value
        """
        # Extract features
        audio_features = np.stack([self.extract_audio_features(audio, sr) for audio in audio_batch])
        ontology_vectors = np.stack([state.to_vector() for state in ontology_batch])

        # Prepare tensors
        audio_tensor = torch.FloatTensor(audio_features).to(self.device)
        ontology_tensor = torch.FloatTensor(ontology_vectors).to(self.device)
        labels = torch.FloatTensor(satisfaction_labels).unsqueeze(-1).to(self.device)

        # Forward pass
        self.model.train()
        satisfaction_pred, _ = self.model(audio_tensor, ontology_tensor)

        # Compute loss
        loss = self.criterion(satisfaction_pred, labels)

        # Backward pass
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        loss_value = loss.item()
        self.training_history.append(loss_value)

        return loss_value

    def save_model(self, path: str):
        """Save model checkpoint."""
        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "training_history": self.training_history,
            },
            path,
        )
        logger.info(f"Saved critic model to {path}")

    def load_model(self, path: str):
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.device, weights_only=True)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.training_history = checkpoint.get("training_history", [])
        logger.info(f"Loaded critic model from {path}")

    def get_training_stats(self) -> dict:
        """Get training statistics."""
        if not self.training_history:
            return {"error": "No training history"}

        return {
            "total_steps": len(self.training_history),
            "latest_loss": self.training_history[-1],
            "average_loss_last_100": np.mean(self.training_history[-100:]),
            "min_loss": min(self.training_history),
        }


def create_critic_agent(**kwargs) -> ray.ObjectRef:
    """Convenience function to create a Critic agent."""
    return CriticAgent.remote(**kwargs)


if __name__ == "__main__":
    # Example usage
    import ray

    from ..core.audio_ontology import create_clarity_goal, create_reduce_mud_goal

    ray.init(ignore_reinit_error=True)

    # Create critic agent
    critic = CriticAgent.remote()

    # Generate dummy audio
    dummy_audio = np.random.randn(44100 * 2)  # 2 seconds
    dummy_state = AudioState()
    dummy_state.set_attribute(AudioAttribute.CLARITY, 0.5)
    dummy_goals = [create_clarity_goal(), create_reduce_mud_goal()]

    # Evaluate
    evaluation = ray.get(critic.evaluate.remote(dummy_audio, dummy_state, dummy_goals))

    print("Evaluation:", evaluation)

    ray.shutdown()
