#!/usr/bin/env python3
"""Real-time ticket routing with celeris-1.

Routes support tickets to the right team fast enough to sit inside an
interactive request path. Measures per-request latency and short-burst
throughput, and scores routing accuracy against expected labels.

Usage:
    export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
    export CELERIS_API_KEY="<your-api-key>"
    pip install -r requirements.txt
    python3 main.py
"""

import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

ROUTES = ("billing", "technical", "account", "general")

# (ticket text, expected route)
TICKETS = [
    ("I was charged twice for my subscription this month and need a refund.", "billing"),
    ("The API returns a 502 error on every request since this morning.", "technical"),
    ("How do I add a teammate to my workspace?", "account"),
    ("What are your support hours over the holidays?", "general"),
    ("My invoice shows the wrong company name and tax number.", "billing"),
    ("Streaming responses cut off after the first chunk in our integration.", "technical"),
    ("Please change the email address on my account to my new work one.", "account"),
    ("Do you have a status page I can subscribe to?", "general"),
    ("Why did my plan price change without notice?", "billing"),
    ("Requests from our EU region time out but US requests work fine.", "technical"),
]


def celeris_base_url() -> str:
    """CELERIS_BASE_URL is the endpoint root (no /v1). The OpenAI SDK wants
    the versioned path, so append /v1 unless it is already there."""
    base = (
        os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or ""
    ).rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def build_prompt(ticket: str) -> str:
    # Sentence-style answers are reliable on celeris-1. Prompts that demand a
    # bare one-word answer often come back empty, so ask for a short sentence
    # and parse the route out of it.
    return (
        "Which team should handle this support ticket: billing, technical, "
        f"account, or general? Answer in a short sentence. Ticket: {ticket}"
    )


def parse_route(output: str) -> str | None:
    """Return the first route named in the reply. Replies are short sentences
    like "This is a billing issue", so first mention wins."""
    lowered = output.lower()
    positions = [(lowered.find(route), route) for route in ROUTES if route in lowered]
    return min(positions)[1] if positions else None


def classify(client: OpenAI, model: str, ticket: str) -> tuple[str | None, float]:
    started = time.monotonic()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": build_prompt(ticket)}],
        max_tokens=256,  # one routing label; general default is 2048
        temperature=0.1,
    )
    latency_ms = (time.monotonic() - started) * 1000
    return parse_route(response.choices[0].message.content or ""), latency_ms


def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


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

    # Pass 1: sequential, the shape of an interactive request path.
    print("sequential pass (one ticket at a time):\n")
    latencies = []
    correct = 0
    for ticket, expected in TICKETS:
        route, latency_ms = classify(client, model, ticket)
        latencies.append(latency_ms)
        mark = "ok " if route == expected else "MISS"
        if route == expected:
            correct += 1
        print(f"  [{mark}] {latency_ms:6.0f} ms  {route or '?':9}  {ticket[:56]}")
        time.sleep(0.3)

    print()
    print(
        f"routing accuracy: {correct}/{len(TICKETS)} "
        f"({100 * correct / len(TICKETS):.0f}%)"
    )
    print(
        f"latency: p50 {percentile(latencies, 0.5):.0f} ms, "
        f"p95 {percentile(latencies, 0.95):.0f} ms, "
        f"max {max(latencies):.0f} ms, mean {statistics.mean(latencies):.0f} ms"
    )

    # Pass 2: a short concurrent burst, the shape of a busy queue.
    print("\nconcurrent pass (4 workers, one burst):\n")
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda t: classify(client, model, t[0]), TICKETS))
    elapsed = time.monotonic() - started
    burst_latencies = [latency for _, latency in results]
    print(
        f"  {len(TICKETS)} tickets in {elapsed:.2f} s "
        f"({len(TICKETS) / elapsed:.1f} tickets/s), "
        f"p50 {percentile(burst_latencies, 0.5):.0f} ms per ticket"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
