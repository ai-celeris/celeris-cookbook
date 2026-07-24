# Next.js on Vercel

The safe, boring, copy-paste way to put Celeris behind your own backend: a
minimal Next.js app where the browser talks only to **your** API route, and
the route calls Celeris server-side with a key from Vercel's managed
environment store. The key is never in the browser, never in code, never in
git.

Five files on top of an empty Next.js app:

| File | Purpose |
| --- | --- |
| `app/api/generate/route.ts` | The one server-side file that talks to Celeris (OpenAI JS SDK + `process.env`). |
| `app/page.tsx` | Prompt box that POSTs to `/api/generate`. |
| `app/layout.tsx` | Bare root layout. |
| `package.json`, `tsconfig.json` | Standard Next.js scaffolding. |

The route handler uses the full SDK base URL and the service's
`max_tokens=2048` default output budget (rules in the
[latency guide](../../guides/latency.md)).

## Run locally

```sh docs-e2e=skip
cd examples/nextjs-vercel
npm install

export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
export CELERIS_API_KEY="<your-api-key>"

npm run dev
# open http://localhost:3000
```

## Deploy to Vercel

Store the key in Vercel's encrypted environment store, this is the whole
point of the example:

```sh docs-e2e=skip
npm i -g vercel
vercel link                                  # create/link the project

vercel env add CELERIS_API_KEY production    # paste the key when prompted
vercel env add CELERIS_BASE_URL production   # paste the full SDK base URL

vercel deploy --prod
```

(Dashboard path: Project → Settings → Environment Variables. Mark
`CELERIS_API_KEY` as **Sensitive** so it can't be read back from the UI.)

Vercel injects both values as environment variables into the serverless
function at runtime; `route.ts` reads them with `process.env` exactly as it
does locally.

## Security notes

- **The key lives only in the platform secret store** (Vercel env vars /
  your local shell). Nothing in this repo contains it (no `.env` file, no
  config), and `route.ts` never returns it in a response.
- **The browser only ever talks to your own backend.** `page.tsx` fetches
  `/api/generate`; the Celeris endpoint and credentials are invisible to the
  client.
- **Rate-limiting the public endpoint is your responsibility.** As deployed,
  `/api/generate` is open to anyone who finds your URL and spends your
  Celeris quota. Add Vercel WAF rules / middleware rate limiting or an auth
  check before advertising the URL.
