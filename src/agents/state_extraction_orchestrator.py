"""Orchestrator for multi-agent state extraction with event detection and specialized agents."""

from typing import Optional, List, Union, Any
import asyncio

from .event_detector import EventDetectorAgent, create_event_detector
from .hp_agent import HPAgent, create_hp_agent
from .resource_agent import ResourceAgent, create_resource_agent
from .effect_agent import EffectAgent, create_effect_agent
from .lifecycle_agent import LifecycleAgent, create_lifecycle_agent
from ..models.state_updates import (
    EventType, EventDetectionResult
)
from ..models.state_commands_optimized import (
    HPAgentResult, ResourceAgentResult, EffectAgentResult, StateAgentResult,
    StateCommand, StateCommandResult
)
from ..context.effect_agent_context_builder import EffectAgentContextBuilder, create_effect_agent_context_builder
from ..services.rules_cache_service import RulesCacheService, create_rules_cache_service


class StateExtractionOrchestrator:
    """
    Orchestrates multi-agent state extraction with event detection and specialized agents.

    Two-phase extraction:
    1. Event Detector identifies which types of changes occurred
    2. Specialized agents (HP/Effect/Resource/Lifecycle) run in parallel based on detected events
    3. Results are merged into unified StateExtractionResult

    Uses 4-agent architecture:
    - HPAgent: Handles HP_CHANGE events
    - EffectAgent: Handles EFFECT_APPLIED events
    - ResourceAgent: Handles RESOURCE_USAGE events
    - LifecycleAgent: Handles STATE_CHANGE events (death saves, rests)
    """

    def __init__(
        self,
        event_detector: EventDetectorAgent,
        hp_agent: HPAgent,
        effect_agent: EffectAgent,
        resource_agent: ResourceAgent,
        lifecycle_agent: LifecycleAgent,
        rules_cache_service: RulesCacheService,
        effect_agent_context_builder: EffectAgentContextBuilder
    ):
        """Initialize orchestrator with all required agents."""
        self.event_detector = event_detector
        self.hp_agent = hp_agent
        self.effect_agent = effect_agent
        self.resource_agent = resource_agent
        self.lifecycle_agent = lifecycle_agent
        self.rules_cache_service = rules_cache_service
        self.effect_agent_context_builder = effect_agent_context_builder

    async def extract_state_changes(
        self,
        formatted_turn_context: str,
        game_context: Optional[dict] = None,
        turn_snapshot: Optional[Any] = None  # NEW - snapshot with active_turns_by_level
    ) -> StateCommandResult:
        """
        Extract state changes using two-phase multi-agent approach.

        Args:
            formatted_turn_context: XML-formatted turn context with unprocessed messages (from state_extractor_context_builder)
            game_context: Optional game context (turn_id, character info, etc.)
            turn_snapshot: Optional snapshot from TurnManager (used by EffectAgent for cache merging)

        Returns:
            StateCommandResult with all extracted commands from specialized agents
        """
        try:
            # Phase 1: Detect which event types occurred
            events = await self.event_detector.detect_events(
                formatted_turn_context,
                game_context
            )

            # Phase 2: Build list of agents to run based on detected events
            tasks = []
            agent_types = []  # Track which agent produced which result

            # HP_CHANGE → HPAgent
            if EventType.HP_CHANGE in events.detected_events:
                tasks.append(self.hp_agent.extract(formatted_turn_context, game_context))
                agent_types.append("hp")

            # RESOURCE_USAGE → ResourceAgent
            if EventType.RESOURCE_USAGE in events.detected_events:
                tasks.append(self.resource_agent.extract(formatted_turn_context, game_context))
                agent_types.append("resource")

            # EFFECT_APPLIED → EffectAgent (with rules cache context)
            if EventType.EFFECT_APPLIED in events.detected_events and turn_snapshot:
                # Build context via EffectAgentContextBuilder (using snapshot)
                effect_context = self.effect_agent_context_builder.build_context(
                    narrative=formatted_turn_context,
                    active_turns_by_level=turn_snapshot.active_turns_by_level,
                    game_context=game_context
                )
                tasks.append(self.effect_agent.extract(effect_context))
                agent_types.append("effect")

            # STATE_CHANGE → LifecycleAgent
            if EventType.STATE_CHANGE in events.detected_events:
                tasks.append(self.lifecycle_agent.extract(formatted_turn_context, game_context))
                agent_types.append("lifecycle")

            # If no events detected, return empty result
            if not tasks:
                return StateCommandResult(
                    commands=[],
                    notes=f"No events detected. Confidence: {events.confidence}"
                )

            # Phase 3: Run all agent tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Phase 4: Merge results from all agents
            return self._merge_results(results, events, agent_types)

        except Exception as e:
            return StateCommandResult(
                commands=[],
                notes=f"Orchestration failed: {str(e)}"
            )

    def _merge_results(
        self,
        results: List[Union[HPAgentResult, ResourceAgentResult, EffectAgentResult, StateAgentResult, Exception]],
        events: EventDetectionResult,
        agent_types: List[str]
    ) -> StateCommandResult:
        """
        Merge specialized agent results into unified StateCommandResult.

        All agents return command-based results. This method simply collects
        all commands from all agents into a flat list.

        Handles exceptions gracefully - if one agent fails, others still contribute.
        """
        merged_commands: List[StateCommand] = []
        notes_parts = [f"Events: {[e.value for e in events.detected_events]}"]

        # Process each agent result
        for i, result in enumerate(results):
            agent_type = agent_types[i] if i < len(agent_types) else "unknown"

            # Handle exceptions
            if isinstance(result, Exception):
                notes_parts.append(f"{agent_type} failed: {str(result)}")
                continue

            # All agents return command-based results
            commands = result.commands

            # Add all commands to merged list
            merged_commands.extend(commands)
            notes_parts.append(f"{agent_type}: {len(commands)} commands")

        return StateCommandResult(
            commands=merged_commands,
            notes=" | ".join(notes_parts)
        )


