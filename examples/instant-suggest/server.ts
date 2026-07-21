// Instant regex suggestion server.
//
// Serves the static UI from public/ and exposes POST /api/synthesize: it
// takes a plain-English description and returns a regex with a short
// explanation. The browser calls it on every typing pause, so the whole
// point is that one synthesis costs a few hundred milliseconds.
//
//   npm install
//   export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
//   export CELERIS_API_KEY="<your-api-key>"
//   npm start          # http://localhost:8788

import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import OpenAI from "openai";

import { resolveUpstream } from "./config.ts";

const PORT = Number(process.env.PORT ?? 8788);
const PUBLIC_DIR = new URL("./public/", import.meta.url).pathname;
const MAX_DESCRIPTION_CHARS = 500;

const CONTENT_TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
};

// max_tokens must be a multiple of 256 in [256, 1024]. A regex plus a short
// explanation fits comfortably in the smallest step.
const MAX_TOKENS = 256;

const PROMPT = `Write ONE JavaScript regular expression for the description below.
Reply with ONLY a JSON object: {"regex": "...", "explanation": "..."}.
The regex value is the pattern only, without surrounding slashes or flags.
Keep the explanation to one short sentence.

Description: `;

function parseSuggestion(output: string): { regex: string; explanation: string } | null {
  const cleaned = output.replace(/^```(?:json)?\s*|\s*```$/g, "").trim();
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  const slice = cleaned.slice(start, end + 1);
  // Regex patterns are full of backslashes and the model sometimes emits
  // them singly (\d), which is invalid JSON. Try as-is first, then with
  // lone backslashes doubled.
  for (const candidate of [slice, slice.replace(/\\(?![\\"/bfnrtu])/g, "\\\\")]) {
    try {
      const parsed = JSON.parse(candidate);
      if (typeof parsed.regex === "string" && parsed.regex.length > 0) {
        return { regex: parsed.regex, explanation: String(parsed.explanation ?? "") };
      }
    } catch {
      // try the next candidate
    }
  }
  return null;
}

async function readBody(request: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString("utf8");
}

function sendJson(response: ServerResponse, status: number, body: unknown): void {
  response.writeHead(status, { "content-type": "application/json", "cache-control": "no-store" });
  response.end(JSON.stringify(body));
}

async function handleSynthesize(request: IncomingMessage, response: ServerResponse): Promise<void> {
  let description: string;
  try {
    const parsed = JSON.parse(await readBody(request));
    description = String(parsed.description ?? "").trim().slice(0, MAX_DESCRIPTION_CHARS);
    if (!description) throw new Error("empty");
  } catch {
    sendJson(response, 400, { error: "description required" });
    return;
  }

  // Same credential seam as the chatbot example: an optional user-supplied
  // key travels per-request in this header, in memory only, never logged.
  const userKeyHeader = request.headers["x-user-api-key"];
  const userApiKey = Array.isArray(userKeyHeader) ? userKeyHeader[0] : userKeyHeader;

  let upstream;
  try {
    upstream = resolveUpstream(userApiKey);
  } catch (error) {
    sendJson(response, 500, { error: "misconfigured", detail: String(error) });
    return;
  }

  const client = new OpenAI({
    baseURL: upstream.baseURL,
    apiKey: upstream.apiKey,
    maxRetries: 0,
  });

  const started = performance.now();
  try {
    const completion = await client.chat.completions.create({
      model: upstream.model,
      messages: [{ role: "user", content: PROMPT + description }],
      max_tokens: MAX_TOKENS,
      temperature: 0,
    });
    const serverMs = Math.round(performance.now() - started);
    const suggestion = parseSuggestion(completion.choices[0]?.message?.content ?? "");
    if (!suggestion) {
      sendJson(response, 502, { error: "unparseable", server_ms: serverMs });
      return;
    }
    sendJson(response, 200, { ...suggestion, server_ms: serverMs });
  } catch (error) {
    if (error instanceof OpenAI.APIError && error.status === 429) {
      sendJson(response, 429, { error: "rate_limited" });
      return;
    }
    console.error("synthesis failed:", error instanceof Error ? error.message : error);
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
  if (request.method === "POST" && pathname === "/api/synthesize") {
    await handleSynthesize(request, response);
  } else if (request.method === "GET" && pathname === "/api/health") {
    sendJson(response, 200, { ok: true });
  } else if (request.method === "GET") {
    await handleStatic(pathname, response);
  } else {
    response.writeHead(405).end();
  }
});

server.listen(PORT, () => {
  console.log(`instant-suggest listening on http://localhost:${PORT}`);
});
