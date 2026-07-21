# Streaming chatbot

A small web chatbot on `celeris-1` built to show off the thing Celeris is for:
**speed**. The browser measures time-to-first-token and total latency for
every reply and prints them under each message. On a warm connection a full
multi-sentence reply typically lands in **~250-300 ms end to end**, and
because celeris-1 is a diffusion model that generates the whole reply in
parallel, the stream usually arrives as a single burst (first token ≈ full
response).

The stack is deliberately tiny: a vanilla JS page served by a ~150-line
Node/TypeScript server that streams chat completions through the
[OpenAI SDK for JS](https://github.com/openai/openai-node) pointed at the
Celeris base URL.

## Run it

```sh
cd examples/chatbot
npm install

export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
export CELERIS_API_KEY="<your-api-key>"

npm start
# open http://localhost:8787
```

## How it works

- **`server.ts`** serves `public/` and exposes `POST /api/chat`: it takes the
  conversation so far, fits it into the model's input budget, and streams the
  completion back as plain text chunks.
- **`budget.ts`** is the Celeris token-window math (rules in the
  [latency guide](../../guides/latency.md)). `fitConversation` keeps the system prompt
  and the newest turns, dropping the oldest history first, so long chats
  keep working.
- **`config.ts`** resolves the endpoint and credential in one place. The
  browser never holds the server's key.
- **`public/app.js`** renders the stream as it arrives and computes
  time-to-first-token / total time / chars-per-second in the browser, where
  the numbers actually matter.

## Credential seams (for hosted demos)

This example is built to run locally on your own key, but the credential path
is deliberately pluggable, `config.ts` is the only place that decides whose
key a request runs on:

1. **Server key (default)**: from `CELERIS_API_KEY` in the server's
   environment. A hosted demo swaps this for a shared, low-rate-limit proxy
   key. That is why the UI treats **429 as a first-class "rate limited,
   try again shortly" state** with retry guidance, not a generic error.
2. **User-supplied key**: expand *"Use your own API key"* in the UI to run
   requests on your key instead. It is kept in browser memory only, sent per
   request as an `x-user-api-key` header, and never persisted or logged.
3. **Workspace key (future)**: a login-aware proxy can resolve the key from
   the user's workspace; that slot is the same `resolveUpstream` seam.

## Type checking

```sh
npm run typecheck
```

No build step: `tsx` runs the TypeScript server directly.
