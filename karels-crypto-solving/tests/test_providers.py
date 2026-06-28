from karels_crypto_solving import providers


def test_provider_routing():
    assert providers.provider_for("gpt-4o") == "openai"
    assert providers.provider_for("o4-mini") == "openai"
    assert providers.provider_for("gpt-5.5-2026-04-23") == "openai"
    assert providers.provider_for("claude-haiku-4-5-20251001") == "anthropic"
    assert providers.provider_for("gemini-2.0-flash-lite-001") == "google"


def test_is_reasoning_model():
    assert providers.is_reasoning_model("o3")
    assert providers.is_reasoning_model("gpt-5-mini-2025-08-07")
    assert not providers.is_reasoning_model("gpt-4o")
    assert not providers.is_reasoning_model("gpt-5-chat-latest")


def test_provider_error_carries_status():
    err = providers.ProviderError("nope", status_code=429)
    assert err.status_code == 429
    assert "nope" in str(err)
