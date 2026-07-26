# Cookbook demo proxy

The interactive demos on the published cookbook pages (see [`../demos`](../demos))
call a small shared proxy that holds an API key server-side, so the browser
never sees one. That proxy is operational infrastructure for the docs site
rather than an example, so it lives in the private infrastructure repository
alongside the rest of the docs deployment.

## What it does

The proxy exposes one route per embedded app, each matching the shape of that
example's own server so the embedded page runs the example's unmodified client
code:

| Route | Request | Response |
| --- | --- | --- |
| `POST /cookbook-api/chat` | `{messages: [{role, content}]}` | streamed plain text |
| `POST /cookbook-api/synthesize` | `{description}` | `{regex, explanation, server_ms}` |

It is reachable only through the docs domain, caps request size, message
count, and output tokens, and runs on a dedicated key with its own spend
limit, so a shared public endpoint can only ever leak a trickle of quota.
Message content and key material are never logged.

## Building the same thing yourself

If you want this pattern for your own app, the cookbook has two worked
examples, both keeping the key on the server:

- [Next.js on Vercel](../examples/nextjs-vercel): one route handler, with the
  key in the managed environment store.
- [FastAPI on Fly.io](../examples/fastapi-fly): one endpoint, with the key in
  the encrypted secret store.

Neither needs a shared proxy. You only need one when a single public page has
to serve many strangers on one key, which is the situation these demos are in
and yours probably is not.
