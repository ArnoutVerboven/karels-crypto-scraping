from karels_crypto_solving import providers


def test_provider_routing():
    assert providers.provider_for("gpt-4o-mini") == "openai"
    assert providers.provider_for("claude-opus-4-8") == "anthropic"
    assert providers.provider_for("gemini-3-pro-preview") == "google"


def test_anthropic_modes_ladder():
    # No reasoning effort -> never enable thinking.
    assert providers._anthropic_modes("claude-x", None) == ["off"]
    # First time: full ladder, enabled first.
    assert providers._anthropic_modes("claude-x", "low") == ["enabled", "adaptive", "off"]
    # A cached working mode is tried first, with the rest as fallbacks.
    providers._ANTHROPIC_MODE["claude-opus-4-8"] = "adaptive"
    assert providers._anthropic_modes("claude-opus-4-8", "low")[0] == "adaptive"
    providers._ANTHROPIC_MODE.clear()


def test_anthropic_kwargs_modes():
    enabled = providers._anthropic_kwargs("m", "s", "u", 256, 0.0, "low", "enabled")
    assert enabled["thinking"]["type"] == "enabled"
    assert "temperature" not in enabled  # omitted while thinking

    adaptive = providers._anthropic_kwargs("m", "s", "u", 256, 0.0, "low", "adaptive")
    assert adaptive["extra_body"]["thinking"]["type"] == "adaptive"
    assert adaptive["extra_body"]["output_config"]["effort"] == "low"

    off = providers._anthropic_kwargs("m", "s", "u", 256, 0.0, None, "off")
    assert off["max_tokens"] == 256
    assert off["temperature"] == 0.0
    assert "thinking" not in off
