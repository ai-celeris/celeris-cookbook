// Build-output contract for the embeddable demos. These run after
// `node demos/build.mjs`, so CI builds first and then asserts.
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const HERE = dirname(fileURLToPath(import.meta.url));
const DIST = join(HERE, "dist");
const EXAMPLES = join(dirname(HERE), "examples");

test("burst-rendering demo is built", () => {
  const dir = join(DIST, "burst-rendering");
  assert.ok(existsSync(join(dir, "index.html")), "index.html missing");
  assert.ok(existsSync(join(dir, "embed.js")), "embed.js missing");
});

test("burst-rendering assets are referenced relatively", () => {
  const html = readFileSync(join(DIST, "burst-rendering", "index.html"), "utf8");
  assert.ok(!/(?:src|href)="\/(?!\/)/.test(html), "absolute asset path would 404 under /cookbook-demos/");
});

test("every demo loads the embed bridge", () => {
  for (const name of ["chatbot", "instant-suggest", "burst-rendering"]) {
    const html = readFileSync(join(DIST, name, "index.html"), "utf8");
    assert.match(html, /<script src="embed\.js"><\/script>/);
  }
});

// Regression guard. The host sizes the iframe from what embed.js reports, and
// documentElement's box is clamped to that viewport, so measuring it feeds our
// own answer back and the frame latches at its smallest value. Measure content.
test("the embed bridge measures content height, not the root element box", () => {
  const bridge = readFileSync(join(HERE, "embed.js"), "utf8");
  assert.match(bridge, /body\.scrollHeight/, "height must come from content");
  assert.ok(
    !/documentElement\.getBoundingClientRect/.test(bridge),
    "measuring documentElement's box latches the frame at its minimum height",
  );
});

test("the embed bridge only exchanges messages with its same-origin host", () => {
  const bridge = readFileSync(join(HERE, "embed.js"), "utf8");
  assert.match(bridge, /event\.source !== parent/);
  assert.match(bridge, /event\.origin !== hostOrigin/);
  assert.match(bridge, /postMessage\([^;]+hostOrigin\)/s);
  assert.ok(!bridge.includes('postMessage({ type: "celeris-demo-height", height: height }, "*")'));
});

test("inference demos point at the shared proxy", () => {
  for (const name of ["chatbot", "instant-suggest"]) {
    const html = readFileSync(join(DIST, name, "index.html"), "utf8");
    assert.match(
      html,
      /window\.__CELERIS_DEMO__ = \{"apiBase":"\/cookbook-api\/","maxBodyBytes":7000,"maxMessages":8\}/,
    );
    assert.match(html, /<body data-embed>/);
  }
});

test("the shared chatbot bounds history before it reaches the edge", () => {
  const source = readFileSync(join(EXAMPLES, "chatbot", "public", "app.js"), "utf8");
  assert.match(source, /new TextEncoder\(\)/);
  assert.match(source, /messagesForRequest\(\)/);
  assert.match(source, /config\.maxBodyBytes/);
});

test("demo app.js is copied unmodified from the example", () => {
  for (const name of ["chatbot", "instant-suggest"]) {
    const built = readFileSync(join(DIST, name, "app.js"), "utf8");
    const source = readFileSync(join(EXAMPLES, name, "public", "app.js"), "utf8");
    assert.equal(built, source, `${name} app.js diverged from the example`);
  }
});

test("the chatbot embed drops the bring-your-own-key panel", () => {
  // The docs content policy allows same-origin connections only, so a direct
  // browser call to the inference host cannot work here.
  const html = readFileSync(join(DIST, "chatbot", "index.html"), "utf8");
  assert.ok(!html.includes("Use your own API key"), "own-key panel must not ship in the embed");
});

test("the chatbot client survives the missing own-key field", () => {
  // Stripping the panel removes #api-key, so every read of it must be
  // optional or the first send throws.
  const source = readFileSync(join(EXAMPLES, "chatbot", "public", "app.js"), "utf8");
  const reads = source.match(/apiKeyInput[.?]/g) ?? [];
  assert.ok(reads.length > 0, "expected the client to reference the own-key field");
  for (const read of reads) {
    assert.equal(read, "apiKeyInput?", "every own-key field access must be optional");
  }
});
