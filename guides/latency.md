# Understanding latency with Celeris-1

This guide explains how to measure, budget, and design for latency on the
Celeris API. The examples in this cookbook link here instead of repeating
it. Two facts drive everything else:

1. Celeris-1 is a diffusion model. It generates the whole reply in parallel
   and usually delivers it as **one burst**, not token by token.
2. Requests have an **8192-token total window**. An explicit `max_tokens` must
   be a positive multiple of **256**; when omitted, it defaults to **2048**.

## The vocabulary

- **Time to first token (TTFT)**: from sending the request to the first
  byte of the reply.
- **Total latency**: from sending the request to the last byte.
- **Tokens per second**: output tokens divided by the streaming window
  (total minus TTFT).

On token-by-token models these three numbers tell different stories: TTFT
sets how soon something appears, tokens per second sets how long the user
watches text arrive. On Celeris-1 they collapse: **TTFT equals total** in
practice, and tokens per second over a near-zero streaming window is not a
meaningful number.

Measured on a live workspace (2026-07-21): a full multi-sentence chat reply
in 250 to 300 ms end to end, first token at 319 ms with the full reply 2 ms
later, single-label classification at 260 ms median, benchmark p50 across
mixed tasks at 687 ms total with TTFT within 1 ms of total in every sample.

## Decomposing a request

Wall clock for one request is roughly:

```text docs-e2e=skip
total = network round trip + server time
```

- **Network round trip** is yours: client to endpoint and back, plus TLS
  setup on the first request. Cold first requests in our runs cost 700 to
  1100 ms; warm requests on a kept-alive connection add tens of
  milliseconds. Reuse connections (the OpenAI SDK does this for you).
- **Server time** scales mainly with output length. Short labels and small
  JSON objects return in about 250 to 300 ms; a regex with an explanation
  (about 50 to 80 tokens) runs 750 to 850 ms; long replies near the
  max_tokens cap run around 1 second.

The practical rules: keep replies as short as the task allows, and keep the
connection warm.

### Prewarm before the first user request

For latency-sensitive browser apps, start the connection while the user is
reading or typing rather than after they click. An author-issued `OPTIONS` with
the same non-safelisted header names as the eventual request makes the browser
perform and cache the real CORS preflight, while also establishing DNS and TLS:

```ts docs-e2e=skip
const chatUrl = `${baseUrl}/chat/completions`;

fetch(chatUrl, {
  method: "OPTIONS",
  mode: "cors",
  credentials: "omit",
  headers: {
    Authorization: "Bearer cors-preflight-warmup",
    "Content-Type": "application/json",
  },
}).catch(() => {}); // best effort; never block the UI
```

If your application has a server, also send an authenticated
small `POST` to `/<model>/echo` during startup. `/echo` returns the request body,
does not invoke the model, and does not consume inference quota; it establishes
the server-to-Celeris connection before the first completion. Apply a
timeout, deduplicate concurrent warm-ups, and ignore failures. The real request
remains the source of truth.

```ts docs-e2e=skip
const modelUrl = baseUrl.replace(/\/v1\/?$/, "");

await fetch(`${modelUrl}/echo`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.CELERIS_API_KEY}`,
    "Content-Type": "text/plain",
  },
  body: "warm",
  signal: AbortSignal.timeout(5000),
}).catch(() => {});
```

Keep this authenticated call on your server. Do not put an API key into
browser JavaScript to prewarm a connection.

## Design for the burst

Because the reply arrives whole:

- **Streaming buys API symmetry, not progress.** `stream: true` works, but
  all chunks arrive together at the end. Do not build progressive rendering
  and typing effects; there is nothing incremental to show.
- **Show, then explain.** Render the complete answer the moment it lands.
  If you want motion for feel, animate after arrival, not while waiting.
- **Measure TTFT anyway.** It is your proof of the burst: if TTFT stops
  equaling total, delivery behavior changed and your client should know.

## Budgeting the token window

One request has 8192 tokens for input and requested output combined.
`max_tokens` reserves the output canvas. It must be a positive multiple of
256, and the service uses 2048 when you omit it. The input budget is whatever
remains after that reservation:

```python docs-e2e=skip
TOTAL_TOKEN_LIMIT = 8192
DEFAULT_MAX_OUTPUT_TOKENS = 2048
OUTPUT_TOKEN_BLOCK = 256


def output_token_budget(requested: int | None = None) -> int:
    """Apply the service default and validate an explicit reservation."""
    value = DEFAULT_MAX_OUTPUT_TOKENS if requested is None else requested
    if value <= 0 or value % OUTPUT_TOKEN_BLOCK:
        raise ValueError("max_tokens must be a positive multiple of 256")
    if value >= TOTAL_TOKEN_LIMIT:
        raise ValueError("max_tokens must leave room for the prompt")
    return value


def input_token_budget(max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS) -> int:
    """Maximum prompt tokens left after the output reservation."""
    return TOTAL_TOKEN_LIMIT - output_token_budget(max_tokens)
```

With the default 2048-token output reservation, up to 6144 tokens remain for
the prompt. A short classification requesting 256 output tokens leaves 7936
tokens. A large, block-aligned 6912-token output reservation leaves 1280
tokens. Chat-template overhead counts against those input budgets.

Celeris does not expose its tokenizer. Estimate about 4 bytes per token,
leave an allowance for the chat template (the cookbook helpers use 8 tokens
plus 4 per message), and clip long input **before** sending. The API will
not clip for you; an oversized request fails.

Two budgeting habits from the examples:

- **Reserve only what the task needs.** Labels, compact verdicts, and tool
  calls deliberately reserve 256 or 512. Omit the field when the 2048-token
  service default is appropriate.
- **Drop oldest first.** Chat history and agent transcripts should evict
  their oldest turns, never the system prompt or the newest message.

## Choosing an endpoint

Use the global base URL unless you have a reason to prefer a region:

```text docs-e2e=skip
https://inference.celeris.ai/celeris-1/v1
```

For latency-sensitive workloads near US East, you can target:

```text docs-e2e=skip
https://us-east-1.aws.inference.celeris.ai/celeris-1/v1
```

Regional endpoints prefer that region but may fail over during maintenance or
capacity constraints. Measure end-to-end latency and the `Server-Timing`
header with the endpoint your application will actually use.

## What becomes possible around 300 ms

When a model call costs a quarter of a second instead of several seconds,
you can spend model calls the way you spend database queries:

- **Call it per keystroke pause.** Synthesize an artifact on every typing
  pause and throw away stale results (the instant-suggest example).
- **Call it on every request.** Run a guardrail gate in the hot path, both
  directions, no sampling (the guardrails example).
- **Call it in loops.** A 10-step agent at 300 ms per step finishes in 3
  seconds, which is interactive; at 2 seconds per step it is a background
  job (the agent-latency example).
- **Call it in parallel.** Fan out classification over a burst of items and
  drain the queue at interactive speed (the realtime-classification
  example).

The pattern behind all four: treat the model as a fast function, budget the
window deliberately, and keep replies small.
