# Cookbook demo proxy

A small hardened proxy that lets the docs site's **live chatbot demo widget**
(the optional widget on the [chatbot example](../examples/chatbot) page) talk
to Celeris without ever exposing an API key to the browser.

Not an example — this is the operational piece behind the demo. It exposes
`POST /api/chat` with the same request/response shape as the chatbot example
server, plus the hardening a public shared endpoint needs:

| Control | Default | Env |
| --- | --- | --- |
| Origin allowlist (exact match, CORS) | `http://localhost:3000` | `DEMO_ALLOWED_ORIGINS` (comma-separated) |
| Global rate limit (token bucket) | 2 rps, burst 4 | `DEMO_GLOBAL_RPS`, `DEMO_GLOBAL_BURST` |
| Per-IP limit (fixed window) | 6/min | `DEMO_PER_IP_PER_MIN` |
| Body size cap | 16 KB | `DEMO_MAX_BODY_BYTES` |
| Conversation caps | 20 messages / 8000 chars | (fixed) |

Throttled requests get a **friendly JSON 429** (`{"error": "rate_limited",
"message": …, "retry_after_s": 5}` with a `Retry-After` header) that the
widget renders as a "busy — try again shortly" state. Message content and key
material are never logged; the only logs are startup configuration shape and
upstream failure classes.

## Run locally

```sh
cd demo-proxy
npm install

export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
export CELERIS_API_KEY="<your-api-key>"
export DEMO_ALLOWED_ORIGINS="http://localhost:3000"

npm start          # POST /api/chat on :8080, GET /healthz
```

## Deploy

No standing infrastructure exists for this yet — deploying is a deliberate
manual step. The natural home is the existing celeris-apps compose host
(Docker Compose behind Caddy):

1. Build the image from this directory's `Dockerfile` and add a service to
   the compose file with `CELERIS_BASE_URL`, `CELERIS_API_KEY` (from the
   host's secret store — never in the compose file), and
   `DEMO_ALLOWED_ORIGINS=https://docs.celeris.ai`.
2. Route it in Caddy (e.g. `demo.<zone>` → container port 8080). The proxy
   trusts the first `X-Forwarded-For` hop for per-IP limiting, which Caddy
   sets.
3. Health check: `GET /healthz`.
4. Then enable the widget on the docs site by setting
   `COOKBOOK_CHAT_DEMO_URL=https://demo.<zone>/api/chat` in the docs build
   environment (see the docs repo's `prepare-cookbook.mjs`).

Keep the limits conservative: the whole point is that a stranger finding the
endpoint can waste at most a trickle of quota.

## Type checking

```sh
npm run typecheck
```
