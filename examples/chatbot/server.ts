// Minimal streaming chatbot server for the Celeris API.
//
// Serves the static UI from public/ and streams chat completions through
// POST /api/chat using the OpenAI SDK pointed at the Celeris base URL. The
// browser measures time-to-first-token itself — the point of this example is
// seeing Celeris's latency, so the server adds as little as possible on top.
//
//   npm install
//   export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
//   export CELERIS_API_KEY="<your-api-key>"
//   npm start          # http://localhost:8787

import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import OpenAI from "openai";

import { fitConversation, normalizeMaxTokens, type ChatMessage } from "./budget.ts";
import { resolveUpstream } from "./config.ts";

const PORT = Number(process.env.PORT ?? 8787);
const PUBLIC_DIR = new URL("./public/", import.meta.url).pathname;

const SYSTEM_PROMPT =
  "You are a fast, friendly assistant. Keep answers short and direct.";

const CONTENT_TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
};

async function readBody(request: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString("utf8");
}

function sendJson(response: ServerResponse, status: number, body: unknown): void {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(body));
}

function isRateLimit(error: unknown): boolean {
  return error instanceof OpenAI.APIError && error.status === 429;
}

async function handleChat(request: IncomingMessage, response: ServerResponse): Promise<void> {
  let history: ChatMessage[];
  try {
    const parsed = JSON.parse(await readBody(request));
    history = (parsed.messages ?? []).filter(
      (m: ChatMessage) =>
        (m.role === "user" || m.role === "assistant") && typeof m.content === "string",
    );
    if (history.length === 0) throw new Error("empty conversation");
  } catch {
    sendJson(response, 400, { error: "bad_request" });
    return;
  }

  // A user-supplied key travels only in this header, is used for this one
  // request, and is never logged or stored.
  const userKeyHeader = request.headers["x-user-api-key"];
  const userApiKey = Array.isArray(userKeyHeader) ? userKeyHeader[0] : userKeyHeader;

  let upstream;
  try {
    upstream = resolveUpstream(userApiKey);
  } catch (error) {
    sendJson(response, 500, { error: "misconfigured", detail: String(error) });
    return;
  }

  const client = new OpenAI({ baseURL: upstream.baseURL, apiKey: upstream.apiKey });
  const maxTokens = normalizeMaxTokens(512);
  const messages = fitConversation(SYSTEM_PROMPT, history, maxTokens);

  try {
    const stream = await client.chat.completions.create({
      model: upstream.model,
      messages,
      max_tokens: maxTokens,
      temperature: 0.3,
      stream: true,
    });

    response.writeHead(200, {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
      "x-accel-buffering": "no",
    });
    for await (const chunk of stream) {
      const delta = chunk.choices[0]?.delta?.content;
      if (delta) response.write(delta);
    }
    response.end();
  } catch (error) {
    if (response.headersSent) {
      response.end();
      return;
    }
    if (isRateLimit(error)) {
      // First-class state, not a generic failure: hosted demos share a
      // low-RPS key, so the UI treats 429 as "try again shortly".
      sendJson(response, 429, { error: "rate_limited" });
      return;
    }
    console.error("chat request failed:", error instanceof Error ? error.message : error);
    sendJson(response, 502, { error: "upstream_failed" });
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
    response.writeHead(404, { "content-type": "text/plain" });
    response.end("not found");
  }
}

const server = createServer(async (request, response) => {
  const pathname = new URL(request.url ?? "/", "http://localhost").pathname;
  if (request.method === "POST" && pathname === "/api/chat") {
    await handleChat(request, response);
  } else if (request.method === "GET" && pathname === "/api/health") {
    sendJson(response, 200, { ok: true });
  } else if (request.method === "GET") {
    await handleStatic(pathname, response);
  } else {
    response.writeHead(405).end();
  }
});

server.listen(PORT, () => {
  console.log(`chatbot listening on http://localhost:${PORT}`);
});
