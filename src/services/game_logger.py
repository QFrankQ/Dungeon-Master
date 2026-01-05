"""
Game Logger - Structured logging service for D&D game tracing.

Uses structlog for production-grade structured logging with:
- JSON output to files (JSONL format for streaming)
- Component-specific channels for filtering
- Session and turn context tracking
- Optional console output for debugging

Provides a simple, game-specific API on top of structlog.
"""

import os
import sys
from enum import Enum
from typing import Optional, Dict, Any, TextIO
from datetime import datetime
from pathlib import Path

import structlog
from structlog.typing import FilteringBoundLogger


class LogLevel(Enum):
    """Log severity levels (maps to stdlib logging levels)."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40


class LogChannel(str, Enum):
    """Component-specific logging channels."""
    DM_AGENT = "dm_agent"               # DM responses, narrative generation
    DM_TOOLS = "dm_tools"               # Tool invocations (rules query, spawn, initiative)
    STATE_EXTRACTION = "state_extraction"  # Event detection, command generation
    COMMAND_EXECUTION = "command_execution"  # Per-command state changes
    TURN_MANAGEMENT = "turn_management"  # Turn stack, message filtering
    COMBAT_CYCLE = "combat_cycle"       # Combat phases, initiative, turn order
    STEP_PROGRESSION = "step_progression"  # Step objectives, phase transitions
    DISCORD_UI = "discord_ui"           # Views, modals, buttons, embeds
    PLAYER_INPUT = "player_input"       # Messages, rolls, action declarations
    CONTEXT_BUILDING = "context_building"  # DM/extractor context assembly


def _level_to_name(level: LogLevel) -> str:
    """Convert LogLevel enum to string name."""
    return level.name.lower()


class GameLogger:
    """
    Centralized logging service for game tracing, backed by structlog.

    Features:
    - Component-specific channels for filtering
    - File output in JSONL format (default)
    - Optional console output for live debugging
    - Session and turn context tracking
    - Streaming writes (entries written immediately)

    Usage:
        logger = GameLogger()
        logger.start_session("session_123")
        logger.combat("Combat started", participants=["fighter", "goblin_1"])
        logger.close_session()
    """

    def __init__(
        self,
        min_level: LogLevel = LogLevel.INFO,
        output_dir: str = "logs/",
        console_output: bool = False
    ):
        """
        Initialize the game logger.

        Args:
            min_level: Minimum log level to record (default: INFO)
            output_dir: Directory for log files (default: logs/)
            console_output: Enable console output (default: False)
        """
        self.min_level = min_level
        self.output_dir = Path(output_dir)
        self.console_output = console_output

        self.session_id: Optional[str] = None
        self.current_turn_id: Optional[str] = None
        self.log_file: Optional[Path] = None
        self._file_handle: Optional[TextIO] = None
        self._logger: Optional[FilteringBoundLogger] = None

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Configure structlog
        self._configure_structlog()

    def _configure_structlog(self):
        """Configure structlog with appropriate processors."""
        # Shared processors for all outputs
        shared_processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        ]

        # Configure structlog globally
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(self.min_level.value),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,  # Allow reconfiguration
        )

    def start_session(self, session_id: str) -> Path:
        """
        Start a new logging session.

        Creates a new log file and configures structlog to write to it.

        Args:
            session_id: Unique session identifier

        Returns:
            Path to the log file
        """
        self.session_id = session_id
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{session_id}_{timestamp}.jsonl"
        self.log_file = self.output_dir / filename

        # Close any existing file handle
        if self._file_handle:
            self._file_handle.close()

        # Open new file for streaming writes
        self._file_handle = open(self.log_file, "a", encoding="utf-8")

        # Create a custom logger factory that writes to our file
        self._setup_logger()

        # Log session start
        self.turn("Session started", session_id=session_id, log_file=str(self.log_file))

        # Update latest symlink
        self._update_latest_symlink()

        return self.log_file

    def _setup_logger(self):
        """Set up the structlog logger with file and optional console output."""
        # Create processors list
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]

        # JSON processor for file output
        json_processor = structlog.processors.JSONRenderer()

        def write_to_file(_, __, event_dict):
            """Custom processor to write JSON to file."""
            if self._file_handle:
                import json
                self._file_handle.write(json.dumps(event_dict, default=str) + "\n")
                self._file_handle.flush()
            return event_dict

        # Build the final processor chain
        final_processors = processors + [write_to_file]

        if self.console_output:
            # Add console rendering
            console_processor = structlog.dev.ConsoleRenderer(colors=True)

            def write_to_console(_, __, event_dict):
                """Write formatted output to console."""
                # Format for console
                timestamp = event_dict.get("timestamp", "")[:8]  # HH:MM:SS
                level = event_dict.get("level", "info").upper()
                channel = event_dict.get("channel", "SYSTEM")
                event = event_dict.get("event", "")

                # Format data fields
                data_fields = {k: v for k, v in event_dict.items()
                               if k not in ("timestamp", "level", "channel", "event", "session_id", "turn_id")}
                data_str = ""
                if data_fields:
                    data_parts = []
                    for k, v in data_fields.items():
                        if isinstance(v, str) and len(v) > 50:
                            v = v[:47] + "..."
                        data_parts.append(f"{k}={v}")
                    data_str = " | " + ", ".join(data_parts)

                print(f"[{timestamp}] {channel:<12} {level:<7} {event}{data_str}")
                return event_dict

            final_processors.append(write_to_console)

        # Reconfigure structlog
        structlog.configure(
            processors=final_processors,
            wrapper_class=structlog.make_filtering_bound_logger(self.min_level.value),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )

        # Get a bound logger with session context
        self._logger = structlog.get_logger().bind(session_id=self.session_id)

    def _update_latest_symlink(self):
        """Update the 'latest.jsonl' symlink to point to current log file."""
        if not self.log_file:
            return

        latest_link = self.output_dir / "latest.jsonl"
        try:
            if latest_link.is_symlink() or latest_link.exists():
                latest_link.unlink()
            latest_link.symlink_to(self.log_file.name)
        except OSError:
            pass  # Symlinks may not work on all platforms

    def close_session(self):
        """Close the current logging session."""
        if self.session_id:
            self.turn("Session closed", session_id=self.session_id)

        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

        self.session_id = None
        self.current_turn_id = None
        self._logger = None

    def set_turn(self, turn_id: str):
        """Set current turn for log context."""
        self.current_turn_id = turn_id
        if self._logger:
            self._logger = self._logger.bind(turn_id=turn_id)

    def log(
        self,
        channel: LogChannel,
        level: LogLevel,
        message: str,
        **data
    ):
        """
        Log a message with optional structured data.

        Args:
            channel: The logging channel
            level: Log severity level
            message: Human-readable message
            **data: Additional structured data to include
        """
        if level.value < self.min_level.value:
            return

        if not self._logger:
            # Fallback: print to stderr if session not started
            import json
            entry = {
                "timestamp": datetime.now().isoformat(),
                "channel": channel.value,
                "level": level.name,
                "event": message,
                **data
            }
            print(json.dumps(entry, default=str), file=sys.stderr)
            return

        # Get the appropriate log method
        log_method = getattr(self._logger, _level_to_name(level))
        log_method(message, channel=channel.value, **data)

    # ==================== Convenience Methods ====================

    def dm(self, message: str, level: LogLevel = LogLevel.INFO, **data):
        """Log to DM_AGENT channel."""
        self.log(LogChannel.DM_AGENT, level, message, **data)

    def dm_tool(self, message: str, level: LogLevel = LogLevel.INFO, **data):
        """Log to DM_TOOLS channel."""
        self.log(LogChannel.DM_TOOLS, level, message, **data)

    def extraction(self, message: str, level: LogLevel = LogLevel.INFO, **data):
        """Log to STATE_EXTRACTION channel."""
        self.log(LogChannel.STATE_EXTRACTION, level, message, **data)

    def command(self, message: str, level: LogLevel = LogLevel.INFO, **data):
        """Log to COMMAND_EXECUTION channel."""
        self.log(LogChannel.COMMAND_EXECUTION, level, message, **data)

    def turn(self, message: str, level: LogLevel = LogLevel.INFO, **data):
        """Log to TURN_MANAGEMENT channel."""
        self.log(LogChannel.TURN_MANAGEMENT, level, message, **data)

    def combat(self, message: str, level: LogLevel = LogLevel.INFO, **data):
        """Log to COMBAT_CYCLE channel."""
        self.log(LogChannel.COMBAT_CYCLE, level, message, **data)

    def step(self, message: str, level: LogLevel = LogLevel.INFO, **data):
        """Log to STEP_PROGRESSION channel."""
        self.log(LogChannel.STEP_PROGRESSION, level, message, **data)

    def discord(self, message: str, level: LogLevel = LogLevel.INFO, **data):
        """Log to DISCORD_UI channel."""
        self.log(LogChannel.DISCORD_UI, level, message, **data)

    def player(self, message: str, level: LogLevel = LogLevel.INFO, **data):
        """Log to PLAYER_INPUT channel."""
        self.log(LogChannel.PLAYER_INPUT, level, message, **data)

    def context(self, message: str, level: LogLevel = LogLevel.INFO, **data):
        """Log to CONTEXT_BUILDING channel."""
        self.log(LogChannel.CONTEXT_BUILDING, level, message, **data)

    # ==================== Debug Helpers ====================

    def debug(self, channel: LogChannel, message: str, **data):
        """Log at DEBUG level."""
        self.log(channel, LogLevel.DEBUG, message, **data)

    def info(self, channel: LogChannel, message: str, **data):
        """Log at INFO level."""
        self.log(channel, LogLevel.INFO, message, **data)

    def warning(self, channel: LogChannel, message: str, **data):
        """Log at WARNING level."""
        self.log(channel, LogLevel.WARNING, message, **data)

    def error(self, channel: LogChannel, message: str, **data):
        """Log at ERROR level."""
        self.log(channel, LogLevel.ERROR, message, **data)

    def __del__(self):
        """Ensure file handle is closed on deletion."""
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception:
                pass


def create_game_logger(
    min_level: LogLevel = LogLevel.INFO,
    output_dir: str = "logs/",
    console_output: bool = False
) -> GameLogger:
    """
    Factory function to create a configured GameLogger.

    Args:
        min_level: Minimum log level (default: INFO)
        output_dir: Directory for log files (default: logs/)
        console_output: Enable console output (default: False)

    Returns:
        Configured GameLogger instance
    """
    return GameLogger(
        min_level=min_level,
        output_dir=output_dir,
        console_output=console_output
    )


# Singleton instance for global access (optional pattern)
_global_logger: Optional[GameLogger] = None


def get_logger() -> Optional[GameLogger]:
    """Get the global logger instance if set."""
    return _global_logger


def set_logger(logger: GameLogger):
    """Set the global logger instance."""
    global _global_logger
    _global_logger = logger
