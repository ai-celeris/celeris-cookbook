# Alert triage agent

A multi-step **tool-use agent loop** on Celeris-1: given a production alert,
the agent investigates by calling tools, `get_alert`, `search_runbooks`,
`check_recent_deploys`, over synthetic fixture data, reasons across the
results, and emits a structured verdict:

```json docs-e2e=skip
{
  "root_cause": "…",
  "evidence": ["…"],
  "recommended_action": "…",
  "confidence": "high|medium|low"
}
```

The scenario is self-contained: a checkout-service latency alert whose fixture
data contains a smoking gun (a deploy 16 minutes before the alert fired that
made payment calls synchronous) plus plausible decoys, so the agent has to
actually correlate evidence rather than pattern-match.

## Run it

```sh docs-e2e=skip
cd examples/alert-triage-agent
pip install -r requirements.txt

export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
export CELERIS_API_KEY="<your-api-key>"

python3 main.py               # triage ALERT-4127
```

You'll see each tool call as the agent makes it, then the final verdict.

## How the loop works

Each turn, the model must answer with **exactly one JSON object**. That is
either a tool call:

```json docs-e2e=skip
{"tool": "search_runbooks", "args": {"query": "checkout-api latency"}}
```

or the final verdict. The harness parses the JSON, executes the tool over
the fixtures, and feeds the result back as the next user message. Malformed
replies get one corrective nudge; a step cap keeps the loop bounded.

### Why prompt-driven tool calls (not the `tools` parameter)?

This pattern works on **any** OpenAI-compatible endpoint, including small,
fast models that don't implement native function-calling. It also keeps every
byte of the exchange visible in the transcript, which makes the agent easy to
debug. If your endpoint supports native `tools`, the loop body is the only
thing that changes; the tools and verdict schema stay the same.

Concretely: the current Celeris serving deployment rejects the `tools`
parameter (`400: "auto" tool choice requires --enable-auto-tool-choice and
--tool-call-parser to be set`), so prompt-driven is the pattern that works
today. The model follows it well, in smoke testing, Celeris-1 completed the
triage in 4 tool turns with a correct, well-evidenced verdict on every run;
the occasional truncated JSON reply is exactly what the corrective-nudge
branch in the loop is for.

### Budgeting inside an 8192-token window

Agent loops usually assume a big context. Celeris allows 8192 tokens across
the prompt and requested output (rules in the
[latency guide](../../guides/latency.md)), so this example treats budget as a
design constraint:

- **Tool results are compact by design**, the runbook search returns the top
  2 hits, not the whole corpus. A tool that returns pages of JSON would evict
  the reasoning that needs it.
- `max_tokens` is 512 because each turn is one compact JSON object; general
  examples use the 2048-token output default.
- `fit_messages` drops the oldest tool exchanges (never the system prompt or
  the task) when the transcript outgrows the input budget.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | The agent loop, tools, and budgeting. |
| `fixtures/alerts.json` | The alert being triaged. |
| `fixtures/runbooks.json` | Searchable runbook snippets (with decoys). |
| `fixtures/deploys.json` | Recent deploys (with the smoking gun). |
