"""Offline tests for the alert triage agent's parsing and tool plumbing."""

import json

from conftest import load_example

triage = load_example("triage", "examples/alert-triage-agent/main.py")


def test_extract_json_plain_object():
    assert triage.extract_json('{"tool": "get_alert", "args": {"alert_id": "A"}}') == {
        "tool": "get_alert",
        "args": {"alert_id": "A"},
    }


def test_extract_json_with_surrounding_prose():
    reply = 'Sure. {"verdict": {"root_cause": "x", "confidence": "high"}} Done.'
    assert triage.extract_json(reply) == {"verdict": {"root_cause": "x", "confidence": "high"}}


def test_extract_json_rejects_garbage_and_truncation():
    assert triage.extract_json("no json here") is None
    assert triage.extract_json('{"tool": "search_runbooks", "args": {"query": "cut off') is None
    assert triage.extract_json("[1, 2, 3]") is None


def test_run_tool_unknown_tool_is_an_error_payload():
    result = json.loads(triage.run_tool("nope", {}))
    assert "error" in result


def test_run_tool_get_alert_reads_fixture():
    result = json.loads(triage.run_tool("get_alert", {"alert_id": "ALERT-4127"}))
    assert result["service"] == "checkout-api"


def test_run_tool_search_runbooks_ranks_matches():
    result = json.loads(triage.run_tool("search_runbooks", {"query": "checkout-api latency"}))
    assert result[0]["id"] == "RB-12"


def test_fit_messages_never_drops_system_or_task():
    big = "x" * 40_000
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "task"},
        {"role": "user", "content": big},
        {"role": "user", "content": big},
        {"role": "user", "content": "newest"},
    ]
    kept = triage.fit_messages(messages)
    assert kept[0]["content"] == "sys"
    assert kept[1]["content"] == "task"
    assert sum(len(m["content"]) for m in kept) <= triage.INPUT_BUDGET_BYTES
