# Celeris Cookbook

Example code and guides for building with the [Celeris](https://celeris.ai) API.

Each example lives in `examples/<name>/` with its own README and runnable code.
The cookbook website is generated from this repository: `registry.yaml` is the
index, and every registered example README becomes a page.

## Running the examples

Most examples are small Python scripts. You need:

```sh
export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
export CELERIS_API_KEY="<your-api-key>"
```

Then, from an example directory:

```sh
cd examples/getting-started
python3 -m pip install -r requirements.txt
python3 main.py
```

## The Celeris token window

Celeris requests share a **4096-token total window** between input and output:

- The wire `max_tokens` value must be a multiple of 256 in the range 256–1024.
- Whatever you reserve for output leaves `4096 - max_tokens` tokens for all
  input messages combined.

Every example budgets its prompt accordingly; see
[`examples/getting-started`](examples/getting-started) for the canonical
normalization helper.

## Repository layout

| Path | Purpose |
| --- | --- |
| `registry.yaml` | Index of examples: title, slug, description, tags, authors, date. The website builds from this. |
| `authors.yaml` | Optional display metadata for authors (falls back to GitHub profile). |
| `examples/` | One directory per example, each with a `README.md` and runnable code. |
| `site/` | Static site generator that renders the registry and example pages. |
| `scripts/` | Validation and deployment helpers. |
| `infra/` | OpenTofu configuration for the cookbook website (S3 + CloudFront). |

## Building the website locally

```sh
python3 -m pip install -r site/requirements.txt
python3 site/build.py
open site/dist/index.html
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: add
`examples/<your-example>/` with a README and runnable code, register it in
`registry.yaml`, and open a pull request. CI validates the registry and builds
the site on every PR.
