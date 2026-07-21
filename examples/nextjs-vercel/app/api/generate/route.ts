// The one server-side file that talks to Celeris. Runs only on the server
// (Vercel function / Node process). The API key comes from the environment:
// locally from your shell, in production from Vercel's encrypted env store.
// It never ships to the browser.

import OpenAI from "openai";

// CELERIS_BASE_URL is the endpoint root (no /v1); the OpenAI SDK wants the
// versioned path, so append /v1 unless it is already there.
function celerisBaseUrl(): string {
  const root = (process.env.CELERIS_BASE_URL ?? process.env.OPENAI_BASE_URL ?? "").replace(/\/+$/, "");
  return root.endsWith("/v1") ? root : `${root}/v1`;
}

// Celeris accepts max_tokens only as a multiple of 256 in [256, 1024], inside
// a 4096-token total window shared with the input.
function normalizeMaxTokens(requested: number): number {
  return Math.min(Math.max(Math.ceil(requested / 256) * 256, 256), 1024);
}

export async function POST(request: Request) {
  const { prompt } = await request.json().catch(() => ({ prompt: "" }));
  if (typeof prompt !== "string" || !prompt.trim()) {
    return Response.json({ error: "prompt required" }, { status: 400 });
  }

  const apiKey = process.env.CELERIS_API_KEY ?? process.env.OPENAI_API_KEY;
  if (!apiKey || !process.env.CELERIS_BASE_URL) {
    return Response.json({ error: "server missing CELERIS_BASE_URL / CELERIS_API_KEY" }, { status: 500 });
  }

  const client = new OpenAI({ baseURL: celerisBaseUrl(), apiKey });
  try {
    const completion = await client.chat.completions.create({
      model: process.env.CELERIS_MODEL ?? "celeris-1",
      messages: [{ role: "user", content: prompt.slice(0, 8000) }],
      max_tokens: normalizeMaxTokens(512),
      temperature: 0.3,
    });
    return Response.json({ reply: completion.choices[0]?.message?.content ?? "" });
  } catch {
    return Response.json({ error: "upstream request failed" }, { status: 502 });
  }
}
