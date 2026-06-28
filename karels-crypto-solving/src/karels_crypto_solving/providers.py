"""Generic chat interface across model providers (via the company gateway).

All providers authenticate with the **same** key (``OPENAI_API_KEY`` — the
gateway token) but use different base URLs and SDKs:

* OpenAI    — ``OPENAI_BASE_URL``    (``openai`` SDK, chat completions)
* Anthropic — ``ANTHROPIC_BASE_URL`` (``anthropic`` SDK, messages)
* Google    — ``GOOGLE_BASE_URL``    (``google-genai`` SDK, Vertex mode)

`chat()` hides the per-provider differences in message shape, "thinking"/
reasoning controls, temperature handling and token-usage accounting, returning a
uniform :class:`ChatResult`. Provider/transport errors are normalised to
:class:`ProviderError` (with a status code) so callers can decide what to retry
vs. crash on.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Map a reasoning-effort label to an approximate "thinking" token budget, used
# by providers whose thinking is budget-based (Anthropic, Google).
_THINKING_BUDGET = {"minimal": 1024, "low": 2048, "medium": 6000, "high": 16000}


@dataclass
class ChatResult:
    text: str
    prompt_tokens: int
    completion_tokens: int


class ProviderError(Exception):
    """A provider/transport error (rate limit, unavailable, bad request, …)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def provider_for(model: str) -> str:
    name = (model or "").lower()
    if name.startswith("claude"):
        return "anthropic"
    if name.startswith("gemini"):
        return "google"
    return "openai"


def is_reasoning_model(model: str) -> bool:
    """OpenAI reasoning families (o-series, gpt-5 non-chat). Other providers gate
    "thinking" purely on whether ``reasoning_effort`` is requested."""
    name = (model or "").lower()
    if name.startswith(("o1", "o3", "o4", "o5")):
        return True
    return name.startswith("gpt-5") and "chat" not in name


def chat(
    model: str,
    system: str,
    user: str,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
) -> ChatResult:
    provider = provider_for(model)
    if provider == "anthropic":
        return _anthropic_chat(model, system, user, max_tokens, temperature, reasoning_effort)
    if provider == "google":
        return _google_chat(model, system, user, max_tokens, temperature, reasoning_effort)
    return _openai_chat(model, system, user, max_tokens, temperature, reasoning_effort)


# --- OpenAI ---------------------------------------------------------------

_openai_client = None


def _openai_chat(model, system, user, max_tokens, temperature, reasoning_effort) -> ChatResult:
    global _openai_client
    import openai

    if _openai_client is None:
        _openai_client = openai.OpenAI()  # reads OPENAI_API_KEY / OPENAI_BASE_URL
    reasoning = is_reasoning_model(model)
    kwargs = {}
    if temperature is not None and not reasoning:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_completion_tokens"] = max(max_tokens, 16000) if reasoning else max_tokens
    if reasoning_effort and reasoning:
        kwargs["reasoning_effort"] = reasoning_effort
    try:
        resp = _openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **kwargs,
        )
    except openai.APIStatusError as exc:
        raise ProviderError(str(exc), getattr(exc, "status_code", None)) from exc
    except openai.APIError as exc:  # connection/timeout
        raise ProviderError(str(exc), None) from exc
    usage = getattr(resp, "usage", None)
    return ChatResult(
        text=resp.choices[0].message.content or "",
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
    )


# --- Anthropic ------------------------------------------------------------

_anthropic_client = None


def _anthropic_chat(model, system, user, max_tokens, temperature, reasoning_effort) -> ChatResult:
    global _anthropic_client
    import anthropic

    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(
            base_url=os.environ["ANTHROPIC_BASE_URL"], api_key=os.environ["OPENAI_API_KEY"]
        )
    kwargs = {"model": model, "system": system, "messages": [{"role": "user", "content": user}]}
    if reasoning_effort:
        budget = _THINKING_BUDGET.get(reasoning_effort, 4000)
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
        kwargs["max_tokens"] = (max_tokens or 0) + budget + 1024  # must exceed the budget
        # temperature must be default (1) when thinking is enabled -> omit it.
    else:
        kwargs["max_tokens"] = max_tokens or 1024
        if temperature is not None:
            kwargs["temperature"] = temperature
    try:
        resp = _anthropic_client.messages.create(**kwargs)
    except anthropic.APIStatusError as exc:
        raise ProviderError(str(exc), getattr(exc, "status_code", None)) from exc
    except anthropic.APIError as exc:
        raise ProviderError(str(exc), None) from exc
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    usage = resp.usage
    return ChatResult(
        text=text,
        prompt_tokens=getattr(usage, "input_tokens", 0) or 0,
        completion_tokens=getattr(usage, "output_tokens", 0) or 0,
    )


# --- Google (Vertex via gateway) ------------------------------------------

_google_client = None


def _google_chat(model, system, user, max_tokens, temperature, reasoning_effort) -> ChatResult:
    global _google_client
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    from google.oauth2.credentials import Credentials

    if _google_client is None:
        _google_client = genai.Client(
            vertexai=True,
            project="aigateway",
            location="global",
            http_options=types.HttpOptions(
                api_version="v1", base_url=os.environ["GOOGLE_BASE_URL"]
            ),
            credentials=Credentials(os.environ["OPENAI_API_KEY"]),
        )
    cfg = types.GenerateContentConfig(system_instruction=system)
    if max_tokens is not None:
        cfg.max_output_tokens = max_tokens
    if temperature is not None:
        cfg.temperature = temperature
    if reasoning_effort:
        cfg.thinking_config = types.ThinkingConfig(
            thinking_budget=_THINKING_BUDGET.get(reasoning_effort, 4000)
        )
    try:
        resp = _google_client.models.generate_content(model=model, contents=user, config=cfg)
    except APIError as exc:
        raise ProviderError(str(exc), getattr(exc, "code", None)) from exc
    meta = getattr(resp, "usage_metadata", None)
    completion = (getattr(meta, "candidates_token_count", 0) or 0) + (
        getattr(meta, "thoughts_token_count", 0) or 0
    )
    return ChatResult(
        text=resp.text or "",
        prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
        completion_tokens=completion,
    )
