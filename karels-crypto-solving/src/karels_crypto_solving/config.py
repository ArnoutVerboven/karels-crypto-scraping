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


def load_env() -> None:
    """Load a local ``.env`` file if present (real env vars take precedence).

    Looks from the current directory upward, so a ``.env`` in the module folder
    or repo root is picked up. ``override=False`` means CI secrets / already-set
    variables win over the file.
    """
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:  # pragma: no cover - dotenv is a declared dependency
        return
    load_dotenv(find_dotenv(usecwd=True), override=False)


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
