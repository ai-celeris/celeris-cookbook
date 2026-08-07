"use client";

import { useState } from "react";

// The browser only ever talks to OUR /api/generate route. The Celeris API key
// lives server-side in an environment variable; it never reaches this page.
export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);

  async function generate(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setReply("");
    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      const body = await response.json();
      setReply(response.ok ? body.reply : `Error: ${body.error}`);
    } catch (error) {
      setReply(`Error: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Celeris on Next.js</h1>
      <form onSubmit={generate}>
        <input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Ask Celeris-1 something…"
          style={{ width: "70%", padding: "0.5rem" }}
        />
        <button disabled={busy || !prompt.trim()} style={{ padding: "0.5rem 1rem", marginLeft: "0.5rem" }}>
          {busy ? "…" : "Generate"}
        </button>
      </form>
      {reply && <p style={{ whiteSpace: "pre-wrap" }}>{reply}</p>}
    </main>
  );
}
