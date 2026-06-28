from karels_crypto_solving.parse_models import extract_registry

HTML = """
<table>
  <tr><th>Model</th><th>Input</th><th>Output</th></tr>
  <tr><td>claude-haiku-4-5-20251001</td><td>$1.0 / 1MTok</td><td>$5.0 / 1MTok</td></tr>
  <tr><td>gemini-2.0-flash-lite-001</td><td>$0.075 / 1MTok</td><td>$0.30 / 1MTok</td></tr>
</table>
"""


def test_extract_registry_table():
    reg = extract_registry(HTML)
    assert "Model" not in reg  # header row rejected
    assert reg["claude-haiku-4-5-20251001"] == {"available": True, "input": 1.0, "output": 5.0}
    assert reg["gemini-2.0-flash-lite-001"]["input"] == 0.075
    assert reg["gemini-2.0-flash-lite-001"]["output"] == 0.30
