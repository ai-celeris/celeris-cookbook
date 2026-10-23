import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import OpenAI from "openai";

import { resolveUpstream } from "./config.ts";

const PORT = Number(process.env.PORT ?? 8789);
const PUBLIC_DIR = new URL("./public/", import.meta.url).pathname;
const MAX_QUERY_CHARS = 500;
const WORD = /[a-z0-9]+/g;

const DOCS = [
  ["Resetting your password", "Use account settings to reset a forgotten password or rotate credentials."],
  ["API key rotation", "Rotate API keys from the console. Old keys work for one hour after rotation."],
  ["Rate limits and 429 responses", "Requests over your workspace limit return HTTP 429 with a Retry-After header."],
  ["Retry strategies", "Use exponential backoff with jitter when a request fails with 429 or 5xx."],
  ["Billing and invoices", "Invoices are issued monthly and can be downloaded as PDFs from billing."],
  ["Refund policy", "Unused prepaid credits are refundable within 30 days of purchase."],
  ["Team roles and permissions", "Owners can invite members and change roles. Viewers have read-only access."],
  ["Webhook delivery", "Webhooks retry failed deliveries five times with increasing delay."],
  ["Streaming responses", "Set stream to true to receive replies as server-sent events."],
  ["Request timeouts", "The default client timeout is 60 seconds. Long requests should stream."],
  ["Data retention", "Request and response bodies are retained for 30 days, then deleted."],
  ["Exporting usage data", "Usage exports are available as daily CSV files per workspace."],
  ["Single sign-on setup", "Configure SAML SSO from security settings. SCIM sync is optional."],
  ["Error codes reference", "4xx codes are request problems. 5xx codes are service problems. 429 is rate limiting."],
  ["Deleting your account", "Account deletion removes all workspace data after a seven-day grace period."],
  ["Regions and data residency", "Workspaces pin to one region. Data does not leave the pinned region."],
] as const;

const CONTENT_TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
};

const REWRITE_PROMPT = `Rewrite this search query into 3 to 6 lowercase keywords for a keyword
search over product documentation. Expand abbreviations and add close synonyms.
Reply with ONLY a JSON object: {"keywords": ["...", "..."]}

Query: `;

function terms(text: string): string[] {
  return text.toLowerCase().match(WORD) ?? [];
}

function search(queryTerms: string[]) {
  const wanted = new Set(queryTerms.filter(Boolean));
  return DOCS.map(([title, body]) => {
    const haystack = new Set(terms(`${title} ${body}`));
    const score = [...wanted].filter((term) => haystack.has(term)).length;
    return { title, body, score };
  })
    .filter((document) => document.score > 0)
    .sort((a, b) => b.score - a.score || a.title.localeCompare(b.title))
    .slice(0, 3)
    .map(({ title, body }) => ({ title, body }));
}

function parseKeywords(output: string): string[] | null {
  const cleaned = output.replace(/^\`\`\`(?:json)?\s*|\s*\`\`\`$/g, "").trim();
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  try {
    const parsed: unknown = JSON.parse(cleaned.slice(start, end + 1));
    if (!parsed || typeof parsed !== "object" || !("keywords" in parsed)) return null;
    const keywords = (parsed as { keywords?: unknown }).keywords;
    if (!Array.isArray(keywords) || keywords.length === 0) return null;
    return keywords.map(String).map((keyword) => keyword.trim()).filter(Boolean).slice(0, 6);
  } catch {
    return null;
  }
}

async function readBody(request: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString("utf8");
}

function sendJson(response: ServerResponse, status: number, body: unknown): void {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  response.end(JSON.stringify(body));
}

async function handleSearch(request: IncomingMessage, response: ServerResponse): Promise<void> {
  let query: string;
  try {
    const parsed = JSON.parse(await readBody(request));
    query = String(parsed.query ?? "").trim().slice(0, MAX_QUERY_CHARS);
    if (!query) throw new Error("empty");
  } catch {
    sendJson(response, 400, { error: "query_required" });
    return;
  }

  const rawResults = search(terms(query));
  const userKeyHeader = request.headers["x-user-api-key"];
  const userApiKey = Array.isArray(userKeyHeader) ? userKeyHeader[0] : userKeyHeader;
  let upstream;
  try {
    upstream = resolveUpstream(userApiKey);
  } catch (error) {
    sendJson(response, 500, { error: "misconfigured", detail: String(error), raw_results: rawResults });
    return;
  }

  const client = new OpenAI({ baseURL: upstream.baseURL, apiKey: upstream.apiKey, maxRetries: 0 });
  const started = performance.now();
  try {
    const completion = await client.chat.completions.create({
      model: upstream.model,
      messages: [{ role: "user", content: REWRITE_PROMPT + query }],
      max_tokens: 256,
      temperature: 0,
      // Timing covers the completed rewrite. Streaming can expose incomplete
      // timing headers, so keep this request explicitly non-streaming.
      stream: false,
    });
    const serverMs = Math.round(performance.now() - started);
    const keywords = parseKeywords(completion.choices[0]?.message?.content ?? "");
    if (!keywords) {
      sendJson(response, 200, {
        raw_results: rawResults,
        results: rawResults,
        keywords: null,
        server_ms: serverMs,
        fallback: "The rewrite could not be read, so the original query was used.",
      });
      return;
    }
    sendJson(response, 200, {
      raw_results: rawResults,
      results: search(keywords.flatMap(terms)),
      keywords,
      server_ms: serverMs,
    });
  } catch (error) {
    const serverMs = Math.round(performance.now() - started);
    const rateLimited = error instanceof OpenAI.APIError && error.status === 429;
    sendJson(response, 200, {
      raw_results: rawResults,
      results: rawResults,
      keywords: null,
      server_ms: serverMs,
      fallback: rateLimited
        ? "Query understanding is rate limited, so the original query was used."
        : "Query understanding is unavailable, so the original query was used.",
    });
  }
}

async function handleStatic(pathname: string, response: ServerResponse): Promise<void> {
  const relative = pathname === "/" ? "index.html" : pathname.slice(1);
  const safe = normalize(relative);
  if (safe.startsWith("..") || safe.includes("\0")) {
    response.writeHead(404).end();
    return;
  }
  try {
    const file = await readFile(join(PUBLIC_DIR, safe));
    response.writeHead(200, {
      "content-type": CONTENT_TYPES[extname(safe)] ?? "application/octet-stream",
    });
    response.end(file);
  } catch {
    response.writeHead(404, { "content-type": "text/plain" }).end("not found");
  }
}

const server = createServer(async (request, response) => {
  const pathname = new URL(request.url ?? "/", "http://localhost").pathname;
  if (request.method === "POST" && pathname === "/api/search") {
    await handleSearch(request, response);
  } else if (request.method === "GET" && pathname === "/api/health") {
    sendJson(response, 200, { ok: true });
  } else if (request.method === "GET") {
    await handleStatic(pathname, response);
  } else {
    response.writeHead(405).end();
  }
});

server.listen(PORT, () => {
  console.log(`instant-search listening on http://localhost:${PORT}`);
});
