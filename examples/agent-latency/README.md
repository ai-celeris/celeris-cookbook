# Agent latency compounds

An agent is a loop: model call, tool call, model call, tool call. Every
model call sits on the critical path, so per-step latency multiplies by the
number of steps. At 2 seconds per step, a 10-step agent takes 20 seconds and
users give up. At a few hundred milliseconds per step, the same agent
finishes in seconds and can live inside an interactive product.

This example runs a small order-support agent on celeris-1, measures wall
clock per step, and shows how the totals compound.

## Run it

```sh
cd examples/agent-latency
pip install -r requirements.txt

export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
export CELERIS_API_KEY="<your-api-key>"

python3 main.py
```

## Measured results

A real run against a live workspace (2026-07-21). The agent answered a
customer question ("where is my order, can I still get a refund?") using
three tools:

```text
  step 1:   1093 ms  get_order({"order_id": "ORD-1042"})
  step 2:    269 ms  get_shipping_status({"tracking_id": "TRK-88231"})
  step 3:    282 ms  get_refund_policy({})
  step 4:    359 ms  final answer

4 model steps, mean 501 ms per step, total 2.0 s wall clock
```

Step 1 includes cold-connection setup; warm steps run at 270 to 360 ms. The
compounding table from that run:

| steps | at measured pace | at 2 s per step |
| --- | --- | --- |
| 1 | 0.5 s | 2 s |
| 5 | 2.5 s | 10 s |
| 10 | 5.0 s | 20 s |
| 20 | 10.0 s | 40 s |
| 50 | 25.0 s | 100 s |

The per-step gap looks small. Multiplied by a realistic step count, it is
the difference between an interactive agent and a background job.

## How it works

- The loop is the same prompt-driven JSON pattern as the alert triage
  example: the model replies with one JSON object per turn, either a tool
  call or the final answer. It works on any OpenAI-compatible endpoint.
- Tool results are compact so every step fits the 4096-token window beside a
  normalized `max_tokens` of 256.
- The harness times each model call separately, so you can see exactly where
  the wall clock goes.

## Which agent steps suit a fast model

Match the model to the step, not the whole agent:

- **Good fits**: tool selection and argument filling, routing, extraction,
  lookups, formatting, validation, summarizing tool output. These are most
  of the steps in most agents, and they reward speed.
- **Poor fits**: open-ended planning, novel code synthesis, long-context
  reasoning. Send those few steps to a larger model if you need it.

A practical split: run the loop on a fast model and escalate individual
steps only when they fail or need depth. The compounding table shows why
this matters: making the common steps fast is what makes the whole agent
feel instant.
