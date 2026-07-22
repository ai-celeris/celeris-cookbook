#!/usr/bin/env python3
"""Is celeris-1 a fit for YOUR task? Bring your prompts and find out.

Reads a JSONL file of tasks, runs each against celeris-1 N times, and
reports a task-fit verdict: per-task quality, latency percentiles, empty and
truncation counts, and a plain-language summary. The tool is built to tell
the truth in both directions; a poor-fit result is as useful as a good one.

Task file format (one JSON object per line):

    {"id": "route-1", "prompt": "...", "checker": "label_set",
     "labels": ["billing", "technical"], "expected": "billing",
     "max_tokens": 256}

max_tokens is optional and defaults to 2048. Set it lower when the task
explicitly asks for a short output.

Checkers:
    exact       reply equals "expected" (after trimming)
    contains    reply contains "expected" (case-insensitive)
    json_keys   reply parses as JSON containing all keys in "expected_keys"
    label_set   exactly the "expected" label from "labels" appears in the reply
    none        no objective check; latency and reliability only

Usage:
    export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
    export CELERIS_API_KEY="<your-api-key>"
    pip install -r requirements.txt
    python3 main.py tasks/good-fit-classification.jsonl
    python3 main.py your-tasks.jsonl --repetitions 5
"""

import argparse
import importlib.util
import json
import os
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Reuse the benchmark harness internals (measurement loop, checkers,
# percentiles) instead of duplicating them.
_spec = importlib.util.spec_from_file_location(
    "cookbook_benchmark", HERE.parent / "benchmark" / "main.py"
)
benchmark = importlib.util.module_from_spec(_spec)
sys.modules["cookbook_benchmark"] = benchmark
_spec.loader.exec_module(benchmark)


def exact_checker(expected: str):
    def check(output: str) -> bool:
        return output.strip() == expected.strip()

    return check


def label_set_checker(labels: list, expected: str):
    lowered_labels = [label.lower() for label in labels]

    def check(output: str) -> bool:
        found = {label for label in lowered_labels if label in output.lower()}
        return found == {expected.lower()}

    return check


def build_checker(spec: dict):
    checker = spec.get("checker", "none")
    if checker == "exact":
        return exact_checker(str(spec["expected"]))
    if checker == "contains":
        return benchmark.answer_checker(str(spec["expected"]).lower())
    if checker == "json_keys":
        return benchmark.json_checker(list(spec["expected_keys"]))
    if checker == "label_set":
        return label_set_checker(list(spec["labels"]), str(spec["expected"]))
    if checker == "none":
        return None
    raise ValueError(f"unknown checker {checker!r} in task {spec.get('id')!r}")


def load_tasks(path: Path) -> list:
    tasks = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        spec = json.loads(line)
        tasks.append(
            {
                "id": str(spec.get("id", f"task-{line_number}")),
                "task": benchmark.Task(
                    category=str(spec.get("checker", "none")),
                    prompt=str(spec["prompt"]),
                    max_tokens=benchmark.max_output_tokens(
                        int(spec["max_tokens"]) if "max_tokens" in spec else None
                    ),
                    checker=build_checker(spec),
                ),
            }
        )
    return tasks


def verdict_for(accuracy: float | None, empty_rate: float, truncated: int) -> tuple:
    reasons = []
    if empty_rate > 0.05:
        reasons.append(f"empty replies on {empty_rate:.0%} of runs")
    if truncated:
        reasons.append(f"{truncated} truncated replies (raise max_tokens)")
    if accuracy is None:
        return ("unchecked", reasons or ["no objective checker; judge quality by eye"])
    if accuracy >= 0.9 and empty_rate <= 0.05:
        return ("strong fit", reasons or ["accurate and reliable across repetitions"])
    if accuracy >= 0.6:
        reasons.insert(0, f"accuracy {accuracy:.0%}; tune the prompt or add a repair step")
        return ("partial fit", reasons)
    reasons.insert(0, f"accuracy {accuracy:.0%}; this task likely needs a larger model")
    return ("poor fit", reasons)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task_file", type=Path, help="JSONL task file")
    parser.add_argument("--repetitions", type=int, default=3, help="runs per task (default 3)")
    args = parser.parse_args()

    if not (os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL")):
        print("Set CELERIS_BASE_URL and CELERIS_API_KEY first.", file=sys.stderr)
        return 2

    from openai import OpenAI

    client = OpenAI(
        base_url=benchmark.celeris_base_url(),
        api_key=os.environ.get("CELERIS_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        max_retries=0,
    )
    model = os.environ.get("CELERIS_MODEL", "celeris-1")

    tasks = load_tasks(args.task_file)
    print(f"{len(tasks)} tasks x {args.repetitions} repetitions against {model}\n")

    all_latencies = []
    rows = [
        "| task | checker | accuracy | p50 ms | empties | verdict |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    fit_counts = {"strong fit": 0, "partial fit": 0, "poor fit": 0, "unchecked": 0}
    worst_reasons = []

    for entry in tasks:
        samples = []
        for _ in range(args.repetitions):
            samples.append(benchmark.run_once(client, model, entry["task"]))
            time.sleep(0.4)
        ok = [sample for sample in samples if sample.ok]
        latencies = [sample.total_ms for sample in ok]
        all_latencies.extend(latencies)
        checked = [sample for sample in ok if sample.correct is not None]
        accuracy = (
            sum(1 for sample in checked if sample.correct) / len(checked) if checked else None
        )
        empty_rate = sum(1 for sample in ok if sample.empty) / max(len(ok), 1)
        truncated = sum(1 for sample in ok if sample.truncated)

        verdict, reasons = verdict_for(accuracy, empty_rate, truncated)
        fit_counts[verdict] += 1
        if verdict == "poor fit":
            worst_reasons.append(f"{entry['id']}: {reasons[0]}")
        accuracy_text = f"{accuracy:.0%}" if accuracy is not None else "n/a"
        rows.append(
            f"| {entry['id']} | {entry['task'].category} | {accuracy_text} "
            f"| {benchmark.percentile(latencies, 0.5):.0f} "
            f"| {sum(1 for sample in ok if sample.empty)} | {verdict} |"
        )

    print("\n".join(rows))
    print()
    print(
        f"latency across all runs: p50 {benchmark.percentile(all_latencies, 0.5):.0f} ms, "
        f"p95 {benchmark.percentile(all_latencies, 0.95):.0f} ms, "
        f"mean {statistics.mean(all_latencies):.0f} ms"
        if all_latencies
        else "no successful runs"
    )

    checked_tasks = len(tasks) - fit_counts["unchecked"]
    strong = fit_counts["strong fit"]
    print()
    if checked_tasks == 0:
        print("SUMMARY: no objective checkers supplied; review outputs by eye.")
    elif strong == checked_tasks:
        print("SUMMARY: strong fit. Every checked task met the accuracy bar; run your real traffic next.")
    elif fit_counts["poor fit"] == 0:
        print("SUMMARY: partial fit. No task failed outright, but some need prompt work or a repair step.")
    else:
        print(
            f"SUMMARY: mixed. {strong}/{checked_tasks} checked tasks are a strong fit; "
            f"{fit_counts['poor fit']} look wrong for a fast small model. "
            "Consider the cascade pattern: fast model for the fits, larger model for the rest."
        )
        for reason in worst_reasons:
            print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
