# Understanding latency with celeris-1

This guide explains how to measure, budget, and design for latency on the
Celeris API. The examples in this cookbook link here instead of repeating
it. Two facts drive everything else:

1. celeris-1 is a diffusion model. It generates the whole reply in parallel
   and usually delivers it as **one burst**, not token by token.
2. Requests share a **4096-token window** between input and output, and the
   wire `max_tokens` value must be a multiple of 256 between 256 and 1024.

## The vocabulary

- **Time to first token (TTFT)**: from sending the request to the first
  byte of the reply.
- **Total latency**: from sending the request to the last byte.
- **Tokens per second**: output tokens divided by the streaming window
  (total minus TTFT).

On token-by-token models these three numbers tell different stories: TTFT
sets how soon something appears, tokens per second sets how long the user
watches text arrive. On celeris-1 they collapse: **TTFT equals total** in
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

One request has 4096 tokens for input and output combined. You choose the
split by setting `max_tokens`, which must be a multiple of 256 between 256
and 1024. Reserve output first, then fit the input in what remains. The
canonical helpers, used across this cookbook:

```python docs-e2e=skip
TOTAL_TOKEN_LIMIT = 4096
MIN_OUTPUT_TOKENS = 256
MAX_OUTPUT_TOKENS = 1024
OUTPUT_TOKEN_STEP = 256


def normalize_max_tokens(requested: int) -> int:
    """Round up to a supported 256-token step, clamped to [256, 1024]."""
    if requested <= MIN_OUTPUT_TOKENS:
        return MIN_OUTPUT_TOKENS
    if requested >= MAX_OUTPUT_TOKENS:
        return MAX_OUTPUT_TOKENS
    step = OUTPUT_TOKEN_STEP
    return ((requested + step - 1) // step) * step


def input_token_budget(max_tokens: int) -> int:
    """Tokens left for ALL input messages after the output reservation."""
    return TOTAL_TOKEN_LIMIT - normalize_max_tokens(max_tokens)
```

Worked example: you request 512 output tokens. That is already a legal
value, so the reservation is 512 and your input budget is 3584 tokens for
all messages combined, including the chat template. Request 300 and the
reservation rounds **up** to 512 (rounding down would silently shrink the
output you asked for). Request 2000 and it clamps to 1024, leaving 3072 for
input.

Celeris does not expose its tokenizer. Estimate about 4 bytes per token,
leave an allowance for the chat template (the cookbook helpers use 8 tokens
plus 4 per message), and clip long input **before** sending. The API will
not clip for you; an oversized request fails.

Two budgeting habits from the examples:

- **Small canvas by default.** Labels, verdicts, and tool calls fit in 256.
  Every step of reservation you do not use is input room you keep.
- **Drop oldest first.** Chat history and agent transcripts should evict
  their oldest turns, never the system prompt or the newest message.

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
