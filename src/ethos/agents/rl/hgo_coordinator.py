"""
Hierarchical Goal Optimization (HGO) Coordinator for MAAPS

The HGO Coordinator mediates between competing agents (EQ and Dynamics).
When agents conflict (both trying to optimize but pulling in different directions),
the coordinator determines priorities, sequencing, and compromise solutions.

This implements the "now they fight" phase - the coordinator prevents chaos.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import ray

from ethos.core.audio_ontology import (
    AgentAction,
    AudioAttribute,
    AudioGoal,
    AudioOntologyManager,
    AudioState,
)

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of conflicts between agents."""

    NO_CONFLICT = 0
    PARAMETER_CONFLICT = 1  # Both agents affecting same audio aspect
    GOAL_CONFLICT = 2  # Agents pursuing incompatible goals
    RESOURCE_CONFLICT = 3  # Both agents needing same computational resources
    TEMPORAL_CONFLICT = 4  # Order dependency issues


@dataclass
class AgentProposal:
    """Proposal from an agent to take action."""

    agent_id: str
    action: AgentAction
    predicted_impact: dict[AudioAttribute, float]
    predicted_satisfaction: float
    confidence: float
    priority: float = 0.5


@dataclass
class CoordinationDecision:
    """Decision from the coordinator."""

    approved_proposals: list[AgentProposal]
    rejected_proposals: list[AgentProposal]
    execution_order: list[str]  # Agent IDs in execution order
    compromise_adjustments: dict[str, dict[str, float]]  # agent_id -> param adjustments
    reasoning: str


@dataclass
class ConflictReport:
    """Report of conflict between agents."""

    conflict_type: ConflictType
    involved_agents: list[str]
    conflicting_attributes: list[AudioAttribute]
    severity: float  # 0.0 to 1.0
    description: str


