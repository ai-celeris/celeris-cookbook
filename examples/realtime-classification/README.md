# Real-time ticket routing

You want every incoming support ticket routed to the right team the moment
it arrives. A large general model takes seconds per ticket, so routing ends
up as a background batch job and the user waits. With a response in a few
hundred milliseconds, classification can sit directly in the request path:
the ticket is routed before the confirmation page renders.

This example routes tickets to one of four teams (billing, technical,
account, general) with celeris-1 and measures what that costs in latency.

## Run it

```sh docs-e2e=skip
cd examples/realtime-classification
pip install -r requirements.txt

export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
export CELERIS_API_KEY="<your-api-key>"

python3 main.py
```

## Measured results

A real run against a live workspace (2026-07-21):

```text docs-e2e=skip
routing accuracy: 10/10 (100%)
latency: p50 260 ms, p95 917 ms, max 917 ms, mean 328 ms

concurrent pass (4 workers, one burst):
  10 tickets in 1.15 s (8.7 tickets/s), p50 317 ms per ticket
```

The p95 outlier is the first request on a cold connection. Warm requests sit
between 250 and 300 ms. For comparison, a large general model typically takes
2 to 10 seconds for the same single-label decision. That is the difference
between "route it while the page loads" and "route it later in a queue".

## How it works

- One prompt per ticket asks which team should handle it and requests a
  short sentence back. celeris-1 answers bare one-word prompts unreliably
  (they often come back empty), so the parser pulls the route name out of a
  sentence instead. First route mentioned wins.
- This deliberately short classification uses `max_tokens=256`; see the
  [latency guide](../../guides/latency.md) for the 8192-token total window and
  2048-token input cap.
- The sequential pass measures the interactive path. The concurrent pass
  shows a small worker pool draining a burst.

## Where this pattern fits

Any single-label decision in a hot path: ticket routing, lead scoring,
language detection, intent detection, priority triage. If the label set fits
in one sentence and the input fits in the window, the whole decision costs
about a quarter of a second.
