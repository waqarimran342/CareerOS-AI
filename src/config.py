"""
Configuration for CareerOS AI.

All secrets come from environment variables (a local `.env` file is loaded
automatically if present). Never hard-code API keys in source code.

The `.env` file lives in the project root and is already listed in
`.gitignore`, so real keys never reach the repository.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = the folder that contains `src/`.
# We load `.env` from there so the app works no matter which folder
# you launch it from (project root or inside `src/`).
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Simple, flat settings object read from environment variables."""

    app_name: str = "CareerOS AI"
    app_version: str = "0.1.0"

    # ------------------------------------------------------------------
    # Google Gemini — via the google-generativeai SDK.
    #
    # Get your API key at: https://aistudio.google.com/apikey
    # ------------------------------------------------------------------
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")

    # gemini-3.6-flash is the default; switch models (e.g.
    # gemini-flash-latest for Google's auto-updating alias) with the
    # GEMINI_MODEL environment variable.
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    gemini_temperature: float = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
    gemini_max_tokens: int = int(os.getenv("GEMINI_MAX_TOKENS", "2048"))

    # ------------------------------------------------------------------
    # GitHub REST API (public data, no login required).
    # A personal access token is OPTIONAL — it only raises the rate
    # limit from 60 to 5000 requests/hour.
    # ------------------------------------------------------------------
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_timeout_seconds: int = int(os.getenv("GITHUB_TIMEOUT", "15"))
    github_max_repos: int = int(os.getenv("GITHUB_MAX_REPOS", "8"))

    # ------------------------------------------------------------------
    # Upload limits.
    # ------------------------------------------------------------------
    max_resume_mb: float = float(os.getenv("MAX_RESUME_MB", "10"))
    max_resume_chars: int = int(os.getenv("MAX_RESUME_CHARS", "12000"))

    # ------------------------------------------------------------------
    # Server.
    # ------------------------------------------------------------------
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))


# Single shared settings instance used across the app.
settings = Settings()


def is_gemini_configured() -> bool:
    """Return True when a Google Gemini API key is available."""
    return bool(settings.google_api_key.strip())
