# FastAPI on Fly.io

The safe, boring, copy-paste way to put Celeris behind your own Python
backend: a minimal FastAPI app where the browser talks only to **your**
endpoint, and the server calls Celeris with a key from Fly.io's managed
secret store. The key is never in the browser, never in code, never in git.

Five files:

| File | Purpose |
| --- | --- |
| `main.py` | FastAPI app: serves the page and the one `/api/generate` endpoint that talks to Celeris (OpenAI Python SDK + env vars). |
| `static/index.html` | Prompt box that POSTs to `/api/generate`. |
| `requirements.txt` | fastapi, uvicorn, openai. |
| `Dockerfile` | Standard slim Python image running uvicorn. |
| `fly.toml` | Fly app config, contains **no** secrets. |

`main.py` carries the two Celeris conventions used across this cookbook:
append `/v1` to `CELERIS_BASE_URL` for the OpenAI SDK, and normalize
`max_tokens` to a multiple of 256 in [256, 1024] (input + output share a
4096-token window).

## Why Fly.io (and not Render/Railway/…)?

Any host with a managed secret store works; the pattern is identical. Fly
gets the nod here because its secret story is the cleanest to teach from the
CLI: `fly secrets set NAME=value` is one command, encrypted at rest, exposed
to the app only as a runtime environment variable, write-only after creation
(`fly secrets list` shows names and digests, never values), and it lives
entirely outside the config file that gets committed. Render works the same
way (dashboard, then Environment, then add `CELERIS_API_KEY`). If you
prefer Render, `main.py` runs unchanged.

## Run locally

```sh
cd examples/fastapi-fly
pip install -r requirements.txt

export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
export CELERIS_API_KEY="<your-api-key>"

uvicorn main:app --reload
# open http://localhost:8000
```

## Deploy to Fly.io

```sh
brew install flyctl            # or: curl -L https://fly.io/install.sh | sh
fly auth login

fly launch --no-deploy         # registers the app; accept the generated name
                               # (or edit `app` in fly.toml first)

# The point of this example: the key goes into Fly's encrypted secret store.
fly secrets set CELERIS_API_KEY="<your-api-key>"
fly secrets set CELERIS_BASE_URL="https://<your-celeris-endpoint>"

fly deploy
```

`fly secrets set` stages the values encrypted and injects them as environment
variables when the machine boots; `main.py` reads them with `os.environ`
exactly as it does locally.

## Security notes

- **The key lives only in the platform secret store** (Fly secrets / your
  local shell). Nothing in this directory contains it (no `.env`, no
  `fly.toml` entry), and the server never returns it in a response.
- **The browser only ever talks to your own backend.** `index.html` fetches
  `api/generate`; the Celeris endpoint and credentials are invisible to the
  client.
- **Rate-limiting the public endpoint is your responsibility.** As deployed,
  `/api/generate` is open to anyone who finds your URL and spends your
  Celeris quota. Put a rate limiter (e.g. `slowapi`), an auth check, or a
  proxy WAF in front before advertising the URL.
