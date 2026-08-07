#!/usr/bin/env python3
"""Mini benchmark harness for the Celeris API.

Run a small built-in task set (summarize / extract-JSON / classify /
short-answer) against your own workspace and get a latency + reliability +
correctness report you can paste anywhere (the summary is Markdown).

Measures per request: time-to-first-token and total latency (Celeris-1 is a
diffusion model that usually delivers the whole reply in one burst, so TTFT
tends to equal total, it is measured anyway), throttles (429s), retries,
transport/HTTP errors, empty outputs, and truncation (finish_reason=length).
Tasks with checkable answers (JSON parses + required keys, classification
label match, short-answer match) are scored for correctness.

Usage:
    export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
    export CELERIS_API_KEY="<your-api-key>"
    pip install -r requirements.txt
    python3 main.py                     # 16 tasks x 3 repetitions, concurrency 3
    python3 main.py --repetitions 5 --concurrency 2
"""

import argparse
import json
import os
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from openai import APIError, APIStatusError, OpenAI

# --- Celeris conventions (see the getting-started example) --------------------

TOTAL_TOKEN_LIMIT = 8192
DEFAULT_MAX_OUTPUT_TOKENS = 2048
OUTPUT_TOKEN_BLOCK = 256
SHORT_OUTPUT_TOKENS = 256


def max_output_tokens(requested: int | None = None) -> int:
    """Use the 2048-token default or validate an explicit output budget."""
    value = DEFAULT_MAX_OUTPUT_TOKENS if requested is None else requested
    if value <= 0 or value % OUTPUT_TOKEN_BLOCK:
        raise ValueError("max_tokens must be a positive multiple of 256")
    if value >= TOTAL_TOKEN_LIMIT:
        raise ValueError("max_tokens must leave room for the prompt")
    return value


def input_token_budget(max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS) -> int:
    """Maximum prompt tokens left after the output reservation."""
    return TOTAL_TOKEN_LIMIT - max_output_tokens(max_tokens)


def celeris_base_url() -> str:
    """Return the full SDK base URL, accepting legacy endpoint roots too."""
    base = (
        os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or ""
    ).rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


# --- Task set -----------------------------------------------------------------
# 16 short tasks in 4 categories. Checkers return True/False; None means the
# category has no objective check (reported as n/a).

SUMMARIZE_TEXTS = [
    "The deploy at 03:25 switched the payment client from asynchronous reconciliation to synchronous retries with three attempts. Sixteen minutes later, checkout p99 latency crossed two seconds and paged the on-call engineer, while p50 and the error rate stayed flat.",
    "Diffusion language models generate whole token canvases in parallel denoising steps instead of emitting tokens one at a time. This trades the familiar streaming behavior for dramatically lower end-to-end latency on short, structured outputs.",
    "The migration moved trace storage from per-host JSONL files to a shared object store with daily partitions. Query latency improved for cross-host investigations, but per-request write amplification doubled, so the team added client-side batching before rollout.",
    "Customer support tickets spiked after the pricing page A/B test shipped a variant that hid the free-tier column on mobile. Rolling the variant back restored the baseline within an hour, and the experiment was rerun with a fixed layout the following week.",
]

EXTRACT_PROMPTS = [
    ('Extract as JSON with keys "name", "quantity", "unit": Add three cups of flour to the bowl. Reply with ONLY the JSON object.', ["name", "quantity", "unit"]),
    ('Extract as JSON with keys "city", "temperature_c": It was 31 degrees Celsius in Sydney this afternoon. Reply with ONLY the JSON object.', ["city", "temperature_c"]),
    ('Extract as JSON with keys "service", "version": The incident started right after checkout-api 2026.07.21-1 rolled out. Reply with ONLY the JSON object.', ["service", "version"]),
    ('Extract as JSON with keys "product", "price_usd": The mechanical keyboard sells for 129 US dollars. Reply with ONLY the JSON object.', ["product", "price_usd"]),
]

# NOTE on phrasing: prompts that demand a BARE single-word/number answer
# ("Reply with just the number") frequently return an EMPTY completion from
# Celeris-1 (completion_tokens=1, finish_reason=stop). Sentence-eliciting
# phrasings answer reliably, so the tasks use those; the empty-output counter
# still catches the defect whenever it occurs.

CLASSIFY_PROMPTS = [
    ("The new dashboard is fantastic, setup took two minutes and everything just worked.", "positive"),
    ("Support never replied and the invoice was wrong twice in a row.", "negative"),
    ("The meeting has been moved from Tuesday to Wednesday afternoon.", "neutral"),
    ("I love how fast the responses are, genuinely impressive work.", "positive"),
]

SHORT_ANSWER_PROMPTS = [
    ("What is 17 + 25? Answer in a short sentence.", "42"),
    ("What is the capital of France? Answer in a short sentence.", "paris"),
    ("How many minutes are in two and a half hours? Answer in a short sentence.", "150"),
    ("How many days are in April? Answer in a short sentence.", "30"),
]


@dataclass
class Task:
    category: str
    prompt: str
    max_tokens: int
    checker: object = None  # callable(str) -> bool, or None


def json_checker(required_keys):
    def check(output: str) -> bool:
        # Tolerate a fenced code block around the JSON.
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", output.strip())
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            return False
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, dict) and all(key in parsed for key in required_keys)

    return check


def label_checker(expected: str):
    labels = {"positive", "negative", "neutral"}

    def check(output: str) -> bool:
        found = {label for label in labels if label in output.lower()}
        return found == {expected}

    return check


def answer_checker(expected: str):
    def check(output: str) -> bool:
        return expected in output.strip().lower()

    return check


