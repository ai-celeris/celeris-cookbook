"""The token-window helpers every example repeats must agree on the rules:
max_tokens is a multiple of 256 in [256, 1024], and the base URL gains /v1."""

import pytest
from conftest import load_example

benchmark = load_example("benchmark", "examples/benchmark/main.py")
triage = load_example("triage", "examples/alert-triage-agent/main.py")


@pytest.mark.parametrize(
    ("requested", "expected"),
    [(0, 256), (1, 256), (256, 256), (257, 512), (512, 512), (513, 768), (1024, 1024), (5000, 1024)],
)
def test_normalize_max_tokens(requested, expected):
    assert benchmark.normalize_max_tokens(requested) == expected


def test_normalized_values_are_wire_legal():
    for requested in range(0, 2048, 37):
        value = benchmark.normalize_max_tokens(requested)
        assert 256 <= value <= 1024
        assert value % 256 == 0


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
