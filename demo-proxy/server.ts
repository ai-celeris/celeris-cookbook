// Demo proxy for the cookbook chatbot widget.
//
// Holds the Celeris API key server-side and exposes POST /api/chat with the
// same request/response shape as the chatbot example server, hardened for
// public exposure:
//
//   - strict Origin allowlist (DEMO_ALLOWED_ORIGINS, comma-separated)
//   - global token-bucket rate limit (protects the shared key)
//   - per-IP fixed-window limit (stops one visitor draining the bucket)
//   - request size caps (body bytes, message count, total chars)
//   - friendly JSON 429s the widget renders as a "busy, retry shortly" state
//   - no message content and no key material is ever logged
//
//   export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
//   export CELERIS_API_KEY="<your-api-key>"
//   export DEMO_ALLOWED_ORIGINS="https://docs.celeris.ai"
//   npm start                                   # listens on :8080

import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import OpenAI from "openai";

import { PerIpWindow, TokenBucket } from "./limits.ts";

const PORT = Number(process.env.PORT ?? 8080);
const MAX_BODY_BYTES = Number(process.env.DEMO_MAX_BODY_BYTES ?? 16_384);
const MAX_MESSAGES = 20;
const MAX_TOTAL_CHARS = 8_000;
const MAX_TOKENS = 512; // multiple of 256 in [256, 1024] per the Celeris window

const ALLOWED_ORIGINS = new Set(
  (process.env.DEMO_ALLOWED_ORIGINS ?? "http://localhost:3000")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean),
);

const globalBucket = new TokenBucket(
  Number(process.env.DEMO_GLOBAL_RPS ?? 2),
  Number(process.env.DEMO_GLOBAL_BURST ?? 4),
);
const perIp = new PerIpWindow(Number(process.env.DEMO_PER_IP_PER_MIN ?? 6));

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

function celerisBaseUrl(): string {
  const root = (process.env.CELERIS_BASE_URL ?? process.env.OPENAI_BASE_URL ?? "").replace(/\/+$/, "");
  if (!root) throw new Error("Set CELERIS_BASE_URL first.");
  return root.endsWith("/v1") ? root : `${root}/v1`;
}

function clientIp(request: IncomingMessage): string {
  const forwarded = request.headers["x-forwarded-for"];
  const first = (Array.isArray(forwarded) ? forwarded[0] : forwarded)?.split(",")[0]?.trim();
  return first || request.socket.remoteAddress || "unknown";
}

function corsHeaders(origin: string): Record<string, string> {
  return {
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-allow-headers": "content-type",
    "access-control-max-age": "600",
    vary: "origin",
  };
}

function sendJson(
  response: ServerResponse,
  status: number,
  body: unknown,
  extraHeaders: Record<string, string> = {},
): void {
  response.writeHead(status, { "content-type": "application/json", ...extraHeaders });
  response.end(JSON.stringify(body));
}

function rateLimited(response: ServerResponse, headers: Record<string, string>): void {
  sendJson(
    response,
    429,
    {
      error: "rate_limited",
      message: "The shared demo is busy right now, wait a few seconds and try again.",
      retry_after_s: 5,
    },
    { "retry-after": "5", ...headers },
  );
}

async function readBodyCapped(request: IncomingMessage): Promise<string | null> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of request) {
    size += (chunk as Buffer).length;
    if (size > MAX_BODY_BYTES) return null;
    chunks.push(chunk as Buffer);
  }
  return Buffer.concat(chunks).toString("utf8");
}

function parseMessages(body: string): ChatMessage[] | null {
  let parsed: { messages?: ChatMessage[] };
  try {
    parsed = JSON.parse(body);
  } catch {
    return null;
  }
  const messages = (parsed.messages ?? []).filter(
    (m) => (m.role === "user" || m.role === "assistant") && typeof m.content === "string",
  );
  if (messages.length === 0 || messages.length > MAX_MESSAGES) return null;
  // Cap total content, dropping oldest turns first (the newest ask matters most).
  let total = messages.reduce((sum, m) => sum + m.content.length, 0);
  while (messages.length > 1 && total > MAX_TOTAL_CHARS) {
    total -= messages[0].content.length;
    messages.shift();
  }
  if (total > MAX_TOTAL_CHARS) {
    messages[0] = { role: messages[0].role, content: messages[0].content.slice(-MAX_TOTAL_CHARS) };
  }
  return messages;
}

async function handleChat(
  request: IncomingMessage,
  response: ServerResponse,
  headers: Record<string, string>,
): Promise<void> {
  if (!globalBucket.take() || !perIp.take(clientIp(request))) {
    rateLimited(response, headers);
    return;
  }

  const body = await readBodyCapped(request);
  if (body === null) {
    sendJson(response, 413, { error: "too_large" }, headers);
    return;
  }
  const messages = parseMessages(body);
  if (messages === null) {
    sendJson(response, 400, { error: "bad_request" }, headers);
    return;
  }

  const apiKey = process.env.CELERIS_API_KEY ?? process.env.OPENAI_API_KEY;
  if (!apiKey) {
    sendJson(response, 500, { error: "misconfigured" }, headers);
    return;
  }

  const client = new OpenAI({ baseURL: celerisBaseUrl(), apiKey, maxRetries: 0 });
  try {
    const stream = await client.chat.completions.create({
      model: process.env.CELERIS_MODEL ?? "celeris-1",
      messages: [
        {
          role: "system",
          content: "You are a fast, friendly assistant demonstrating the Celeris API. Keep answers short.",
        },
        ...messages,
      ],
      max_tokens: MAX_TOKENS,
      temperature: 0.3,
      stream: true,
    });
    response.writeHead(200, {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
      ...headers,
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
    if (error instanceof OpenAI.APIError && error.status === 429) {
      rateLimited(response, headers);
      return;
    }
    // Log the failure class only, never the request or response content.
    console.error("upstream request failed:", error instanceof Error ? error.constructor.name : "unknown");
    sendJson(response, 502, { error: "upstream_failed" }, headers);
  }
}

const server = createServer(async (request, response) => {
  const pathname = new URL(request.url ?? "/", "http://localhost").pathname;
  const origin = request.headers.origin ?? "";

  if (request.method === "GET" && pathname === "/healthz") {
    sendJson(response, 200, { ok: true });
    return;
  }

  if (pathname !== "/api/chat") {
    response.writeHead(404).end();
    return;
  }
  if (!ALLOWED_ORIGINS.has(origin)) {
    sendJson(response, 403, { error: "origin_not_allowed" });
    return;
  }
  const headers = corsHeaders(origin);
  if (request.method === "OPTIONS") {
    response.writeHead(204, headers).end();
    return;
  }
  if (request.method !== "POST") {
    response.writeHead(405, headers).end();
    return;
  }
  await handleChat(request, response, headers);
});

server.listen(PORT, () => {
  // Startup log carries configuration shape only, no key material.
  console.log(
    `demo-proxy on :${PORT} · origins=[${[...ALLOWED_ORIGINS].join(", ")}] · ` +
      `global ${process.env.DEMO_GLOBAL_RPS ?? 2} rps · per-ip ${process.env.DEMO_PER_IP_PER_MIN ?? 6}/min`,
  );
});