def build_tasks() -> list:
    tasks = []
    for text in SUMMARIZE_TEXTS:
        tasks.append(Task("summarize", f"Summarize in one sentence: {text}", SHORT_OUTPUT_TOKENS))
    for prompt, keys in EXTRACT_PROMPTS:
        tasks.append(Task("extract-json", prompt, SHORT_OUTPUT_TOKENS, json_checker(keys)))
    for text, label in CLASSIFY_PROMPTS:
        tasks.append(
            Task(
                "classify",
                f"What is the sentiment of this message, positive, negative, or neutral? Answer in a short sentence. Message: {text}",
                SHORT_OUTPUT_TOKENS,
                label_checker(label),
            )
        )
    for prompt, answer in SHORT_ANSWER_PROMPTS:
        tasks.append(Task("short-answer", prompt, SHORT_OUTPUT_TOKENS, answer_checker(answer)))
    return tasks


# --- Measurement --------------------------------------------------------------

MAX_ATTEMPTS = 3  # 1 initial + up to 2 retries, 429s only


@dataclass
class Sample:
    category: str
    ok: bool = False
    ttft_ms: float = 0.0
    total_ms: float = 0.0
    throttles: int = 0
    retries: int = 0
    error: str = ""
    empty: bool = False
    truncated: bool = False
    correct: object = None  # True/False, or None when uncheckable


def run_once(client: OpenAI, model: str, task: Task) -> Sample:
    sample = Sample(category=task.category)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        started = time.monotonic()
        first_token_at = None
        text_parts = []
        finish_reason = None
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": task.prompt}],
                max_tokens=task.max_tokens,
                temperature=0.1,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.delta and choice.delta.content:
                    if first_token_at is None:
                        first_token_at = time.monotonic()
                    text_parts.append(choice.delta.content)
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
        except APIStatusError as error:
            if error.status_code == 429 and attempt < MAX_ATTEMPTS:
                sample.throttles += 1
                sample.retries += 1
                time.sleep(2.0 * attempt)
                continue
            sample.error = "throttle" if error.status_code == 429 else f"http_{error.status_code}"
            return sample
        except APIError:
            sample.error = "transport"
            return sample

        ended = time.monotonic()
        output = "".join(text_parts)
        sample.ok = True
        sample.total_ms = (ended - started) * 1000
        sample.ttft_ms = ((first_token_at or ended) - started) * 1000
        sample.empty = not output.strip()
        sample.truncated = finish_reason == "length"
        if task.checker is not None:
            sample.correct = bool(task.checker(output))
        return sample
    return sample


def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def summarize(samples: list, elapsed_s: float) -> str:
    ok = [s for s in samples if s.ok]
    totals = [s.total_ms for s in ok]
    ttfts = [s.ttft_ms for s in ok]
    lines = [
        "## Benchmark summary",
        "",
        f"- requests: {len(samples)} ({len(ok)} ok, {len(samples) - len(ok)} failed) in {elapsed_s:.1f}s",
        (
            f"- throttled (429): {sum(s.throttles for s in samples)} · retries: {sum(s.retries for s in samples)}"
            f" · empty outputs: {sum(1 for s in ok if s.empty)} · truncated (length): {sum(1 for s in ok if s.truncated)}"
        ),
        "",
        "| metric | p50 | p90 | p99 | mean |",
        "| --- | --- | --- | --- | --- |",
        f"| total (ms) | {percentile(totals, 0.5):.0f} | {percentile(totals, 0.9):.0f} | {percentile(totals, 0.99):.0f} | {statistics.mean(totals):.0f} |" if totals else "| total (ms) | - | - | - | - |",
        f"| ttft (ms) | {percentile(ttfts, 0.5):.0f} | {percentile(ttfts, 0.9):.0f} | {percentile(ttfts, 0.99):.0f} | {statistics.mean(ttfts):.0f} |" if ttfts else "| ttft (ms) | - | - | - | - |",
        "",
        "| category | requests | correct | correctness |",
        "| --- | --- | --- | --- |",
    ]
    for category in ("summarize", "extract-json", "classify", "short-answer"):
        rows = [s for s in ok if s.category == category]
        checked = [s for s in rows if s.correct is not None]
        if checked:
            correct = sum(1 for s in checked if s.correct)
            score = f"{correct}/{len(checked)} ({100 * correct / len(checked):.0f}%)"
        else:
            score = "n/a (no objective check)"
        lines.append(f"| {category} | {len(rows)} | {sum(1 for s in checked if s.correct)} | {score} |" if checked else f"| {category} | {len(rows)} | - | {score} |")
    lines.append("")
    lines.append("_TTFT ≈ total is expected: Celeris-1 is a diffusion model and usually delivers the whole reply in one burst._")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repetitions", type=int, default=3, help="runs per task (default 3)")
    parser.add_argument("--concurrency", type=int, default=3, help="parallel requests (default 3)")
    args = parser.parse_args()

    if not (os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL")):
        print("Set CELERIS_BASE_URL and CELERIS_API_KEY first.", file=sys.stderr)
        return 2

    client = OpenAI(
        base_url=celeris_base_url(),
        api_key=os.environ.get("CELERIS_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        max_retries=0,  # retries are counted explicitly above
    )
    model = os.environ.get("CELERIS_MODEL", "celeris-1")

    work = build_tasks() * args.repetitions
    print(f"model {model} · {len(work)} requests ({args.repetitions}x{len(build_tasks())} tasks) · concurrency {args.concurrency}\n")

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        samples = list(pool.map(lambda task: run_once(client, model, task), work))
    elapsed = time.monotonic() - started

    done = sum(1 for s in samples if s.ok)
    print(f"completed {done}/{len(samples)} requests\n")
    print(summarize(samples, elapsed))
    return 0 if done == len(samples) else 1


if __name__ == "__main__":
    raise SystemExit(main())
