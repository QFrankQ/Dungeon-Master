"""
Session configuration model for multiplayer coordination.

Defines per-server/session configuration options including timeouts,
reminder settings, and batching behavior.
"""

from typing import Optional
from pydantic import BaseModel, Field

from src.models.response_expectation import ResponseType


class SessionConfig(BaseModel):
    """
    Per-server/session configuration for multiplayer coordination.

    Attributes:
        action_timeout_seconds: Timeout for normal action turns
        initiative_timeout_seconds: Timeout for initiative rolls
        save_timeout_seconds: Timeout for saving throws
        reaction_timeout_seconds: Timeout for reaction opportunities
        reminder_at_percent: When to send reminder (0.5 = at 50% time remaining)
        batch_delay_seconds: Buffer time for rapid-fire responses
        auto_roll_on_timeout: Whether to auto-roll for players who timeout
    """

    action_timeout_seconds: int = Field(
        default=300,
        description="Timeout for normal action turns (5 minutes default)"
    )

    initiative_timeout_seconds: int = Field(
        default=120,
        description="Timeout for initiative rolls (2 minutes default)"
    )

    save_timeout_seconds: int = Field(
        default=60,
        description="Timeout for saving throws (1 minute default)"
    )

    reaction_timeout_seconds: int = Field(
        default=30,
        description="Timeout for reaction opportunities (30 seconds default)"
    )

    reminder_at_percent: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="When to send reminder (0.5 = at 50% time remaining)"
    )

    batch_delay_seconds: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Buffer time for rapid-fire responses before processing"
    )

    auto_roll_on_timeout: bool = Field(
        default=True,
        description="Whether to auto-roll for players who timeout"
    )

    def get_timeout(self, response_type: ResponseType) -> Optional[int]:
        """
        Get timeout for a specific response type.

        Args:
            response_type: The type of response expected

        Returns:
            Timeout in seconds, or None if no timeout applies
        """
        timeout_map = {
            ResponseType.ACTION: self.action_timeout_seconds,
            ResponseType.INITIATIVE: self.initiative_timeout_seconds,
            ResponseType.SAVING_THROW: self.save_timeout_seconds,
            ResponseType.REACTION: self.reaction_timeout_seconds,
            ResponseType.FREE_FORM: None,  # No timeout for exploration
            ResponseType.NONE: None,       # No timeout when narrating
        }
        return timeout_map.get(response_type)

    def get_reminder_time(self, response_type: ResponseType) -> Optional[int]:
        """
        Get when to send a reminder for a specific response type.

        Args:
            response_type: The type of response expected

        Returns:
            Time in seconds after which to send reminder, or None
        """
        timeout = self.get_timeout(response_type)
        if timeout is None:
            return None

        return int(timeout * self.reminder_at_percent)

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "examples": [
                {
                    "action_timeout_seconds": 300,
                    "initiative_timeout_seconds": 120,
                    "save_timeout_seconds": 60,
                    "reaction_timeout_seconds": 30,
                    "reminder_at_percent": 0.5,
                    "batch_delay_seconds": 0.5,
                    "auto_roll_on_timeout": True
                },
                {
                    "action_timeout_seconds": 600,
                    "initiative_timeout_seconds": 180,
                    "save_timeout_seconds": 90,
                    "reaction_timeout_seconds": 45,
                    "reminder_at_percent": 0.25,
                    "batch_delay_seconds": 1.0,
                    "auto_roll_on_timeout": False
                }
            ]
        }


def create_session_config(**kwargs) -> SessionConfig:
    """
    Factory function to create a SessionConfig with optional overrides.

    Args:
        **kwargs: Override any default configuration values

    Returns:
        A new SessionConfig instance
    """
    return SessionConfig(**kwargs)


# Default configuration instance
DEFAULT_SESSION_CONFIG = SessionConfig()
