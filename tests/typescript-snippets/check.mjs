import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const GUIDE = resolve(HERE, "../../guides/compatibility.md");
const TSC = resolve(HERE, "node_modules/.bin/tsc");
const TSX = resolve(HERE, "node_modules/.bin/tsx");

const snippets = [...readFileSync(GUIDE, "utf8").matchAll(/```ts[^\n]*\n([\s\S]*?)```/g)].map(
  (match) => match[1],
);
if (snippets.length !== 2) {
  throw new Error(`expected 2 TypeScript snippets, found ${snippets.length}`);
}

const requests = [];
const server = createServer((request, response) => {
  const chunks = [];
  request.on("data", (chunk) => chunks.push(chunk));
  request.on("end", () => {
    const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    requests.push({ path: request.url, body });
    const payload = JSON.stringify({
      id: "chatcmpl-snippet",
      object: "chat.completion",
      created: 0,
      model: body.model,
      choices: [
        {
          index: 0,
          message: { role: "assistant", content: "Hello from the snippet test." },
          finish_reason: "stop",
        },
      ],
      usage: { prompt_tokens: 5, completion_tokens: 6, total_tokens: 11 },
    });
    response.writeHead(200, {
      "content-type": "application/json",
      "content-length": Buffer.byteLength(payload),
    });
    response.end(payload);
  });
});

function run(command, args, env = process.env) {
  return new Promise((resolveRun, reject) => {
    const child = spawn(command, args, { cwd: HERE, env, stdio: "inherit" });
    child.on("error", reject);
    child.on("exit", (code, signal) => {
      if (code === 0) resolveRun();
      else reject(new Error(`${command} exited with ${code ?? signal}`));
    });
  });
}

await new Promise((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
const address = server.address();
if (!address || typeof address === "string") throw new Error("snippet server did not bind");

const generated = mkdtempSync(join(HERE, ".generated-"));
try {
  for (const [index, snippet] of snippets.entries()) {
    const file = join(generated, `snippet-${index + 1}.mts`);
    writeFileSync(file, snippet);
    await run(TSC, [
      "--ignoreConfig",
      "--strict",
      "--noEmit",
      "--target",
      "ES2022",
      "--module",
      "NodeNext",
      "--moduleResolution",
      "NodeNext",
      "--skipLibCheck",
      "--types",
      "node",
      file,
    ]);
    await run(TSX, [file], {
      ...process.env,
      CELERIS_BASE_URL: `http://127.0.0.1:${address.port}/v1`,
      CELERIS_API_KEY: "snippet-test-key",
    });
  }

  if (requests.length !== snippets.length) {
    throw new Error(`expected ${snippets.length} requests, received ${requests.length}`);
  }
  for (const { path, body } of requests) {
    if (path !== "/v1/chat/completions") throw new Error(`unexpected request path: ${path}`);
    if (body.model !== "celeris-1") throw new Error(`unexpected model: ${body.model}`);
    if (body.max_tokens !== 256) throw new Error(`unexpected max_tokens: ${body.max_tokens}`);
  }
  console.log(`${snippets.length} TypeScript snippets type-check and execute`);
} finally {
  rmSync(generated, { recursive: true, force: true });
  await new Promise((resolveClose, reject) =>
    server.close((error) => (error ? reject(error) : resolveClose())),
  );
}
