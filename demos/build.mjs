#!/usr/bin/env node
// Build the browser application recipes into static, deployable directories.
//
// This repository owns only the ordinary application build. A consumer that
// embeds or hosts these apps is responsible for any deployment-specific
// configuration and packaging after this command completes.
//
//   npm run build:apps                       # build every browser app
//   npm run build:apps -- chatbot            # build selected apps

import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(HERE);
const DIST = join(HERE, "dist");

export const APPS = [
  { name: "chatbot", kind: "static" },
  { name: "instant-suggest", kind: "static" },
  { name: "instant-search", kind: "static" },
  { name: "burst-rendering", kind: "vite" },
];

function buildStatic(name) {
  cpSync(join(ROOT, "examples", name, "public"), join(DIST, name), { recursive: true });
}

function buildVite(name) {
  const source = join(ROOT, "examples", name);
  const target = join(DIST, name);
  if (!existsSync(join(source, "node_modules", ".bin", "vite"))) {
    execFileSync("npm", ["ci"], { cwd: source, stdio: "inherit" });
  }
  execFileSync("npm", ["run", "build", "--", "--base=./", `--outDir=${target}`, "--emptyOutDir"], {
    cwd: source,
    stdio: "inherit",
  });
}

export function buildApp(name) {
  const app = APPS.find((candidate) => candidate.name === name);
  if (!app) throw new Error(`unknown browser app: ${name}`);
  mkdirSync(DIST, { recursive: true });
  rmSync(join(DIST, name), { recursive: true, force: true });
  if (app.kind === "vite") buildVite(name);
  else buildStatic(name);
  console.log(`browser apps: built ${name}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const requested = process.argv.slice(2);
  if (requested.length === 0) rmSync(DIST, { recursive: true, force: true });
  for (const name of requested.length ? requested : APPS.map(({ name }) => name)) buildApp(name);
}
