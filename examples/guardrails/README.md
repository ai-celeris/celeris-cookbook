# Guardrails on every request

Most teams want a moderation and validation gate in front of their product's
LLM features. With a slow model the gate costs seconds, so it gets applied to
samples, or only to suspicious traffic, and the worst inputs slip through on
the fast path. A gate that answers in under 300 ms can run on every single
request without users noticing.

This example checks each message against a written policy and returns a
structured verdict (allow, block, or flag) with a reason, then measures the
latency the gate adds.

## Run it

```sh
cd examples/guardrails
pip install -r requirements.txt

export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
export CELERIS_API_KEY="<your-api-key>"

python3 main.py
```

## Measured results

A real run against a live workspace (2026-07-21):

```text
parseable verdicts: 8/8
agreement with expected action: 8/8
added latency per request: p50 293 ms, p95 1006 ms, mean 384 ms
```

The p95 outlier is the first request on a cold connection. Warm requests add
about 280 to 330 ms. The test set covers normal questions, prompt injection
attempts, abuse, and cases that should go to a human (a possible data
breach, an account deletion request).

## How it works

- The policy is written out in plain language in the prompt, with explicit
  rules for what to block and what to flag. A gate model applies the rules
  you give it. When the policy was vaguer, the model made defensible but
  different calls on the human-review cases; spelling the rules out took
  agreement from 6/8 to 8/8.
- The model must reply with only a JSON object: `{"action": ..., "reason":
  ...}`. The parser tolerates code fences and surrounding prose, validates
  the action against the allowed set, and treats anything else as a failed
  check (fail closed or open is your call, make it deliberately).
- `max_tokens` is normalized to 256. Verdicts are short by design.

## Where this pattern fits

Input gates (prompt injection, abuse, off-topic), output gates (policy and
tone checks before text reaches a user), and form or content validation. At
about 300 ms per check you can afford the gate on the hot path, in both
directions, on every request.