def create_state_extraction_orchestrator(
    model_name: str,
    api_key: str,
    rules_cache_service: Optional[RulesCacheService] = None
) -> StateExtractionOrchestrator:
    """
    Factory function to create fully configured state extraction orchestrator.

    Creates all required agents and services using the 4-agent architecture:
    - EventDetector: Detects which event types occurred
    - HPAgent: Extracts HP changes (HP_CHANGE events)
    - EffectAgent: Extracts conditions/effects (EFFECT_APPLIED events) with LanceDB caching
    - ResourceAgent: Extracts spell slots/items/hit dice (RESOURCE_USAGE events)
    - LifecycleAgent: Extracts death saves/rests (STATE_CHANGE events)
    - RulesCacheService: Manages cached rule descriptions (shared across system)
    - EffectAgentContextBuilder: Builds effect extraction context with cached rules

    Args:
        model_name: Gemini model to use for all agents
        api_key: API key (required for guild-level BYOK)
        rules_cache_service: Optional shared RulesCacheService. If None, creates a new instance.
                            Share this service with DM tools to maintain consistent cache.

    Returns:
        StateExtractionOrchestrator with all agents initialized
    """
    # Create or use shared RulesCacheService
    if rules_cache_service is None:
        rules_cache_service = create_rules_cache_service()

    # Create context builder with the cache service
    effect_agent_context_builder = create_effect_agent_context_builder(rules_cache_service)

    return StateExtractionOrchestrator(
        event_detector=create_event_detector(model_name, api_key),
        hp_agent=create_hp_agent(model_name, api_key),
        effect_agent=create_effect_agent(model_name, api_key),
        resource_agent=create_resource_agent(model_name, api_key),
        lifecycle_agent=create_lifecycle_agent(model_name, api_key),
        rules_cache_service=rules_cache_service,
        effect_agent_context_builder=effect_agent_context_builder
    )
