#!/usr/bin/env python3
"""How per-step latency compounds in agents, measured on celeris-1.

Runs a small order-support agent (a JSON tool loop over built-in data),
measures wall clock per model step, then shows how per-step latency
compounds as agents take more steps.

Usage:
    export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
    export CELERIS_API_KEY="<your-api-key>"
    pip install -r requirements.txt
    python3 main.py
"""

import json
import os
import statistics
import sys
import time

from openai import OpenAI

MAX_STEPS = 8

# Built-in data for the agent's tools.
ORDERS = {
    "ORD-1042": {
        "id": "ORD-1042",
        "item": "mechanical keyboard",
        "placed_at": "2026-07-14",
        "status": "shipped",
        "tracking_id": "TRK-88231",
    }
}

SHIPMENTS = {
    "TRK-88231": {
        "tracking_id": "TRK-88231",
        "carrier_status": "in transit",
        "last_scan": "2026-07-20, regional hub",
        "estimated_delivery": "2026-07-23",
    }
}

REFUND_POLICY = {
    "window_days": 30,
    "shipped_orders": "Refundable until 30 days after delivery. The item must be returned.",
}


def get_order(order_id: str) -> dict:
    return ORDERS.get(order_id) or {"error": f"unknown order {order_id!r}"}


def get_shipping_status(tracking_id: str) -> dict:
    return SHIPMENTS.get(tracking_id) or {"error": f"unknown tracking id {tracking_id!r}"}


def get_refund_policy() -> dict:
    return REFUND_POLICY


TOOLS = {
    "get_order": (get_order, {"order_id": str}),
    "get_shipping_status": (get_shipping_status, {"tracking_id": str}),
    "get_refund_policy": (get_refund_policy, {}),
}

SYSTEM_PROMPT = """You are an order-support agent. Answer the customer by using tools step by step.

Reply with EXACTLY ONE JSON object per turn, nothing else. Either a tool call:
  {"tool": "get_order", "args": {"order_id": "..."}}
  {"tool": "get_shipping_status", "args": {"tracking_id": "..."}}
  {"tool": "get_refund_policy", "args": {}}
or, once you know enough, the final answer:
  {"answer": "..."}

Check the order, then its shipment, then the refund policy before answering.
Keep every reply to one line of JSON."""

TASK = (
    "Customer message: Where is my order ORD-1042, and can I still get a "
    "refund if I change my mind?"
)


def celeris_base_url() -> str:
    """Return the full SDK base URL, accepting legacy endpoint roots too."""
    base = (
        os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or ""
    ).rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def extract_json(text: str) -> dict | None:
    """Parse the first JSON object in the model's reply."""
    start = text.find("{")
    if start < 0:
        return None
    decoder = json.JSONDecoder()
    for index in range(start, len(text)):
        if text[index] != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            continue
    return None


def run_tool(name: str, args: dict) -> str:
    if name not in TOOLS:
        return json.dumps({"error": f"unknown tool {name!r}"})
    function, signature = TOOLS[name]
    kwargs = {key: cast(args[key]) for key, cast in signature.items() if key in args}
    try:
        return json.dumps(function(**kwargs))
    except TypeError as error:
        return json.dumps({"error": str(error)})


def run_agent(client: OpenAI, model: str) -> tuple[str | None, list]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TASK},
    ]
    step_latencies_ms = []

    for step in range(1, MAX_STEPS + 1):
        started = time.monotonic()
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=256,  # one compact JSON object; general default is 2048
            temperature=0.1,
        )
        latency_ms = (time.monotonic() - started) * 1000
        step_latencies_ms.append(latency_ms)

        reply = (response.choices[0].message.content or "").strip()
        messages.append({"role": "assistant", "content": reply})
        parsed = extract_json(reply)

        if parsed is None:
            print(f"  step {step}: {latency_ms:6.0f} ms  (unparseable, asking again)")
            messages.append({
                "role": "user",
                "content": "Reply with exactly one JSON object: a tool call or the final answer.",
            })
            continue

        if "answer" in parsed:
            print(f"  step {step}: {latency_ms:6.0f} ms  final answer")
            return str(parsed["answer"]), step_latencies_ms

        tool = parsed.get("tool", "")
        args = parsed.get("args") or {}
        result = run_tool(tool, args)
        print(f"  step {step}: {latency_ms:6.0f} ms  {tool}({json.dumps(args)})")
        messages.append({"role": "user", "content": f"TOOL RESULT {tool}: {result}"})

    return None, step_latencies_ms


def compounding_table(mean_step_ms: float) -> str:
    """Total agent wall clock at the measured per-step latency, next to a
    slower per-step latency typical of a large general model."""
    slow_step_ms = 2000.0
    lines = [
        "| steps | at measured pace | at 2 s per step |",
        "| --- | --- | --- |",
    ]
    for steps in (1, 5, 10, 20, 50):
        fast = mean_step_ms * steps / 1000
        slow = slow_step_ms * steps / 1000
        lines.append(f"| {steps} | {fast:.1f} s | {slow:.0f} s |")
    return "\n".join(lines)


def main() -> int:
    if not (os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL")):
        print("Set CELERIS_BASE_URL and CELERIS_API_KEY first.", file=sys.stderr)
        return 2

    client = OpenAI(
        base_url=celeris_base_url(),
        api_key=os.environ.get("CELERIS_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        max_retries=0,
    )
    model = os.environ.get("CELERIS_MODEL", "celeris-1")

    print("agent run:\n")
    started = time.monotonic()
    answer, step_latencies = run_agent(client, model)
    total_s = time.monotonic() - started

    print()
    if answer is None:
        print("no final answer within the step budget")
        return 1
    print(f"answer: {answer}\n")
    mean_ms = statistics.mean(step_latencies)
    print(
        f"{len(step_latencies)} model steps, mean {mean_ms:.0f} ms per step, "
        f"total {total_s:.1f} s wall clock"
    )
    print("\nhow per-step latency compounds:\n")
    print(compounding_table(mean_ms))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
