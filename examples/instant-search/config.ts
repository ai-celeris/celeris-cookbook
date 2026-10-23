export interface Upstream {
  baseURL: string;
  apiKey: string;
  model: string;
}

export function resolveUpstream(userApiKey?: string): Upstream {
  const root =
    process.env.CELERIS_BASE_URL?.trim() || process.env.OPENAI_BASE_URL?.trim();
  if (!root) throw new Error("Set CELERIS_BASE_URL (or OPENAI_BASE_URL) first.");
  const trimmed = root.replace(/\/+$/, "");
  const baseURL = trimmed.endsWith("/v1") ? trimmed : `${trimmed}/v1`;
  const serverKey =
    process.env.CELERIS_API_KEY?.trim() || process.env.OPENAI_API_KEY?.trim();
  const apiKey = userApiKey?.trim() || serverKey;
  if (!apiKey) throw new Error("Set CELERIS_API_KEY (or OPENAI_API_KEY) first.");
  return {
    baseURL,
    apiKey,
    model: process.env.CELERIS_MODEL?.trim() || "celeris-1",
  };
}
