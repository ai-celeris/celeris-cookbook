# Understanding latency with celeris-1

This guide explains how to measure, budget, and design for latency on the
Celeris API. The examples in this cookbook link here instead of repeating
it. Two facts drive everything else:

1. celeris-1 is a diffusion model. It generates the whole reply in parallel
   and usually delivers it as **one burst**, not token by token.
2. Requests have an **8192-token total window**, with input capped at **2048
   tokens**. Cookbook examples request **2048 output tokens by default** and
   use smaller values only for deliberately short replies.

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

One request has 8192 tokens for input and output combined, and input alone
cannot exceed 2048 tokens. `max_tokens` reserves the output canvas. The
cookbook defaults it to 2048; a label, small JSON object, or other explicitly
short result can reserve less. The input budget is the smaller of the
2048-token input cap and the room left in the total window:

```python docs-e2e=skip
TOTAL_TOKEN_LIMIT = 8192
MAX_INPUT_TOKENS = 2048
DEFAULT_MAX_OUTPUT_TOKENS = 2048


def input_token_budget(max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS) -> int:
    """Maximum input tokens allowed with this output reservation."""
    if not 0 < max_tokens < TOTAL_TOKEN_LIMIT:
        raise ValueError("max_tokens must be between 1 and 8191")
    return min(MAX_INPUT_TOKENS, TOTAL_TOKEN_LIMIT - max_tokens)
```

With the default 2048-token output reservation, the input budget is 2048
tokens because the input cap binds before the 8192-token total. A short
classification can request 256 output tokens and still has the same 2048-token
input cap. An
unusually large 7000-token output reservation leaves only 1192 tokens for
input because the total-window limit then binds.

Celeris does not expose its tokenizer. Estimate about 4 bytes per token,
leave an allowance for the chat template (the cookbook helpers use 8 tokens
plus 4 per message), and clip long input **before** sending. The API will
not clip for you; an oversized request fails.

Two budgeting habits from the examples:

- **Use the default unless the task is clearly short.** General examples use
  2048 output tokens. Labels, compact verdicts, and tool calls deliberately
  reserve 256 or 512 instead.
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
