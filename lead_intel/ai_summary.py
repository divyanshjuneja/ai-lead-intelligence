"""Optional AI-generated commentary using the Google Gemini API (Option A).

Design rules (the honesty requirements of this project):
- The AI NEVER computes or changes the score. It only writes 2-3 sentences
  of commentary interpreting a result the deterministic engine already
  produced. The UI labels this clearly.
- The API key comes from an environment variable (or .env), never from
  source code.
- Every failure mode (no key, network error, blocked response, malformed
  response) raises `AiSummaryError`, which the UI catches and turns into a
  friendly warning — the app keeps working without the commentary.

A plain `requests` POST to the official Gemini REST endpoint keeps this
transparent: one HTTP call, one JSON payload, one parsed string. The model
name is configurable so you can move to newer Gemini versions without
touching code.
"""

import os
import time

import requests
from dotenv import load_dotenv

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/{model}:generateContent"
)

# The model the user's Gemini key is provisioned for (Google retired 2.5
# models for new users). Override via GEMINI_MODEL if your key differs.
DEFAULT_MODEL = "gemini-3.8-flash"

# Google's documented env var names; GEMINI_API_KEY is the current standard.
API_KEY_ENV_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

# Pause between retry attempts when the Gemini service is struggling.
RETRY_PAUSE_SECONDS = 3


class AiSummaryError(Exception):
    """Raised for any failure in generating AI commentary."""


def get_api_key() -> str | None:
    """Return the Gemini API key from the environment, or None.

    `load_dotenv()` reads a `.env` file in the project root if present, so
    the key never needs to live in source code or git history.
    """
    load_dotenv()
    for name in API_KEY_ENV_VARS:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def build_prompt(company, result) -> str:
    """Build the instruction + facts prompt sent to the model.

    The model receives ONLY what the user entered and what the rules
    concluded — it is told not to invent facts, consistent with the
    project's honesty rules.
    """
    rule_lines = "\n".join(
        f"- {criterion.name}: {criterion.status} "
        f"({criterion.points}/{criterion.max_points} pts) — {criterion.explanation}"
        for criterion in result.criteria
    )
    missing = "; ".join(result.missing_info) or "none"

    return (
        "You are an assistant helping a salesperson understand a lead "
        "qualification result. Write 2 to 3 short sentences interpreting "
        "the result below. Rules: refer only to the facts given here; do "
        "NOT invent company information; explicitly note any unknowns as "
        "gaps in the data. Plain text, no markdown.\n\n"
        f"Company: {company.company_name} "
        f"({company.industry}, {company.employee_count} employees)\n"
        f"Description: {company.description or '(not provided)'}\n"
        f"Rule-based score: {result.total_score}/{result.max_possible} "
        f"({result.classification})\n"
        f"Rule outcomes:\n{rule_lines}\n"
        f"Missing information: {missing}"
    )


def _perform_request(
    prompt: str, api_key: str, model: str, timeout: float, attempts: int = 3
) -> dict:
    """Send the request to Gemini and return the raw JSON payload.

    The API key is sent in the `x-goog-api-key` header: newer Google key
    formats (e.g. starting with "AQ.") are not accepted as a `?key=` query
    parameter, but the header works for all key types.

    Retries up to `attempts` times with a short pause, because the Gemini
    service can transiently time out or return 503 under load.
    """
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(
                GEMINI_ENDPOINT.format(model=model),
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.4,
                        # Flash models with thinking (e.g. gemini-3.8-flash)
                        # spend part of this budget on hidden reasoning
                        # before answering.
                        "maxOutputTokens": 2048,
                    },
                },
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            if attempt == attempts:
                raise AiSummaryError(
                    f"Gemini request failed after {attempts} attempts: {error}"
                ) from error
            time.sleep(RETRY_PAUSE_SECONDS)


def _extract_text(payload: dict) -> str:
    """Pull the reply text out of the Gemini JSON response."""
    try:
        candidate = payload["candidates"][0]
        text = "".join(
            part.get("text", "") for part in candidate["content"]["parts"]
        ).strip()
    except (KeyError, IndexError, TypeError) as error:
        raise AiSummaryError(
            f"Unexpected Gemini response shape: {payload}"
        ) from error

    if not text:
        raise AiSummaryError("Gemini returned an empty response.")
    return text


def generate_summary(
    company,
    result,
    api_key: str,
    model: str | None = None,
    timeout: float = 60.0,
) -> str:
    """Generate AI commentary for an already-computed assessment result.

    model=None falls back to the GEMINI_MODEL env var, or DEFAULT_MODEL.
    """
    if model is None:
        model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    prompt = build_prompt(company, result)
    payload = _perform_request(prompt, api_key, model, timeout)
    return _extract_text(payload)
