# Instant regex, synthesized as you type

Tools that generate small formal artifacts (regexes, SQL fragments, cron
expressions, JSON schemas) feel laggy when each generation takes several
seconds. The user types, waits, loses the thread, and falls back to writing
the artifact by hand. When a synthesis lands in well under a second, the
artifact can simply track the description: pause typing, see the result.

This example is a small web app that turns a plain-English description into
a working regex on every typing pause, with a test panel that checks your
sample strings against the regex instantly in the browser.

## Run it

```sh docs-e2e=skip
cd examples/instant-suggest
npm install

export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
export CELERIS_API_KEY="<your-api-key>"

npm start
# open http://localhost:8788
```

Type a description ("a US phone number with optional area code in
parentheses"). About half a second after you stop typing, the regex appears,
and the test strings below re-check themselves against it.

## Measured results

Real runs against a live workspace (2026-07-21), end to end from the browser:

```text docs-e2e=skip
phone number pattern: synthesized in 839 ms (820 ms model time)
email pattern:        synthesized in 779 ms (767 ms model time)
date pattern:         synthesized in 844 ms (830 ms model time)
```

A regex plus a one-sentence explanation is a bigger reply than a routing
label, so synthesis costs more than the roughly 300 ms single-label calls
elsewhere in this cookbook. It is still fast enough to run on every typing
pause. At several seconds per generation this interaction pattern does not
work at all; nobody waits that long mid-keystroke.

## How it works

- **Debounce and cancel.** The browser waits 400 ms after the last
  keystroke, then calls the server. A new keystroke aborts any in-flight
  request, so only the latest description ever renders.
- **Deterministic checking in the browser.** The model proposes; the browser
  disposes. Test strings are evaluated locally with `new RegExp(...)`, so
  match results are exact, instant, and free.
- **Strict output contract.** The server asks for one JSON object
  (`{"regex": ..., "explanation": ...}`) with `max_tokens` at 256 (see the
  [latency guide](../../guides/latency.md) for the budgeting rules). Regex patterns
  are full of backslashes and the model sometimes emits them singly, which
  is invalid JSON, so the parser retries with lone backslashes doubled.
- **Same credential seam as the chatbot example.** The browser only talks to
  the local server; `config.ts` resolves the endpoint and key from the
  environment, with an optional per-request user key header. A future hosted
  demo swaps that one module.

## Where this pattern fits

Any "description to small artifact" surface: regexes, SQL WHERE clauses,
cron schedules, glob patterns, color palettes, config snippets. The recipe
is the same: debounce, cancel stale requests, validate the artifact
deterministically on the client, and keep the reply small.
