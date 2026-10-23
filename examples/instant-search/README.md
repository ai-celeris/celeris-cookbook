# Instant query understanding for search

Query understanding (rewriting a vague human query into good search terms)
usually adds a second or more before retrieval even starts, so most teams
skip it and ship worse results. At around 300 ms per rewrite, it fits in
front of every search, even per keystroke pause.

This interactive app puts a Celeris-1 rewrite in front of a deliberately tiny
in-memory keyword index. It shows the literal keyword match beside the
understood result, including the rewritten terms and model time. The index is
toy; the interesting part is what the rewrite does to result quality and what
it costs in latency.

## Run it

```sh docs-e2e=skip
cd examples/instant-search
npm install

export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
export CELERIS_API_KEY="<your-api-key>"

npm start
# open http://localhost:8789
```

Type a question or use one of the examples. The app waits 250 ms after the
last keystroke and cancels stale requests, so only the latest query renders.
The original Python command-line version remains available as `main.py`.

## Measured results

A real run against a live workspace (2026-07-22). Two of five queries:

```text docs-e2e=skip
query: "why do I keep getting told to slow down"
  raw keyword match:  ['API key rotation', 'Regions and data residency', ...]
  rewritten in 1021 ms: ['rate limiting', 'throttling', 'speed', ...]
  results after rewrite: ['Error codes reference', 'Rate limits and 429 responses']

query: "hook that tells my server when stuff happens"
  raw keyword match:  ['Retry strategies', 'Streaming responses']
  rewritten in 1974 ms: ['webhook', 'callback', 'event', 'notification', 'trigger']
  results after rewrite: ['Webhook delivery']
```

Warm rewrites in this run took 290 to 310 ms; the slower entries include a
polite backoff retry after a 429. Every successful rewrite improved the
results: raw keyword matching sent "slow down" to the password page, and the
rewrite sent it to the rate-limits page where it belonged. One of five
rewrites failed to parse and the code kept the raw results, which is the
right failure mode for a search box.

## How it works

- **The rewrite is a strict-JSON call**: 3 to 6 lowercase keywords with
  synonyms and expanded abbreviations, `max_tokens` 256, temperature 0 (see
  the [latency guide](../../guides/latency.md) for budgeting rules).
- **The completion is non-streaming.** Timing covers the complete rewrite
  without depending on timing headers that may be incomplete while streaming.
- **Failure keeps the raw query.** Parse failures and repeated 429s fall
  back to the user's original terms. Search never breaks because the
  rewriter had a bad moment.
- **Debounce and cancel.** The browser starts a rewrite after a short typing
  pause and aborts in-flight work when the query changes.
- **Multi-word keywords are split** before hitting the keyword index; your
  real search engine may prefer phrases, so adapt this to its query
  language.

## Where this pattern fits

Any retrieval front door: site search, help centers, log search, product
catalogs. The same shape also works for intent detection before routing a
query to different indexes. Swap the toy index for your search engine and
keep the contract: rewrite fast, fall back to raw, never block on failure.
