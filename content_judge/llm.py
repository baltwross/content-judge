"""
content_judge/llm.py

Gemini LLM wrappers. All LLM calls in the system go through these two functions.
"""

from __future__ import annotations

import time
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from content_judge.config import get_settings

T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 3
RETRY_DELAYS = [10, 30, 60]  # generous backoff for free-tier rate limits


class LLMError(Exception):
    """Raised when an LLM call fails after retries."""

    pass


def _get_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def call_gemini_video(
    prompt: str,
    video_source: str,
    model: str | None = None,
) -> str:
    """
    Gemini wrapper for video analysis — returns raw text.

    Accepts YouTube URL (passed as file_data.file_uri) or local file path
    (uploaded via File API).
    """
    settings = get_settings()
    client = _get_client()
    model = model or settings.default_model

    parts: list[types.Part] = []

    if video_source.startswith(("http://", "https://")):
        # YouTube URL — pass directly
        parts.append(types.Part(file_data=types.FileData(file_uri=video_source)))
    else:
        # Local file — upload via File API
        uploaded = client.files.upload(file=video_source)
        parts.append(types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type))

    parts.append(types.Part(text=prompt))

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model,
                contents=types.Content(parts=parts),
                config=types.GenerateContentConfig(temperature=0.0),
            )
            return response.text
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAYS[attempt])

    raise LLMError(f"Gemini video call failed after {MAX_RETRIES} retries: {last_error}")


def call_gemini_structured(
    prompt: str,
    output_schema: type[T] | None = None,
    model: str | None = None,
    video_source: str | None = None,
    system_prompt: str | None = None,
) -> T | str:
    """
    Gemini wrapper for structured JSON output.

    When output_schema is provided, returns a validated Pydantic model.
    When output_schema is None, returns raw text.

    Supports text-only or video+text input.
    """
    settings = get_settings()
    client = _get_client()
    model = model or settings.default_model

    parts: list[types.Part] = []

    # Add video if provided
    if video_source:
        if video_source.startswith(("http://", "https://")):
            parts.append(types.Part(file_data=types.FileData(file_uri=video_source)))
        else:
            uploaded = client.files.upload(file=video_source)
            parts.append(types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type))

    parts.append(types.Part(text=prompt))

    # Build config
    config_kwargs: dict = {"temperature": 0.0}
    if output_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = output_schema
    if system_prompt:
        config_kwargs["system_instruction"] = system_prompt

    generate_kwargs: dict = {
        "model": model,
        "contents": types.Content(parts=parts),
        "config": types.GenerateContentConfig(**config_kwargs),
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(**generate_kwargs)

            if output_schema is None:
                return response.text

            # Parse structured output into Pydantic model
            return output_schema.model_validate_json(response.text)

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAYS[attempt])

    raise LLMError(f"Gemini structured call failed after {MAX_RETRIES} retries: {last_error}")
