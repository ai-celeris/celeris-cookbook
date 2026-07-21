# Celeris Cookbook

Example code and guides for building with the [Celeris](https://celeris.ai)
API — published at [docs.celeris.ai/cookbook](https://docs.celeris.ai/cookbook/).

Celeris serves **celeris-1**, a low-latency diffusion LLM, through an
OpenAI-compatible API: the official OpenAI SDKs *are* the Celeris clients,
pointed at your Celeris base URL. Each example lives in `examples/<name>/`
as a Jupyter notebook or a runnable mini-app — every example is standalone
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
Then follow the example's README — Python examples use
`pip install -r requirements.txt`, the chatbot uses `npm install && npm start`.

## The Celeris token window

Celeris requests share a **4096-token total window** between input and output:

- The wire `max_tokens` value must be a multiple of 256 in the range 256–1024.
- Whatever you reserve for output leaves `4096 - max_tokens` tokens for all
  input messages combined.

Every example budgets its prompt accordingly; the
[getting-started notebook](examples/getting-started) has the canonical
normalization helpers.

## Examples

| Example | What it shows |
| --- | --- |
| [`getting-started`](examples/getting-started) | First chat completion with the OpenAI SDK, token-window budgeting, streaming. |
| [`chatbot`](examples/chatbot) | Streaming web chatbot measuring time-to-first-token — the latency showcase. |
| [`alert-triage-agent`](examples/alert-triage-agent) | Multi-step tool-use agent loop with a structured verdict, inside the 4096-token window. |
| [`nextjs-vercel`](examples/nextjs-vercel) | Minimal full-stack Next.js deploy with the key in Vercel's managed env store. |
| [`fastapi-fly`](examples/fastapi-fly) | Minimal FastAPI deploy with the key in Fly.io's encrypted secret store. |
| [`benchmark`](examples/benchmark) | Mini benchmark harness: latency percentiles, reliability counters, correctness scoring. |

## Repository layout

| Path | Purpose |
| --- | --- |
| `registry.yaml` | Index of examples: title, slug, description, tags, authors, date. The website builds from this. |
| `authors.yaml` | Optional display metadata for authors (falls back to GitHub profile). |
| `examples/` | One directory per example: a notebook or a mini-app with a README. |
| `scripts/` | Registry validation (`scripts/validate.py`). |

## Publishing

This repository is a **git submodule** of the Celeris docs site
(`components/docs-external/cookbook` in marqo-ai/diffusion-llm-service). The
docs build converts `registry.yaml` and each registered page into the
`/cookbook` section of docs.celeris.ai, rendered in the docs theme with a
filterable index.

On every merge to `main` here, the `Notify Docs Site` workflow dispatches the
docs repo's `Bump Cookbook Submodule` workflow, which opens a
submodule-pointer-bump PR; merging that PR republishes the site. To preview
your example as it will appear on the site, build the docs repo's
`components/docs-external` with the submodule pointed at your branch.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: add
`examples/<your-example>/`, register it in `registry.yaml`, and open a pull
request. CI validates the registry and the examples on every PR.
