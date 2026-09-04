"""
Gemini client for CareerOS AI.

NOTE ON THE FILENAME: this module was originally written for Alibaba Cloud
Qwen (the project started life for the Alibaba Cloud AI Hackathon Pakistan
2026). It now calls the Google Gemini API through the `google-generativeai`
SDK instead. The filename was deliberately kept so existing imports in
agents.py, main.py and the tests keep working — only the contents changed.

Every agent in `agents.py` talks to Gemini through this single, small
wrapper, so the LLM can be swapped or debugged in one place.

Usage:
    client = GeminiClient()              # raises GeminiError if no API key
    data = client.chat_json(
        agent_name="Resume Analysis Agent",
        system_prompt="You are a recruiter...",
        user_prompt="Analyze this resume...",
    )
"""

import json
import re
import time
from typing import Any, Dict, Optional

import google.generativeai as genai

import config


class GeminiError(Exception):
    """Raised when the LLM call fails or returns unusable output."""


# The Gemini FREE tier allows only a few requests per minute (5/min for
# flash models like gemini-3.6-flash). One full CareerOS analysis makes
# exactly 5 LLM calls, so running two analyses back-to-back can hit a 429
# "ResourceExhausted" quota error. Those errors are temporary — the API
# message even says how long to wait — so we retry automatically instead
# of failing the whole analysis.
RATE_LIMIT_MAX_RETRIES = 4
RATE_LIMIT_FALLBACK_WAIT_SECONDS = 15  # used when the error has no "retry in Xs" hint
RATE_LIMIT_MAX_WAIT_SECONDS = 60


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True when an exception looks like a 429 quota / rate-limit error."""
    # google.api_core exposes the HTTP status as .code (429 = Too Many
    # Requests); SDK versions differ, so also match on the error text.
    if getattr(exc, "code", None) == 429:
        return True
    text = f"{type(exc).__name__}: {exc}".lower()
    return (
        "429" in text
        or "resourceexhausted" in text
        or "exceeded your current quota" in text
    )


def _extract_retry_seconds(exc: Exception) -> Optional[float]:
    """Pull the 'Please retry in Xs' hint out of a quota error, if present."""
    match = re.search(r"retry in ([0-9.]+)\s*s", str(exc), re.IGNORECASE)
    return float(match.group(1)) if match else None


# Every prompt gets the same strict output rules appended, so Gemini always
# answers with a single JSON object we can parse.
SHARED_JSON_RULES = """
OUTPUT RULES (very important):
- Reply with ONE valid JSON object and nothing else.
- No markdown, no code fences, no explanations before or after the JSON.
- Use [] for empty lists and "" for empty strings.
- Keep every string concise (under 300 characters) unless told otherwise.
""".strip()


def extract_json_object(text: str) -> Dict[str, Any]:
    """
    Parse a JSON object out of an LLM reply.

    LLMs sometimes wrap JSON in markdown fences (```json ... ```) or add a
    sentence of chatter, so we clean that up before parsing.

    Raises ValueError if no JSON object can be recovered.
    """
    if not text or not text.strip():
        raise ValueError("empty response")

    cleaned = text.strip()

    # If the reply is wrapped in a markdown code fence, keep only the inside.
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()

    # Fall back to the outermost {...} block, ignoring any chatter around it.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in response")

    return json.loads(cleaned[start : end + 1])  # may raise json.JSONDecodeError


class GeminiClient:
    """Thin wrapper around the Gemini API that always returns a dict."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = (api_key or config.settings.google_api_key).strip()
        self.model_name = model or config.settings.gemini_model
        self.temperature = config.settings.gemini_temperature
        self.max_tokens = config.settings.gemini_max_tokens

        if not self.api_key:
            raise GeminiError(
                "GOOGLE_API_KEY is not set. Copy .env.example to .env and "
                "add your Google AI Studio API key (https://aistudio.google.com/apikey)."
            )

        # Configure the SDK once and reuse the model for every call,
        # instead of re-configuring on each request.
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name=self.model_name)

    def _generate_content(
        self, agent_name: str, prompt: str, generation_config: Dict[str, Any]
    ) -> str:
        """
        Call Gemini once, retrying automatically on 429 rate-limit errors.

        Free-tier quota errors are temporary: the API's message even says
        "Please retry in Xs", so we sleep that long (plus a small buffer)
        and try again instead of failing the whole analysis.
        """
        for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                )
            except Exception as exc:
                if not _is_rate_limit_error(exc):
                    # Covers auth errors, bad model names, timeouts, network...
                    raise GeminiError(
                        f"{agent_name}: Gemini API call failed ({type(exc).__name__}: {exc}). "
                        "Check GOOGLE_API_KEY, GEMINI_MODEL and your network."
                    ) from exc

                if attempt >= RATE_LIMIT_MAX_RETRIES:
                    raise GeminiError(
                        f"{agent_name}: still rate-limited after "
                        f"{RATE_LIMIT_MAX_RETRIES} retries ({type(exc).__name__}: {exc}). "
                        "The Gemini free tier allows only a few requests per minute — "
                        "wait about a minute and run the analysis again. Details: "
                        "https://ai.google.dev/gemini-api/docs/rate-limits"
                    ) from exc

                wait = _extract_retry_seconds(exc)
                if wait is None:
                    wait = RATE_LIMIT_FALLBACK_WAIT_SECONDS * (attempt + 1)
                wait = min(wait + 0.5, RATE_LIMIT_MAX_WAIT_SECONDS)
                time.sleep(wait)
                continue

            try:
                # response.text raises ValueError when the reply is empty
                # or was blocked by safety filters.
                return (response.text or "").strip()
            except (ValueError, AttributeError):
                return ""

    def chat_json(
        self,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send one prompt to Gemini and return its answer as a Python dict.

        generate_content() has no separate system/user roles, so the system
        prompt, the shared JSON rules and the user prompt are combined into
        one message. Rate-limit (429) errors are retried automatically in
        _generate_content; if the first answer is not valid JSON, we ask
        Gemini once more to fix its own formatting before giving up.
        """
        prompt = f"{system_prompt}\n\n{SHARED_JSON_RULES}\n\n{user_prompt}"

        temp = self.temperature if temperature is None else temperature
        tokens = max_tokens or self.max_tokens
        generation_config = {
            "temperature": temp,
            "max_output_tokens": tokens,
        }

        last_raw = ""
        for attempt in range(2):  # 1 normal try + 1 repair try
            last_raw = self._generate_content(agent_name, prompt, generation_config)

            try:
                return extract_json_object(last_raw)
            except ValueError:
                # Show Gemini its broken output and ask for valid JSON once.
                prompt = (
                    f"{prompt}\n\n"
                    "Your previous answer was not valid JSON:\n"
                    f"{last_raw[:1000]}\n\n"
                    "Reply again with ONLY the JSON object — no markdown "
                    "fences, no commentary."
                )

        raise GeminiError(
            f"{agent_name} returned invalid JSON twice. "
            f"Raw output began with: {last_raw[:300]!r}"
        )
