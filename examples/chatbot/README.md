# Chatbot with model timing

A small web chatbot on Celeris-1 built to show off the thing Celeris is for:
**speed**. Every reply shows the model's server-side processing time from the
API's `Server-Timing` header, followed by total browser-observed latency. This
keeps the value Celeris controls separate from network time, which varies with
the user's location and connection.

The stack is deliberately tiny: a vanilla JS page served by a ~150-line
Node/TypeScript server that proxies chat completions through the
[OpenAI SDK for JS](https://github.com/openai/openai-node) pointed at the
Celeris base URL.

## Run it

```sh docs-e2e=skip
cd examples/chatbot
npm install

export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
export CELERIS_API_KEY="<your-api-key>"

npm start
# open http://localhost:8787
```

## How it works

- **`server.ts`** serves `public/` and exposes `POST /api/chat`: it takes the
  conversation so far, fits it into the model's input budget, and returns the
  completion as text while forwarding the API's `Server-Timing` header.
- **`budget.ts`** is the Celeris token-window math (rules in the
  [latency guide](../../guides/latency.md)). `fitConversation` keeps the system prompt
  and the newest turns, dropping the oldest history first, so long chats
  keep working.
- **`config.ts`** resolves the endpoint and credential in one place. The
  browser never holds the server's key.
- **`public/app.js`** renders the reply and shows model processing time from
  `Server-Timing` alongside total time measured in the browser.

The upstream request uses a complete response intentionally. For complete
responses, the API's `processing` duration includes prompt processing and
generation. Streaming headers arrive before generation, so their `processing`
duration cannot be presented as model time.

## Credential and endpoint seams

This example is built to run locally on your own key, but the credential path
is deliberately pluggable: `config.ts` is the only place that decides whose
key a request runs on:

1. **Server key (default)**: from `CELERIS_API_KEY` in the server's
   environment. A deployment may instead use a shared, low-rate-limit key.
   That is why the UI treats **429 as a first-class "rate limited,
   try again shortly" state** with retry guidance, not a generic error.
2. **User-supplied key**: expand *"Use your own API key"* in the UI to run
   requests on your key instead. It is kept in browser memory only, sent per
   request as an `x-user-api-key` header, and never persisted or logged.
3. **Workspace key (future)**: a login-aware proxy can resolve the key from
   the user's workspace; that slot is the same `resolveUpstream` seam.

There is a matching seam on the endpoint side. `public/app.js` reads an optional
`window.__CELERIS_APP_CONFIG__?.apiBase`, defaulting to this server's own `api/`
route, so running the example yourself leaves everything as described above.
When a host also sets `prewarm: true`, the page issues a best-effort startup
`OPTIONS` to establish its connection and CORS cache before the first prompt.

## Type checking

```sh docs-e2e=skip
npm run typecheck
```

No build step: `tsx` runs the TypeScript server directly.