@ray.remote
class HGOCoordinator:
    """
    Hierarchical Goal Optimization Coordinator.

    Responsibilities:
    1. Receive proposals from multiple agents
    2. Detect conflicts between proposals
    3. Resolve conflicts using goal hierarchy and ontology
    4. Determine execution order
    5. Provide compromise solutions when needed
    6. Monitor overall system satisfaction
    """

    def __init__(
        self,
        goal_hierarchy: list[AudioGoal] | None = None,
        conflict_threshold: float = 0.3,
        compromise_weight: float = 0.5,
        ontology: AudioOntologyManager | None = None,
    ):
        """
        Initialize HGO Coordinator.

        Args:
            goal_hierarchy: Ordered list of goals (highest priority first)
            conflict_threshold: Threshold for detecting conflicts
            compromise_weight: Weight for compromise solutions (0=first agent, 1=second agent)
            ontology: Ontology manager
        """
        self.goal_hierarchy = goal_hierarchy or []
        self.conflict_threshold = conflict_threshold
        self.compromise_weight = compromise_weight
        self.ontology = ontology or AudioOntologyManager()

        # Coordination history
        self.coordination_history = []
        self.conflict_history = []

        # Agent registry
        self.registered_agents = {}

        logger.info("HGO Coordinator initialized")

    def register_agent(self, agent_id: str, agent_ref: Any, priority: float = 0.5):
        """
        Register an agent with the coordinator.

        Args:
            agent_id: Unique agent identifier
            agent_ref: Ray actor reference
            priority: Default priority (0-1)
        """
        self.registered_agents[agent_id] = {
            "ref": agent_ref,
            "priority": priority,
            "action_count": 0,
            "success_rate": 0.5,
        }
        logger.info(f"Registered agent: {agent_id}")

    def detect_conflicts(
        self, proposals: list[AgentProposal], current_state: AudioState
    ) -> list[ConflictReport]:
        """
        Detect conflicts between agent proposals.

        Args:
            proposals: List of agent proposals
            current_state: Current audio state

        Returns:
            List of conflict reports
        """
        conflicts = []

        # Compare all pairs of proposals
        for i, prop1 in enumerate(proposals):
            for prop2 in proposals[i + 1 :]:
                conflict = self._check_proposal_conflict(prop1, prop2, current_state)
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    def _check_proposal_conflict(
        self, prop1: AgentProposal, prop2: AgentProposal, current_state: AudioState
    ) -> ConflictReport | None:
        """
        Check if two proposals conflict.

        Args:
            prop1, prop2: Proposals to check
            current_state: Current state

        Returns:
            ConflictReport if conflict detected, None otherwise
        """
        # Check for conflicting attribute impacts
        conflicting_attrs = []
        total_conflict = 0.0

        for attr in AudioAttribute:
            impact1 = prop1.predicted_impact.get(attr, 0.0)
            impact2 = prop2.predicted_impact.get(attr, 0.0)

            # Conflict if impacts have opposite signs and are significant
            if (
                abs(impact1) > 0.1 and abs(impact2) > 0.1 and impact1 * impact2 < 0
            ):  # Opposite signs
                conflicting_attrs.append(attr)
                total_conflict += abs(impact1) + abs(impact2)

        if not conflicting_attrs:
            return None

        # Determine conflict type and severity
        severity = min(total_conflict / len(conflicting_attrs), 1.0)

        if severity < self.conflict_threshold:
            return None

        # Determine conflict type
        if any(
            attr in [AudioAttribute.CLARITY, AudioAttribute.WARMTH] for attr in conflicting_attrs
        ):
            conflict_type = ConflictType.GOAL_CONFLICT
        else:
            conflict_type = ConflictType.PARAMETER_CONFLICT

        return ConflictReport(
            conflict_type=conflict_type,
            involved_agents=[prop1.agent_id, prop2.agent_id],
            conflicting_attributes=conflicting_attrs,
            severity=severity,
            description=f"Conflict between {prop1.agent_id} and {prop2.agent_id} on {len(conflicting_attrs)} attributes",
        )

    def resolve_conflicts(
        self,
        proposals: list[AgentProposal],
        conflicts: list[ConflictReport],
        current_state: AudioState,
    ) -> CoordinationDecision:
        """
        Resolve conflicts and make coordination decision.

        Args:
            proposals: All agent proposals
            conflicts: Detected conflicts
            current_state: Current state

        Returns:
            CoordinationDecision
        """
        if not conflicts:
            # No conflicts, approve all proposals
            return CoordinationDecision(
                approved_proposals=proposals,
                rejected_proposals=[],
                execution_order=[p.agent_id for p in proposals],
                compromise_adjustments={},
                reasoning="No conflicts detected, all proposals approved",
            )

        # Strategy 1: Goal hierarchy priority
        # Prioritize proposals that align with higher-priority goals
        proposal_scores = []
        for proposal in proposals:
            score = self._score_proposal_against_goals(proposal, current_state)
            proposal_scores.append((score, proposal))

        proposal_scores.sort(key=lambda x: x[0], reverse=True)

        # Strategy 2: Conflict resolution
        approved = []
        rejected = []
        compromise_adjustments = {}

        for _score, proposal in proposal_scores:
            # Check if this proposal conflicts with already approved proposals
            has_conflict = False
            for conflict in conflicts:
                if proposal.agent_id in conflict.involved_agents:
                    # Check if other involved agent is already approved
                    other_agents = [a for a in conflict.involved_agents if a != proposal.agent_id]
                    if any(a in [p.agent_id for p in approved] for a in other_agents):
                        has_conflict = True

                        # Try compromise
                        if conflict.severity < 0.7:  # Medium severity, try compromise
                            adjustment = self._calculate_compromise(
                                proposal, conflict, current_state
                            )
                            compromise_adjustments[proposal.agent_id] = adjustment
                            approved.append(proposal)
                            has_conflict = False
                        break

            if has_conflict:
                rejected.append(proposal)
            elif proposal not in approved:
                approved.append(proposal)

        # Strategy 3: Determine execution order
        # Order based on attribute dependencies
        execution_order = self._determine_execution_order(approved, current_state)

        # Generate reasoning
        reasoning = self._generate_reasoning(approved, rejected, conflicts, compromise_adjustments)

        decision = CoordinationDecision(
            approved_proposals=approved,
            rejected_proposals=rejected,
            execution_order=execution_order,
            compromise_adjustments=compromise_adjustments,
            reasoning=reasoning,
        )

        self.coordination_history.append(decision)
        return decision

    def _score_proposal_against_goals(
        self, proposal: AgentProposal, current_state: AudioState
    ) -> float:
        """
        Score a proposal based on alignment with goal hierarchy.

        Args:
            proposal: Agent proposal
            current_state: Current state

        Returns:
            Score (higher is better)
        """
        if not self.goal_hierarchy:
            return proposal.predicted_satisfaction

        total_score = 0.0
        total_weight = 0.0

        for goal in self.goal_hierarchy:
            # Get predicted impact on this goal's attribute
            impact = proposal.predicted_impact.get(goal.attribute, 0.0)

            # Calculate current distance from goal
            current_value = current_state.get_attribute(goal.attribute)
            goal.distance_from_target(current_value)

            # Positive score if impact moves toward goal
            if current_value < goal.target_value:
                score = impact if impact > 0 else -abs(impact)
            else:
                score = impact if impact < 0 else -abs(impact)

            # Weight by goal priority
            weighted_score = score * goal.priority
            total_score += weighted_score
            total_weight += goal.priority

        # Normalize
        if total_weight > 0:
            return total_score / total_weight
        return 0.0

    def _calculate_compromise(
        self, proposal: AgentProposal, conflict: ConflictReport, current_state: AudioState
    ) -> dict[str, float]:
        """
        Calculate compromise adjustments for a proposal.

        Args:
            proposal: Conflicting proposal
            conflict: Conflict report
            current_state: Current state

        Returns:
            Parameter adjustments (scaling factors)
        """
        # Simple compromise: scale down the proposal
        adjustment_factor = 1.0 - (conflict.severity * self.compromise_weight)

        adjustments = dict.fromkeys(proposal.action.parameters.keys(), adjustment_factor)

        return adjustments

    def _determine_execution_order(
        self, approved_proposals: list[AgentProposal], current_state: AudioState
    ) -> list[str]:
        """
        Determine optimal execution order for approved proposals.

        Args:
            approved_proposals: List of approved proposals
            current_state: Current state

        Returns:
            List of agent IDs in execution order
        """
        if len(approved_proposals) <= 1:
            return [p.agent_id for p in approved_proposals]

        # Heuristic: EQ before dynamics, as dynamics often depends on frequency content
        order = []
        for proposal in approved_proposals:
            if "eq" in proposal.agent_id.lower():
                order.insert(0, proposal.agent_id)
            else:
                order.append(proposal.agent_id)

        return order

    def _generate_reasoning(
        self,
        approved: list[AgentProposal],
        rejected: list[AgentProposal],
        conflicts: list[ConflictReport],
        compromises: dict[str, dict[str, float]],
    ) -> str:
        """Generate human-readable reasoning for the decision."""
        parts = []

        parts.append(f"Approved {len(approved)} proposals, rejected {len(rejected)}")

        if conflicts:
            parts.append(f"Resolved {len(conflicts)} conflicts")

        if compromises:
            parts.append(f"Applied compromises to {len(compromises)} agents")

        if rejected:
            rejected_ids = [p.agent_id for p in rejected]
            parts.append(f"Rejected: {', '.join(rejected_ids)}")

        return " | ".join(parts)

    async def coordinate(
        self, proposals: list[AgentProposal], current_state: AudioState
    ) -> CoordinationDecision:
        """
        Main coordination method.

        Args:
            proposals: Agent proposals
            current_state: Current audio state

        Returns:
            CoordinationDecision
        """
        # Detect conflicts
        conflicts = self.detect_conflicts(proposals, current_state)

        if conflicts:
            logger.info(f"Detected {len(conflicts)} conflicts")
            for conflict in conflicts:
                logger.debug(f"Conflict: {conflict.description}")
                self.conflict_history.append(conflict)

        # Resolve conflicts
        decision = self.resolve_conflicts(proposals, conflicts, current_state)

        logger.info(f"Coordination decision: {decision.reasoning}")

        return decision

    def set_goal_hierarchy(self, goals: list[AudioGoal]):
        """Update goal hierarchy."""
        self.goal_hierarchy = sorted(goals, key=lambda g: g.priority, reverse=True)
        logger.info(f"Updated goal hierarchy with {len(goals)} goals")

    def get_statistics(self) -> dict:
        """Get coordination statistics."""
        return {
            "total_coordinations": len(self.coordination_history),
            "total_conflicts": len(self.conflict_history),
            "registered_agents": len(self.registered_agents),
            "conflict_rate": len(self.conflict_history) / max(len(self.coordination_history), 1),
        }

    def get_agent_performance(self, agent_id: str) -> dict:
        """Get performance stats for an agent."""
        if agent_id not in self.registered_agents:
            return {"error": "Agent not registered"}

        agent_info = self.registered_agents[agent_id]
        return {
            "agent_id": agent_id,
            "priority": agent_info["priority"],
            "action_count": agent_info["action_count"],
            "success_rate": agent_info["success_rate"],
        }


