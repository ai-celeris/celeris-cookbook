#!/usr/bin/env node
// Build the embeddable demo pages.
//
// Each cookbook browser app becomes a self-contained static page under
// dist/<name>/, served by the docs site at /cookbook-demos/<name>/ and shown
// in an iframe on that app's cookbook page. Output is committed; CI rebuilds
// it and fails on a diff, so the published demos can never drift from source.
//
//   node demos/build.mjs

import { execFileSync } from "node:child_process";
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(HERE);
const DIST = join(HERE, "dist");

// Where the embedded apps send inference requests. In production this is the
// docs site's own origin, routed to the shared proxy. Overridable so a local
// run can point at a proxy on another port; committed output always uses the
// default.
const API_BASE = process.env.CELERIS_DEMO_API_BASE || "/cookbook-api/";

export const DEMOS = [
  { name: "chatbot", kind: "static" },
  { name: "instant-suggest", kind: "static" },
  { name: "burst-rendering", kind: "vite" },
];

/** Turn an example's standalone page into its embedded form. */
function embedHtml(html) {
  return (
    html
      // The docs content policy allows same-origin connections only, so the
      // direct bring-your-own-key path cannot work inside an embed. A docs
      // page is also the wrong place to invite pasting a key.
      .replace(/\n?\s*<details class="own-key">[\s\S]*?<\/details>\n?/, "\n")
      .replace("<body>", "<body data-embed>")
      .replace(
        "</head>",
        `<script>window.__CELERIS_DEMO__ = ${JSON.stringify({ apiBase: API_BASE })};</script>\n</head>`,
      )
      .replace("</body>", '<script src="embed.js"></script>\n</body>')
  );
}

function buildStatic(name) {
  const source = join(ROOT, "examples", name, "public");
  const target = join(DIST, name);
  mkdirSync(target, { recursive: true });
  for (const file of ["app.js", "style.css"]) {
    cpSync(join(source, file), join(target, file));
  }
  writeFileSync(join(target, "index.html"), embedHtml(readFileSync(join(source, "index.html"), "utf8")));
}

function buildVite(name) {
  const example = join(ROOT, "examples", name);
  const target = join(DIST, name);
  // Relative base: the page is served from /cookbook-demos/<name>/, not root.
  execFileSync("npm", ["run", "build", "--", "--base=./", `--outDir=${target}`, "--emptyOutDir"], {
    cwd: example,
    stdio: "inherit",
  });
  writeFileSync(join(target, "index.html"), embedHtml(readFileSync(join(target, "index.html"), "utf8")));
}

export function buildDemo(name) {
  const demo = DEMOS.find((entry) => entry.name === name);
  if (!demo) throw new Error(`unknown demo: ${name}`);
  if (demo.kind === "vite") buildVite(name);
  else buildStatic(name);
  cpSync(join(HERE, "embed.js"), join(DIST, name, "embed.js"));
  console.log(`demos: built ${name}`);
}

function main() {
  rmSync(DIST, { recursive: true, force: true });
  mkdirSync(DIST, { recursive: true });
  for (const demo of DEMOS) buildDemo(demo.name);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main();
