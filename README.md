# Celeris Cookbook

Example code and guides for building with the [Celeris](https://celeris.ai)
API. Published at [docs.celeris.ai/cookbook](https://docs.celeris.ai/cookbook/).

Celeris serves **Celeris-1**, a low-latency diffusion LLM, through an
OpenAI-compatible API: the official OpenAI SDKs *are* the Celeris clients,
pointed at your Celeris base URL. Each example lives in `examples/<name>/`
as a Jupyter notebook or a runnable mini-app, every example is standalone
and clonable. The published site is generated from this repository:
`registry.yaml` is the index, and every registered page (README or notebook)
becomes a page under docs.celeris.ai/cookbook.

## Running the examples

Every SDK example needs:

```sh
export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
export CELERIS_API_KEY="<your-api-key>"
```

The global endpoint is recommended for most applications. Use
`https://us-east-1.aws.inference.celeris.ai/celeris-1/v1` only when you need
to prefer US East. The OpenAI SDK's `OPENAI_BASE_URL` and `OPENAI_API_KEY`
work as fallbacks.

### Building the browser apps

The browser-based recipes can also be built as ordinary static applications:

```sh docs-e2e=skip
npm run build:apps
# or build one recipe
npm run build:apps -- chatbot
```

The command writes ignored output to `demos/dist/<name>/`. It contains no
hosting configuration; deploy it behind the matching example server or let
your own hosting pipeline adapt it.

## The Celeris token window

Celeris requests have an **8192-token total window**:

- If `max_tokens` is omitted, the service defaults it to **2048**.
- An explicit `max_tokens` must be a positive multiple of **256**.
- Prompt tokens plus `max_tokens` must be at most **8192**.

Use the smallest output reservation that fits the task. The
[getting-started notebook](examples/getting-started) includes the canonical
validation and budgeting helpers.

## Guides

- [Understanding latency with Celeris-1](guides/latency.md): metrics, the
  one-burst delivery model, and token-window budgeting. Examples link here
  instead of repeating the rules.
- [The cascade, fast model first](guides/cascade.md): the reference
  architecture for pairing Celeris-1 with a slower, more intelligent model.
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
| [`chatbot`](examples/chatbot) | Web chatbot showing model processing time for every response. |
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
| `registry.yaml` | Index of examples: title, slug, topic, description, tags, authors, date. The website builds its topic-grouped sidebar from this. |
| `authors.yaml` | Optional display metadata for authors (falls back to GitHub profile). |
| `examples/` | One directory per example: a notebook or a mini-app with a README. |
| `demos/build.mjs` | Source-only build entry point for the browser application recipes. |
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
