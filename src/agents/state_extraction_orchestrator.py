"""Orchestrator for multi-agent state extraction with event detection and specialized extractors."""

from typing import Optional, List, Union
import asyncio

from .event_detector import EventDetectorAgent, create_event_detector
from .combat_state_extractor import CombatStateExtractor, create_combat_state_extractor
from .resource_extractor import ResourceExtractor, create_resource_extractor
from ..models.state_updates import (
    StateExtractionResult, EventType, EventDetectionResult,
    CombatStateResult, ResourceResult, CharacterUpdate,
    CombatCharacterUpdate, ResourceCharacterUpdate
)


class StateExtractionOrchestrator:
    """
    Orchestrates multi-agent state extraction with event detection and specialized extractors.

    Two-phase extraction:
    1. Event Detector identifies which types of changes occurred
    2. Specialized extractors (Combat/Resource) run in parallel based on detected events
    3. Results are merged into unified StateExtractionResult
    """

    def __init__(
        self,
        event_detector: EventDetectorAgent,
        combat_extractor: CombatStateExtractor,
        resource_extractor: ResourceExtractor
    ):
        """Initialize orchestrator with all required agents."""
        self.event_detector = event_detector
        self.combat_extractor = combat_extractor
        self.resource_extractor = resource_extractor

    async def extract_state_changes(
        self,
        formatted_turn_context: str, 
        game_context: Optional[dict] = None
    ) -> StateExtractionResult:
        """
        Extract state changes using two-phase multi-agent approach.

        Args:
            formatted_turn_context: XML-formatted turn context with unprocessed messages (from state_extractor_context_builder)
            game_context: Optional game context (turn_id, character info, etc.)

        Returns:
            Unified StateExtractionResult with all extracted changes
        """
        try:
            # Phase 1: Detect which event types occurred
            events = await self.event_detector.detect_events(
                formatted_turn_context,
                game_context
            )

            # Phase 2: Build list of extractors to run based on detected events
            tasks = []
            extractor_types = []

            if EventType.COMBAT_STATE_CHANGE in events.detected_events:
                tasks.append(self.combat_extractor.extract(formatted_turn_context, game_context))
                extractor_types.append("combat")

            if EventType.RESOURCE_USAGE in events.detected_events:
                tasks.append(self.resource_extractor.extract(formatted_turn_context, game_context))
                extractor_types.append("resource")

            # If no events detected, return empty result
            if not tasks:
                return StateExtractionResult(
                    character_updates=[],
                    new_characters=[],
                    combat_info={},
                    notes=f"No events detected. Confidence: {events.confidence}"
                )

            # Phase 3: Run extractors in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Phase 4: Merge results
            return self._merge_results(results, events, extractor_types)

        except Exception as e:
            return StateExtractionResult(
                character_updates=[],
                new_characters=[],
                combat_info={},
                notes=f"Orchestration failed: {str(e)}"
            )

    def _merge_results(
        self,
        results: List[Union[CombatStateResult, ResourceResult, Exception]],
        events: EventDetectionResult,
        extractor_types: List[str]
    ) -> StateExtractionResult:
        """
        Merge specialized extractor results into unified StateExtractionResult.

        Converts CombatCharacterUpdate and ResourceCharacterUpdate to full CharacterUpdate.
        Handles exceptions gracefully - if one extractor fails, others still contribute.
        """
        merged_character_updates = []
        merged_new_characters = []
        merged_combat_info = {}
        notes_parts = [f"Events detected: {', '.join([e.value for e in events.detected_events])}"]

        # Process each result
        for i, result in enumerate(results):
            extractor_type = extractor_types[i] if i < len(extractor_types) else "unknown"

            if isinstance(result, Exception):
                notes_parts.append(f"{extractor_type} extractor failed: {str(result)}")
                continue

            if isinstance(result, CombatStateResult):
                # Convert CombatCharacterUpdate to CharacterUpdate
                for combat_update in result.character_updates:
                    merged_character_updates.append(combat_update.to_character_update())
                if result.combat_info:
                    merged_combat_info.update(result.combat_info)
                if result.notes:
                    notes_parts.append(f"Combat: {result.notes}")

            elif isinstance(result, ResourceResult):
                # Convert ResourceCharacterUpdate to CharacterUpdate
                for resource_update in result.character_updates:
                    merged_character_updates.append(resource_update.to_character_update())
                merged_new_characters.extend(result.new_characters)
                if result.notes:
                    notes_parts.append(f"Resource: {result.notes}")

        # Deduplicate character updates by character_id (merge updates for same character)
        deduplicated_updates = self._deduplicate_character_updates(merged_character_updates)

        return StateExtractionResult(
            character_updates=deduplicated_updates,
            new_characters=merged_new_characters,
            combat_info=merged_combat_info,
            notes=" | ".join(notes_parts)
        )

    def _deduplicate_character_updates(
        self,
        updates: List[CharacterUpdate]
    ) -> List[CharacterUpdate]:
        """
        Deduplicate character updates by merging updates for the same character.

        If both combat and resource extractors update the same character,
        merge their updates into a single CharacterUpdate.
        """
        updates_by_char = {}

        for update in updates:
            char_id = update.character_id

            if char_id not in updates_by_char:
                updates_by_char[char_id] = update
            else:
                # Merge updates for this character
                existing: CharacterUpdate = updates_by_char[char_id]

                # Merge each update type (keep non-None values)
                if update.hp_update:
                    existing.hp_update = update.hp_update
                if update.condition_update:
                    existing.condition_update = update.condition_update
                if update.spell_slot_update:
                    existing.spell_slot_update = update.spell_slot_update
                if update.death_save_update:
                    existing.death_save_update = update.death_save_update
                if update.inventory_update:
                    existing.inventory_update = update.inventory_update
                if update.ability_update:
                    existing.ability_update = update.ability_update
                if update.hit_dice_update:
                    existing.hit_dice_update = update.hit_dice_update
                if update.combat_stat_update:
                    existing.combat_stat_update = update.combat_stat_update

        return list(updates_by_char.values())


def create_state_extraction_orchestrator(
    model_name: str = "gemini-2.5-flash-lite"
) -> StateExtractionOrchestrator:
    """
    Factory function to create fully configured state extraction orchestrator.

    Args:
        model_name: Gemini model to use for all agents

    Returns:
        StateExtractionOrchestrator with all agents initialized
    """
    return StateExtractionOrchestrator(
        event_detector=create_event_detector(model_name),
        combat_extractor=create_combat_state_extractor(model_name),
        resource_extractor=create_resource_extractor(model_name)
    )
