#!/usr/bin/env python3
"""Structured extraction over a document set, fast enough to not batch.

Extracts vendor, invoice number, total, and due date from a synthetic corpus
of messy invoice snippets with asyncio concurrency. Measures documents per
minute at several concurrency levels, counts throttles and repairs, and
scores field accuracy against the known ground truth.

Usage:
    export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
    export CELERIS_API_KEY="<your-api-key>"
    pip install -r requirements.txt
    python3 main.py                       # 40 docs at each of concurrency 1, 4, 8
    python3 main.py --docs 20 --levels 1 4
"""

import argparse
import asyncio
import json
import os
import random
import re
import statistics
import sys
import time

from openai import APIStatusError, AsyncOpenAI

# --- Synthetic corpus ---------------------------------------------------------
# Deterministic (seeded) messy invoice snippets with known ground truth.

VENDORS = [
    "Northwind Traders", "Acme Supply Co", "Globex Industrial", "Initech Services",
    "Umbrella Logistics", "Stark Components", "Wayne Fabrication", "Tyrell Materials",
]

TEMPLATES = [
    "INVOICE {number}\nFrom: {vendor}\nAmount due: ${total}\nPayment due by {date}.",
    "{vendor} - TAX INVOICE\nRef: {number}\nTOTAL: {total} USD\nDue: {date}",
    "invoice #{number} // {vendor}\ntotal owing ${total} ... please pay before {date}",
    "Bill from {vendor}.\nInvoice number {number}. Balance of ${total} is payable by {date}.",
    "*** {vendor} ***\nDoc: {number}\nAmt: ${total}\nTerms: net, due {date}",
]


def build_corpus(count: int) -> list:
    rng = random.Random(42)
    corpus = []
    for i in range(count):
        vendor = rng.choice(VENDORS)
        number = f"INV-{rng.randint(10000, 99999)}"
        total = round(rng.uniform(40, 9500), 2)
        date = f"2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        text = rng.choice(TEMPLATES).format(
            vendor=vendor, number=number, total=f"{total:,.2f}", date=date
        )
        corpus.append({
            "text": text,
            "truth": {"vendor": vendor, "invoice_number": number, "total_usd": total, "due_date": date},
        })
    return corpus


# --- Celeris conventions ------------------------------------------------------

def celeris_base_url() -> str:
    """CELERIS_BASE_URL is the endpoint root (no /v1). The OpenAI SDK wants
    the versioned path, so append /v1 unless it is already there."""
    base = (
        os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or ""
    ).rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


PROMPT = (
    "Extract from this invoice text as JSON with keys "
    '"vendor" (string), "invoice_number" (string), "total_usd" (number), '
    '"due_date" (YYYY-MM-DD string). Reply with ONLY the JSON object.\n\n'
)

REPAIR_PROMPT = (
    "Fix this into ONE valid JSON object with keys "
    '"vendor", "invoice_number", "total_usd", "due_date". '
    "Reply with ONLY the JSON object.\n\n"
)


def parse_extraction(output: str) -> dict | None:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", output.strip())
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    required = {"vendor", "invoice_number", "total_usd", "due_date"}
    return parsed if required.issubset(parsed) else None


def fields_correct(extracted: dict, truth: dict) -> int:
    """Count correct fields out of 4, tolerant of formatting noise."""
    correct = 0
    if str(extracted.get("vendor", "")).strip().lower() == truth["vendor"].lower():
        correct += 1
    if str(extracted.get("invoice_number", "")).strip().upper() == truth["invoice_number"]:
        correct += 1
    try:
        value = float(str(extracted.get("total_usd", "")).replace(",", "").replace("$", ""))
        if abs(value - truth["total_usd"]) < 0.01:
            correct += 1
    except ValueError:
        pass
    if str(extracted.get("due_date", "")).strip() == truth["due_date"]:
        correct += 1
    return correct


# --- The extraction pass ------------------------------------------------------

MAX_RETRIES = 2  # 429s only, polite backoff


class Stats:
    def __init__(self):
        self.latencies_ms = []
        self.throttles = 0
        self.repairs = 0
        self.failures = 0
        self.fields_total = 0
        self.fields_correct = 0


async def call_model(client: AsyncOpenAI, model: str, prompt: str, stats: Stats) -> str | None:
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,  # small extraction object; general default is 2048
                temperature=0.0,
            )
            return response.choices[0].message.content or ""
        except APIStatusError as error:
            if error.status_code == 429 and attempt < MAX_RETRIES:
                stats.throttles += 1
                await asyncio.sleep(2.0 * (attempt + 1))
                continue
            return None
    return None


async def extract_one(client: AsyncOpenAI, model: str, doc: dict, stats: Stats, gate: asyncio.Semaphore) -> None:
    async with gate:
        started = time.monotonic()
        output = await call_model(client, model, PROMPT + doc["text"], stats)
        extracted = parse_extraction(output) if output is not None else None
        if extracted is None and output:
            # Cheap-repair pattern: one more fast call to fix the formatting
            # costs a few hundred milliseconds, far less than losing the doc.
            stats.repairs += 1
            repaired = await call_model(client, model, REPAIR_PROMPT + output, stats)
            extracted = parse_extraction(repaired) if repaired is not None else None
        stats.latencies_ms.append((time.monotonic() - started) * 1000)

        stats.fields_total += 4
        if extracted is None:
            stats.failures += 1
        else:
            stats.fields_correct += fields_correct(extracted, doc["truth"])


async def run_level(corpus: list, concurrency: int) -> tuple:
    client = AsyncOpenAI(
        base_url=celeris_base_url(),
        api_key=os.environ.get("CELERIS_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        max_retries=0,
    )
    model = os.environ.get("CELERIS_MODEL", "celeris-1")
    stats = Stats()
    gate = asyncio.Semaphore(concurrency)

    started = time.monotonic()
    await asyncio.gather(*(extract_one(client, model, doc, stats, gate) for doc in corpus))
    elapsed = time.monotonic() - started
    await client.close()
    return stats, elapsed


def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


async def main_async(args) -> int:
    corpus = build_corpus(args.docs)
    print(f"{args.docs} synthetic invoices per level, levels {args.levels}\n")

    rows = [
        "| concurrency | docs/min | p50 ms/doc | mean ms/doc | throttles | repairs | failures | field accuracy |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for level in args.levels:
        print(f"concurrency {level}: running...")
        stats, elapsed = await run_level(corpus, level)
        docs_per_min = args.docs / elapsed * 60
        accuracy = 100 * stats.fields_correct / stats.fields_total
        rows.append(
            f"| {level} | {docs_per_min:.0f} | {percentile(stats.latencies_ms, 0.5):.0f} "
            f"| {statistics.mean(stats.latencies_ms):.0f} | {stats.throttles} "
            f"| {stats.repairs} | {stats.failures} | {accuracy:.0f}% |"
        )
        print(f"  {args.docs} docs in {elapsed:.1f} s ({docs_per_min:.0f} docs/min)")
        await asyncio.sleep(3)  # let the workspace breathe between levels

    print("\n## Extraction throughput\n")
    print("\n".join(rows))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--docs", type=int, default=40, help="documents per concurrency level (default 40)")
    parser.add_argument("--levels", type=int, nargs="+", default=[1, 4, 8], help="concurrency levels (default 1 4 8)")
    args = parser.parse_args()

    if not (os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL")):
        print("Set CELERIS_BASE_URL and CELERIS_API_KEY first.", file=sys.stderr)
        return 2
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
