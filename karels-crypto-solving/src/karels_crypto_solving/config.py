"""LLM configuration.

Credentials are read from the standard OpenAI environment variables, which are
expected to be provided (e.g. via GitHub secrets):

* ``OPENAI_API_KEY``  - the API key.
* ``OPENAI_BASE_URL`` - the API base URL (the ``openai`` client reads this
  automatically; useful for self-hosted / proxied models).
* ``OPENAI_MODEL``    - the model name to use (defaults to ``gpt-4o-mini``).
"""

from __future__ import annotations

import os

DEFAULT_MODEL = "gpt-4o-mini"


def model_name() -> str:
    # `or` so an empty/unset env var falls back to the default.
    return os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL


def openai_client():
    """Return a synchronous OpenAI client (reads OPENAI_* env vars)."""
    from openai import OpenAI

    return OpenAI()


def async_openai_client():
    """Return an asynchronous OpenAI client (reads OPENAI_* env vars)."""
    from openai import AsyncOpenAI

    return AsyncOpenAI()
