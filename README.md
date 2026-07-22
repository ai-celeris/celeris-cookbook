# Celeris Cookbook

Example code and guides for building with the [Celeris](https://celeris.ai)
API. Published at [docs.celeris.ai/cookbook](https://docs.celeris.ai/cookbook/).

Celeris serves **celeris-1**, a low-latency diffusion LLM, through an
OpenAI-compatible API: the official OpenAI SDKs *are* the Celeris clients,
pointed at your Celeris base URL. Each example lives in `examples/<name>/`
as a Jupyter notebook or a runnable mini-app, every example is standalone
and clonable. The published site is generated from this repository:
`registry.yaml` is the index, and every registered page (README or notebook)
becomes a page under docs.celeris.ai/cookbook.

## Running the examples

Every example needs:

```sh
export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
export CELERIS_API_KEY="<your-api-key>"
```

(The OpenAI SDK's own `OPENAI_BASE_URL` / `OPENAI_API_KEY` work as fallbacks.)
Then follow the example's README, Python examples use
`pip install -r requirements.txt`, the chatbot uses `npm install && npm start`.

## The Celeris token window

Celeris requests have an **8192-token total window**:

- Input is capped at **2048 tokens**, including all messages and chat-template
  overhead.
- Cookbook examples use **2048 output tokens by default**. Examples that ask
  for a label, small JSON object, or another deliberately short answer use a
  smaller `max_tokens` value.
- Input plus the requested output must stay within the 8192-token total.

Every example budgets its prompt accordingly; the
[getting-started notebook](examples/getting-started) has the canonical
budgeting helpers.

## Guides

- [Understanding latency with celeris-1](guides/latency.md): metrics, the
  one-burst delivery model, and token-window budgeting. Examples link here
  instead of repeating the rules.
- [The cascade, fast model first](guides/cascade.md): the reference
  architecture for pairing celeris-1 with a larger model.
- [Framework compatibility](guides/compatibility.md): verified snippets for
  common SDKs and frameworks.
- [The voice turn budget](guides/voice-turn.md): the measured reply step
  beside cited speech-step ranges.
- [Shell tasks with the celeris CLI](guides/cli-shell-tasks.md): semantic
  operations inside ordinary pipes, with the scripting patterns that make
  them dependable.

## Examples

| Example | What it shows |
| --- | --- |
| [`getting-started`](examples/getting-started) | First chat completion with the OpenAI SDK, token-window budgeting, streaming. |
| [`chatbot`](examples/chatbot) | Streaming web chatbot measuring time-to-first-token, the latency showcase. |
| [`alert-triage-agent`](examples/alert-triage-agent) | Multi-step tool-use agent loop with a structured verdict, inside the 8192-token window. |
| [`nextjs-vercel`](examples/nextjs-vercel) | Minimal full-stack Next.js deploy with the key in Vercel's managed env store. |
| [`fastapi-fly`](examples/fastapi-fly) | Minimal FastAPI deploy with the key in Fly.io's encrypted secret store. |
| [`benchmark`](examples/benchmark) | Mini benchmark harness: latency percentiles, reliability counters, correctness scoring. |
| [`realtime-classification`](examples/realtime-classification) | Ticket routing in the request path, about 260 ms per decision. |
| [`guardrails`](examples/guardrails) | A moderation gate fast enough to run on every request. |
| [`agent-latency`](examples/agent-latency) | How per-step latency compounds in agents, with measured numbers. |
| [`instant-suggest`](examples/instant-suggest) | A regex synthesized live on every typing pause, validated in the browser. |
| [`instant-search`](examples/instant-search) | Query rewriting in front of search at about 300 ms per rewrite. |
| [`extraction-at-scale`](examples/extraction-at-scale) | Structured extraction over a corpus, 182 to 289 docs per minute measured. |
| [`burst-rendering`](examples/burst-rendering) | Three ways to render a whole-reply-at-once model in a chat UI. |
| [`task-fit`](examples/task-fit) | Evaluate your own prompts and get honest per-task fit verdicts. |

## Repository layout

| Path | Purpose |
| --- | --- |
| `registry.yaml` | Index of examples: title, slug, description, tags, authors, date. The website builds from this. |
| `authors.yaml` | Optional display metadata for authors (falls back to GitHub profile). |
| `examples/` | One directory per example: a notebook or a mini-app with a README. |
| `scripts/` | Registry validation (`scripts/validate.py`). |

## Publishing

The Celeris docs site includes this repository as a git submodule. The docs
build converts `registry.yaml` and each registered page into the `/cookbook`
section of docs.celeris.ai, rendered in the docs theme with a filterable
index.

On every merge to `main` here, the `Notify Docs Site` workflow dispatches the
docs repo's `Bump Cookbook Submodule` workflow, which opens a
submodule-pointer-bump PR; merging that PR republishes the site. To preview
your example as it will appear on the site, build the docs repo's
`components/docs-external` with the submodule pointed at your branch.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: add
`examples/<your-example>/`, register it in `registry.yaml`, and open a pull
request. CI validates the registry and the examples on every PR.
