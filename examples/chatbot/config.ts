// Endpoint + credential resolution, kept in one place on purpose.
//
// The web client never talks to Celeris directly: it talks to this server,
// which holds the credential. That is exactly the shape a future hosted demo
// takes — swap this module's env lookup for a shared low-RPS proxy key or a
// workspace-aware (Cognito-backed) key lookup and nothing else changes.
//
// Credential precedence per request:
//   1. A user-supplied key forwarded by the browser (in-memory only, sent as
//      the x-user-api-key header) — lets users bypass a shared rate-limited
//      key with their own.
//   2. The server's own key from CELERIS_API_KEY / OPENAI_API_KEY.

export interface Upstream {
  baseURL: string;
  apiKey: string;
  model: string;
  /** True when the request runs on the caller's own key, not the server's. */
  userSupplied: boolean;
}

export function resolveUpstream(userApiKey?: string): Upstream {
  const baseURL =
    process.env.CELERIS_BASE_URL?.trim() || process.env.OPENAI_BASE_URL?.trim();
  if (!baseURL) {
    throw new Error("Set CELERIS_BASE_URL (or OPENAI_BASE_URL) first.");
  }

  const serverKey =
    process.env.CELERIS_API_KEY?.trim() || process.env.OPENAI_API_KEY?.trim();
  const apiKey = userApiKey?.trim() || serverKey;
  if (!apiKey) {
    throw new Error("Set CELERIS_API_KEY (or OPENAI_API_KEY) first.");
  }

  return {
    baseURL,
    apiKey,
    model: process.env.CELERIS_MODEL?.trim() || "celeris-1",
    userSupplied: Boolean(userApiKey?.trim()),
  };
}
