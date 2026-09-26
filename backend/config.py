"""
TaskFlow Pro — Application Configuration

Loads settings from environment variables with sensible defaults.
SQLite is the default database for zero-configuration startup.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

BASE_DIR = Path(__file__).parent


class Settings:
    """Application settings loaded from environment variables."""

    PROJECT_NAME: str = "TaskFlow Pro"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Dependency-Aware Kanban Board with DAG Engine"

    # Database — SQLite by default for zero-config evaluator experience
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'taskflow.db'}"
    )

    # CORS — Allow frontend origin
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    ]

    # Google Gemini AI — Optional, app degrades gracefully without it
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # API Server
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def gemini_available(self) -> bool:
        return bool(self.GEMINI_API_KEY)


settings = Settings()