def create_hgo_coordinator(goals: list[AudioGoal] | None = None, **kwargs) -> ray.ObjectRef:
    """Convenience function to create HGO coordinator."""
    coordinator = HGOCoordinator.remote(goal_hierarchy=goals, **kwargs)
    return coordinator


if __name__ == "__main__":
    # Example usage
    import ray

    from ..core.audio_ontology import create_clarity_goal, create_warmth_goal

    ray.init(ignore_reinit_error=True)

    # Create coordinator
    goals = [
        create_clarity_goal(target=0.8, priority=1.0),
        create_warmth_goal(target=0.7, priority=0.8),
    ]

    coordinator = HGOCoordinator.remote(goal_hierarchy=goals)

    # Register agents
    ray.get(coordinator.register_agent.remote("eq_agent", None, priority=0.8))
    ray.get(coordinator.register_agent.remote("dynamics_agent", None, priority=0.7))

    # Create dummy proposals
    prop1 = AgentProposal(
        agent_id="eq_agent",
        action=AgentAction(agent_id="eq_agent", action_type="eq", parameters={}),
        predicted_impact={AudioAttribute.CLARITY: 0.2},
        predicted_satisfaction=0.7,
        confidence=0.8,
    )

    prop2 = AgentProposal(
        agent_id="dynamics_agent",
        action=AgentAction(agent_id="dynamics_agent", action_type="comp", parameters={}),
        predicted_impact={AudioAttribute.CLARITY: -0.1, AudioAttribute.PUNCH: 0.3},
        predicted_satisfaction=0.75,
        confidence=0.85,
    )

    # Coordinate
    current_state = AudioState()
    current_state.set_attribute(AudioAttribute.CLARITY, 0.5)

    decision = ray.get(coordinator.coordinate.remote([prop1, prop2], current_state))
    print("Decision:", decision.reasoning)
    print("Approved:", [p.agent_id for p in decision.approved_proposals])
    print("Execution order:", decision.execution_order)

    # Get stats
    stats = ray.get(coordinator.get_statistics.remote())
    print("Stats:", stats)

    ray.shutdown()
