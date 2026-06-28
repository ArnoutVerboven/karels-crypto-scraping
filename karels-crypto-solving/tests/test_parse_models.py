from karels_crypto_solving.parse_models import extract_registry

# Mirrors the AI-gateway "models" page: per-provider <details> sections whose
# innermost rows are Models | Cost | Data classification, with a combined cost
# cell. The "Lite LLM" meta-proxy re-lists models (here at $0) and must not
# overwrite the native, priced entries.
HTML = """
<details><summary>Anthropic <span>US or Global</span></summary>
<table>
  <tr><th>Endpoint</th><th>Models</th><th>Notes</th></tr>
  <tr><td>Messages</td>
    <td>
      <table>
        <tr><th>Models</th><th>Cost</th><th>Data classification</th></tr>
        <tr><td>claude-haiku-4-5-20251001</td>
            <td>Input: $1 / 1MTok, Output: $5 / 1MTok</td><td>x</td></tr>
        <tr><td>claude-opus-4-20250514, claude-opus-4-1-20250805</td>
            <td>Input: $15 / 1MTok, Output: $75 / 1MTok</td><td>x</td></tr>
      </table>
    </td>
    <td>note</td></tr>
</table>
</details>
<details><summary>OpenAI <span>US or EU or Global</span></summary>
<table>
  <tr><td>Embeddings</td>
    <td><table>
      <tr><th>Models</th><th>Cost</th><th>Data classification</th></tr>
      <tr><td>text-embedding-3-small</td><td>$0.02 / 1MTok</td><td>x</td></tr>
    </table></td><td>note</td></tr>
  <tr><td>Chat Completions</td>
    <td><table>
      <tr><th>Models</th><th>Cost</th><th>Data classification</th></tr>
      <tr><td>gpt-4o</td><td>Input: $2.5 / 1MTok, Output: $10 / 1MTok</td><td>x</td></tr>
    </table></td><td>note</td></tr>
</table>
</details>
<details><summary>Lite LLM <span>Global</span></summary>
<table>
  <tr><td>Chat Completions</td>
    <td><table>
      <tr><th>Models</th><th>Cost</th><th>Data classification</th></tr>
      <tr><td>claude-opus-4-20250514, gpt-4o</td>
          <td>Input: $0 / 1MTok, Output: $0 / 1MTok</td><td>x</td></tr>
    </table></td><td>note</td></tr>
</table>
</details>
"""


def test_extract_registry_gateway():
    reg = extract_registry(HTML)

    # Header text and endpoint labels are not models.
    assert "Models" not in reg
    assert "Endpoint" not in reg

    # Multi-alias model cells expand to one entry per alias.
    assert reg["claude-haiku-4-5-20251001"] == {
        "available": True,
        "provider": "Anthropic",
        "input": 1.0,
        "output": 5.0,
    }
    assert reg["claude-opus-4-1-20250805"]["input"] == 15.0

    # gpt-4o keeps its native OpenAI price; the Lite LLM $0 duplicate is ignored.
    assert reg["gpt-4o"] == {
        "available": True,
        "provider": "OpenAI",
        "input": 2.5,
        "output": 10.0,
    }
    assert reg["claude-opus-4-20250514"]["provider"] == "Anthropic"
    assert reg["claude-opus-4-20250514"]["input"] == 15.0

    # Single-$ embedding rows (no Input:/Output:) are skipped.
    assert "text-embedding-3-small" not in reg
