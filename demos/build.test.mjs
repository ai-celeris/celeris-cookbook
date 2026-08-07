import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(HERE);
const DIST = join(HERE, "dist");

test("all browser application recipes build from source", () => {
  execFileSync(process.execPath, [join(HERE, "build.mjs")], { cwd: ROOT, stdio: "inherit" });
  for (const name of ["chatbot", "instant-suggest", "burst-rendering"]) {
    assert.ok(existsSync(join(DIST, name, "index.html")), `${name} did not produce index.html`);
  }
});

test("generated browser bundles use relative asset URLs", () => {
  for (const name of ["chatbot", "instant-suggest", "burst-rendering"]) {
    const html = readFileSync(join(DIST, name, "index.html"), "utf8");
    assert.ok(!/(?:src|href)="\/(?!\/)/.test(html), `${name} contains a root-relative asset URL`);
  }
});

test("generated output is ignored by git", () => {
  execFileSync("git", ["check-ignore", "demos/dist/chatbot/index.html"], { cwd: ROOT });
});
