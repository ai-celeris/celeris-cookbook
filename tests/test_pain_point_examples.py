"""Offline tests for the routing, guardrail, and agent example logic."""

import json

from conftest import load_example

routing = load_example("routing", "examples/realtime-classification/main.py")
guardrails = load_example("guardrails", "examples/guardrails/main.py")
agent = load_example("agent_latency", "examples/agent-latency/main.py")


def test_parse_route_first_mention_wins():
    assert routing.parse_route("This is a billing issue, not a technical one.") == "billing"
    assert routing.parse_route("The technical team should handle it.") == "technical"
    assert routing.parse_route("") is None
    assert routing.parse_route("No route named here.") is None


def test_parse_verdict_accepts_fenced_and_prose_json():
    verdict = guardrails.parse_verdict('```json\n{"action": "BLOCK", "reason": "abuse"}\n```')
    assert verdict == {"action": "block", "reason": "abuse"}
    verdict = guardrails.parse_verdict('Sure: {"action": "allow", "reason": "fine"}')
    assert verdict["action"] == "allow"


def test_parse_verdict_rejects_unknown_action_and_bad_json():
    assert guardrails.parse_verdict('{"action": "maybe", "reason": "?"}') is None
    assert guardrails.parse_verdict("not json") is None
    assert guardrails.parse_verdict('{"action": "allow"') is None


def test_agent_extract_json_and_tools():
    assert agent.extract_json('{"tool": "get_order", "args": {"order_id": "ORD-1042"}}')["tool"] == "get_order"
    assert agent.extract_json("nope") is None
    order = json.loads(agent.run_tool("get_order", {"order_id": "ORD-1042"}))
    assert order["tracking_id"] == "TRK-88231"
    assert "error" in json.loads(agent.run_tool("get_order", {"order_id": "missing"}))
    assert "error" in json.loads(agent.run_tool("unknown", {}))


def test_compounding_table_scales_linearly():
    table = agent.compounding_table(500.0)
    assert "| 10 | 5.0 s | 20 s |" in table
    assert "| 50 | 25.0 s | 100 s |" in table
