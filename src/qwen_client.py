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
from typing import Any, Dict, Optional

import google.generativeai as genai

import config


class GeminiError(Exception):
    """Raised when the LLM call fails or returns unusable output."""


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
        one message. If the first answer is not valid JSON, we ask Gemini
        once more to fix its own formatting before giving up.
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
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                )
            except Exception as exc:
                # Covers auth errors, rate limits, timeouts, network issues...
                raise GeminiError(
                    f"{agent_name}: Gemini API call failed ({type(exc).__name__}: {exc}). "
                    "Check GOOGLE_API_KEY, GEMINI_MODEL and your network."
                ) from exc

            last_raw = ""
            try:
                # response.text raises ValueError when the reply is empty
                # or was blocked by safety filters.
                last_raw = (response.text or "").strip()
            except (ValueError, AttributeError):
                last_raw = ""

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
