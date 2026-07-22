"""Token-window helpers and defaults must agree with the public contract."""

from pathlib import Path

import pytest

from conftest import load_example

benchmark = load_example("benchmark", "examples/benchmark/main.py")
triage = load_example("triage", "examples/alert-triage-agent/main.py")


ROOT = Path(__file__).resolve().parents[1]


def test_token_budget_constants_and_default():
    assert benchmark.TOTAL_TOKEN_LIMIT == 8192
    assert benchmark.MAX_INPUT_TOKENS == 2048
    assert benchmark.DEFAULT_MAX_OUTPUT_TOKENS == 2048
    assert benchmark.max_output_tokens() == 2048
    assert benchmark.max_output_tokens(256) == 256


@pytest.mark.parametrize("requested", [0, -1, 8192, 9000])
def test_invalid_output_budget_is_rejected(requested):
    with pytest.raises(ValueError):
        benchmark.max_output_tokens(requested)


@pytest.mark.parametrize(
    ("max_tokens", "expected_input"),
    [(2048, 2048), (256, 2048), (6144, 2048), (7000, 1192)],
)
def test_input_budget_respects_input_and_total_caps(max_tokens, expected_input):
    assert benchmark.input_token_budget(max_tokens) == expected_input


def test_no_stale_token_contract_claims():
    stale_fragments = (
        "40" "96-token",
        "40" "96 token",
        "[256, " "1024]",
        "256-" "1024",
        "between 256 and " "1024",
        "MAX_OUTPUT_TOKENS = " "1024",
    )
    suffixes = {".ipynb", ".md", ".py", ".ts", ".txt", ".yaml"}
    offenders = []
    for path in ROOT.rglob("*"):
        if (
            path == Path(__file__)
            or not path.is_file()
            or path.suffix not in suffixes
            or "dist" in path.parts
            or "node_modules" in path.parts
        ):
            continue
        text = path.read_text(errors="ignore")
        for fragment in stale_fragments:
            if fragment in text:
                offenders.append(f"{path.relative_to(ROOT)}: {fragment}")
    assert not offenders, "stale token contract:\n" + "\n".join(offenders)


@pytest.mark.parametrize(
    ("env_value", "expected"),
    [
        ("https://api.example.com/celeris-1", "https://api.example.com/celeris-1/v1"),
        ("https://api.example.com/celeris-1/", "https://api.example.com/celeris-1/v1"),
        ("https://api.example.com/celeris-1/v1", "https://api.example.com/celeris-1/v1"),
    ],
)
def test_celeris_base_url_appends_v1(monkeypatch, env_value, expected):
    monkeypatch.setenv("CELERIS_BASE_URL", env_value)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    assert benchmark.celeris_base_url() == expected
    assert triage.celeris_base_url() == expected
