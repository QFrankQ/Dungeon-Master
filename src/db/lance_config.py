"""Configuration for LanceDB rules service."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LanceConfig:
    """Configuration for LanceDB rules service."""

    db_path: Path = Path("src/db/lancedb")
    table_name: str = "rules"
    embedding_model: str = "gemini-embedding-001"
    vector_dims: int = 768

    @classmethod
    def from_env(cls) -> "LanceConfig":
        """
        Create config from environment variables.

        Environment variables:
            LANCE_DB_PATH: Path to LanceDB database (default: src/db/lancedb)
            LANCE_TABLE_NAME: Name of the table (default: rules)

        Returns:
            LanceConfig instance
        """
        return cls(
            db_path=Path(os.getenv("LANCE_DB_PATH", "src/db/lancedb")),
            table_name=os.getenv("LANCE_TABLE_NAME", "rules")
        )

    def validate(self) -> bool:
        """
        Validate configuration.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        if self.vector_dims != 768:
            raise ValueError(
                f"Invalid vector_dims: {self.vector_dims}. "
                "gemini-embedding-001 requires 768 dimensions."
            )

        if not self.table_name:
            raise ValueError("table_name cannot be empty")

        return True
