# Celeris Cookbook

Example code and guides for building with the [Celeris](https://celeris.ai)
API — published at [docs.celeris.ai/cookbook](https://docs.celeris.ai/cookbook/).

Celeris serves **celeris-1**, a low-latency diffusion LLM, through an
OpenAI-compatible API: the official OpenAI SDKs *are* the Celeris clients,
pointed at your Celeris base URL. Each example lives in `examples/<name>/`
as a Jupyter notebook or a runnable mini-app. The cookbook website is
generated from this repository: `registry.yaml` is the index, and every
registered page (README or notebook) becomes a page on the site.

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

## Repository layout

| Path | Purpose |
| --- | --- |
| `registry.yaml` | Index of examples: title, slug, description, tags, authors, date. The website builds from this. |
| `authors.yaml` | Optional display metadata for authors (falls back to GitHub profile). |
| `examples/` | One directory per example: a notebook or a mini-app with a README. |
| `site/` | Static site generator that renders the registry and example pages. |
| `scripts/` | Validation and deployment helpers. |
| `infra/` | OpenTofu for the pieces the cookbook owns (assets bucket, deploy role). |

## Building the website locally

```sh
python3 -m pip install -r site/requirements.txt
python3 site/build.py           # BASE_URL=/cookbook/ in production
open site/dist/index.html
```

## Deployment

Merges to `main` dispatch a deploy workflow in the private
`ai-celeris/celeris-cookbook-deploy` repo, which builds the site and publishes
it to S3 + CloudFront under `docs.celeris.ai/cookbook/` via GitHub OIDC. See
`infra/README.md` for the architecture.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: add
`examples/<your-example>/`, register it in `registry.yaml`, and open a pull
request. CI validates the registry and builds the site on every PR.
