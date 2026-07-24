# Benchmark harness

A mini benchmark you can run against **your own Celeris workspace** in under a
minute: 16 built-in tasks across four categories (summarize, extract-JSON,
classify, short-answer), N repetitions at configurable concurrency, and a
Markdown report of latency, reliability, and correctness.

What it measures per request:

- **Latency**: time-to-first-token and total (p50/p90/p99/mean). celeris-1
  usually delivers the whole reply in one burst, so TTFT equals total in
  practice (see the [latency guide](../../guides/latency.md)).
- **Reliability**: throttles (429s, retried with backoff and counted),
  transport/HTTP errors, empty outputs, truncation (`finish_reason=length`).
- **Correctness** where tasks are objectively checkable: extracted JSON must
  parse and contain the required keys, classifications must name exactly the
  right label, short answers must contain the expected value. Summaries have
  no objective check and are reported n/a.

## Run it

```sh docs-e2e=skip
cd examples/benchmark
pip install -r requirements.txt

export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
export CELERIS_API_KEY="<your-api-key>"

python3 main.py                          # 48 requests: 16 tasks x 3, concurrency 3
python3 main.py --repetitions 5 --concurrency 2
```

Mind your workspace's rate limit: this is a smoke-scale benchmark, not a load
test. 429s are retried (up to twice, with backoff) and reported.

## Sample output

A real run against a live workspace (2026-07-21, concurrency 2):

```text docs-e2e=skip
model celeris-1 · 48 requests (3x16 tasks) · concurrency 2

completed 48/48 requests
```

> ## Benchmark summary
>
> - requests: 48 (48 ok, 0 failed) in 24.8s
> - throttled (429): 6 · retries: 6 · empty outputs: 2 · truncated (length): 0
>
> | metric | p50 | p90 | p99 | mean |
> | --- | --- | --- | --- | --- |
> | total (ms) | 687 | 718 | 1023 | 666 |
> | ttft (ms) | 686 | 717 | 1023 | 665 |
>
> | category | requests | correct | correctness |
> | --- | --- | --- | --- |
> | summarize | 12 | - | n/a (no objective check) |
> | extract-json | 12 | 12 | 12/12 (100%) |
> | classify | 12 | 10 | 10/12 (83%) |
> | short-answer | 12 | 12 | 12/12 (100%) |
>
> _TTFT ≈ total is expected: celeris-1 is a diffusion model and usually
> delivers the whole reply in one burst._

## Prompt-phrasing note (worth reading before you edit the tasks)

Prompts that demand a **bare single-word or single-number answer** ("Reply
with just the number") frequently return an *empty* completion from celeris-1
(`completion_tokens=1`, `finish_reason=stop`). Sentence-eliciting phrasings
("Answer in a short sentence") respond reliably, so the built-in tasks use
those, and the empty-output counter surfaces the defect whenever it shows up
anyway. If you add your own tasks, prefer sentence-shaped answers and let the
checkers do substring/label matching.
