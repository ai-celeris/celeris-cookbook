#!/usr/bin/env python3
"""Alert triage agent: a multi-step tool-use loop on the Celeris API.

The agent triages a synthetic production alert by calling tools over fixture
data, get_alert, search_runbooks, check_recent_deploys, then emits a
structured verdict (root-cause hypothesis, recommended action, confidence).

Tool calling here is PROMPT-DRIVEN: each turn the model must reply with one
JSON object naming a tool (or the final verdict), which the loop executes and
feeds back. This pattern works on any OpenAI-compatible endpoint, including
small, fast models without native `tools` support, and every step fits
Celeris's 4096-token window because tool results are compact by design.

Usage:
    export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
    export CELERIS_API_KEY="<your-api-key>"
    pip install -r requirements.txt
    python3 main.py            # triage the default alert (ALERT-4127)
"""

import json
import os
import re
import sys
from pathlib import Path

from openai import OpenAI

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MAX_STEPS = 8

# --- Celeris token window (see the getting-started example) -------------------

TOTAL_TOKEN_LIMIT = 4096
MIN_OUTPUT_TOKENS = 256
MAX_OUTPUT_TOKENS = 1024
OUTPUT_TOKEN_STEP = 256
ESTIMATED_BYTES_PER_TOKEN = 4


def normalize_max_tokens(requested: int) -> int:
    """Round up to a supported 256-token step, clamped to [256, 1024]."""
    if requested <= MIN_OUTPUT_TOKENS:
        return MIN_OUTPUT_TOKENS
    if requested >= MAX_OUTPUT_TOKENS:
        return MAX_OUTPUT_TOKENS
    step = OUTPUT_TOKEN_STEP
    return ((requested + step - 1) // step) * step


MAX_TOKENS = normalize_max_tokens(512)
# Everything sent to the model must fit in the remaining input budget.
INPUT_BUDGET_BYTES = (TOTAL_TOKEN_LIMIT - MAX_TOKENS - 64) * ESTIMATED_BYTES_PER_TOKEN

# --- Tools over fixture data --------------------------------------------------
# Tool results are deliberately compact: with a 4096-token window, a tool that
# returns pages of JSON would evict the reasoning that needs it.


def get_alert(alert_id: str) -> dict:
    """Fetch one alert by id."""
    alerts = json.loads((FIXTURES / "alerts.json").read_text())
    return alerts.get(alert_id) or {"error": f"unknown alert {alert_id!r}"}


def search_runbooks(query: str) -> list:
    """Keyword-match runbooks; returns id, title, and body of the top hits."""
    runbooks = json.loads((FIXTURES / "runbooks.json").read_text())
    words = set(re.findall(r"[a-z0-9-]+", query.lower()))
    scored = []
    for runbook in runbooks:
        haystack = set(k.lower() for k in runbook["keywords"])
        haystack |= set(re.findall(r"[a-z0-9-]+", runbook["title"].lower()))
        score = len(words & haystack)
        if score:
            scored.append((score, runbook))
    scored.sort(key=lambda pair: -pair[0])
    return [runbook for _, runbook in scored[:2]] or [{"error": "no matching runbooks"}]


def check_recent_deploys(service: str = "") -> list:
    """List recent deploys, optionally filtered to one service."""
    deploys = json.loads((FIXTURES / "deploys.json").read_text())
    if service:
        matched = [d for d in deploys if d["service"] == service]
        return matched or [{"error": f"no recent deploys for {service!r}"}]
    return deploys


TOOLS = {
    "get_alert": (get_alert, {"alert_id": str}),
    "search_runbooks": (search_runbooks, {"query": str}),
    "check_recent_deploys": (check_recent_deploys, {"service": str}),
}

SYSTEM_PROMPT = """You are an SRE triage agent. Investigate the alert step by step using tools.

Reply with EXACTLY ONE JSON object per turn, nothing else. Either a tool call:
  {"tool": "get_alert", "args": {"alert_id": "..."}}
  {"tool": "search_runbooks", "args": {"query": "..."}}
  {"tool": "check_recent_deploys", "args": {"service": "..."}}
or, once you have enough evidence, the final verdict:
  {"verdict": {"root_cause": "...", "evidence": ["..."], "recommended_action": "...", "confidence": "high|medium|low"}}

Rules: investigate before concluding (check the alert, at least one runbook,
and recent deploys). Cite concrete evidence (ids, versions, timestamps).
Keep every reply to one line of JSON."""


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
    kwargs = {}
    for key, cast in signature.items():
        if key in args:
            kwargs[key] = cast(args[key])
    try:
        return json.dumps(function(**kwargs))
    except TypeError as error:
        return json.dumps({"error": str(error)})


def fit_messages(messages: list) -> list:
    """Drop the oldest tool exchanges (never the system or task message) until
    the conversation fits the input budget."""
    def size(msgs):
        return sum(len(m["content"].encode("utf-8")) for m in msgs)

    kept = list(messages)
    while len(kept) > 2 and size(kept) > INPUT_BUDGET_BYTES:
        del kept[2]
    return kept


def celeris_base_url() -> str:
    """CELERIS_BASE_URL is the endpoint root (no /v1); the OpenAI SDK wants
    the versioned path, so append /v1 unless it is already there."""
    base = (
        os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or ""
    ).rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def triage(alert_id: str) -> dict | None:
    client = OpenAI(
        base_url=celeris_base_url(),
        api_key=os.environ.get("CELERIS_API_KEY") or os.environ.get("OPENAI_API_KEY"),
    )
    model = os.environ.get("CELERIS_MODEL", "celeris-1")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Triage alert {alert_id}."},
    ]

    for step in range(1, MAX_STEPS + 1):
        response = client.chat.completions.create(
            model=model,
            messages=fit_messages(messages),
            max_tokens=MAX_TOKENS,
            temperature=0.1,
        )
        reply = (response.choices[0].message.content or "").strip()
        messages.append({"role": "assistant", "content": reply})

        parsed = extract_json(reply)
        if parsed is None:
            print(f"[step {step}] unparseable reply, asking again: {reply[:120]!r}")
            messages.append({
                "role": "user",
                "content": "Reply with exactly one JSON object: a tool call or the final verdict.",
            })
            continue

        if "verdict" in parsed:
            return parsed["verdict"]

        tool = parsed.get("tool", "")
        args = parsed.get("args") or {}
        print(f"[step {step}] {tool}({json.dumps(args)})")
        result = run_tool(tool, args)
        print(f"          -> {result[:160]}{'…' if len(result) > 160 else ''}")
        messages.append({"role": "user", "content": f"TOOL RESULT {tool}: {result}"})

    return None


def main() -> int:
    if not (os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL")):
        print("Set CELERIS_BASE_URL and CELERIS_API_KEY first.", file=sys.stderr)
        return 2

    alert_id = sys.argv[1] if len(sys.argv) > 1 else "ALERT-4127"
    print(f"triaging {alert_id}\n")
    verdict = triage(alert_id)

    print()
    if verdict is None:
        print("no verdict within the step budget, try again or raise MAX_STEPS")
        return 1
    print("VERDICT")
    print(json.dumps(verdict, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
