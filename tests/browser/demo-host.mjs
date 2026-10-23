import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

const root = new URL("../../examples/", import.meta.url).pathname;
let lastChat = null;

const types = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};

createServer(async (request, response) => {
  const url = new URL(request.url, "http://127.0.0.1:4178");
  if (url.pathname === "/apps/chatbot/api/chat" && request.method === "POST") {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    lastChat = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    await new Promise((resolve) => setTimeout(resolve, 20));
    response.setHeader("content-type", "text/plain; charset=utf-8");
    response.setHeader("server-timing", "routing;dur=1.2, processing;dur=12.4");
    response.end("Fast reply <script>window.__demoXss = true</script>");
    return;
  }
  if (url.pathname === "/apps/instant-suggest/api/synthesize" && request.method === "POST") {
    response.setHeader("content-type", "application/json; charset=utf-8");
    response.end(JSON.stringify({ regex: "^hello$", explanation: "An exact match.", server_ms: 12 }));
    return;
  }
  if (url.pathname === "/apps/instant-search/api/search" && request.method === "POST") {
    response.setHeader("content-type", "application/json; charset=utf-8");
    response.end(JSON.stringify({
      raw_results: [],
      results: [{
        title: "Rate limits and 429 responses",
        body: "Requests over your limit return HTTP 429.",
      }],
      keywords: ["rate limiting", "throttling"],
      server_ms: 14,
    }));
    return;
  }
  if (url.pathname === "/__last-chat") {
    response.setHeader("content-type", "application/json; charset=utf-8");
    response.end(JSON.stringify(lastChat));
    return;
  }
  if (url.pathname.startsWith("/apps/")) {
    const [slug, ...requested] = url.pathname.slice("/apps/".length).split("/").filter(Boolean);
    const assets = requested.length ? requested : ["index.html"];
    const path = normalize(join(root, slug, "public", ...assets));
    if (!path.startsWith(root)) {
      response.writeHead(404).end();
      return;
    }
    try {
      response.setHeader("content-type", types[extname(path)] ?? "application/octet-stream");
      response.end(await readFile(path));
    } catch {
      response.writeHead(404).end();
    }
    return;
  }
  response.writeHead(404).end();
}).listen(4178, "127.0.0.1");
