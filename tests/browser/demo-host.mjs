import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

const root = new URL("../../demos/dist/", import.meta.url).pathname;
let lastChat = null;

const types = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};

function hostPage(slug) {
  return `<!doctype html><html data-theme="light"><body>
    <button id="theme">Toggle theme</button>
    <iframe id="demo" title="${slug} interactive demo" src="/cookbook-demos/${slug}/?theme=light"></iframe>
    <script>
      const frame = document.getElementById("demo");
      addEventListener("message", (event) => {
        if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
        if (event.data?.type === "celeris-demo-height") {
          frame.style.height = Math.min(Math.max(event.data.height, 240), 1200) + "px";
        }
      });
      document.getElementById("theme").onclick = () => {
        const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = theme;
        frame.contentWindow.postMessage({type: "celeris-demo-theme", theme}, location.origin);
      };
    </script>
  </body></html>`;
}

createServer(async (request, response) => {
  const url = new URL(request.url, "http://127.0.0.1:4178");
  if (url.pathname.startsWith("/host/")) {
    response.setHeader("content-type", types[".html"]);
    response.end(hostPage(url.pathname.split("/").pop()));
    return;
  }
  if (url.pathname === "/cookbook-api/chat" && request.method === "POST") {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    lastChat = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    response.setHeader("content-type", "text/plain; charset=utf-8");
    response.end("Fast reply <script>window.__demoXss = true</script>");
    return;
  }
  if (url.pathname === "/cookbook-api/synthesize" && request.method === "POST") {
    response.setHeader("content-type", "application/json; charset=utf-8");
    response.end(JSON.stringify({ regex: "^hello$", explanation: "An exact match.", server_ms: 12 }));
    return;
  }
  if (url.pathname === "/__last-chat") {
    response.setHeader("content-type", "application/json; charset=utf-8");
    response.end(JSON.stringify(lastChat));
    return;
  }
  if (url.pathname.startsWith("/cookbook-demos/")) {
    const relative = url.pathname.slice("/cookbook-demos/".length).replace(/\/$/, "/index.html");
    const path = normalize(join(root, relative));
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
