// Celeris token-window budgeting.
//
// Requests share a 4096-token total window between input and output. The wire
// max_tokens value must be a multiple of 256 in [256, 1024]; whatever it
// reserves leaves 4096 - max_tokens tokens for all input messages combined.

export const TOTAL_TOKEN_LIMIT = 4096;
export const MIN_OUTPUT_TOKENS = 256;
export const MAX_OUTPUT_TOKENS = 1024;
export const OUTPUT_TOKEN_STEP = 256;

// Celeris does not expose its tokenizer; ~4 bytes/token is a serviceable
// estimate, with a small allowance for the chat template.
const ESTIMATED_BYTES_PER_TOKEN = 4;
const CHAT_BASE_TOKENS = 8;
const CHAT_MESSAGE_TOKENS = 4;

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

/** Round up to a supported 256-token step, clamped to [256, 1024]. */
export function normalizeMaxTokens(requested: number): number {
  if (requested <= MIN_OUTPUT_TOKENS) return MIN_OUTPUT_TOKENS;
  if (requested >= MAX_OUTPUT_TOKENS) return MAX_OUTPUT_TOKENS;
  return Math.ceil(requested / OUTPUT_TOKEN_STEP) * OUTPUT_TOKEN_STEP;
}

/** Tokens left for ALL input messages after the output reservation. */
export function inputTokenBudget(maxTokens: number): number {
  return TOTAL_TOKEN_LIMIT - normalizeMaxTokens(maxTokens);
}

function estimateTokens(messages: ChatMessage[]): number {
  let bytes = 0;
  for (const message of messages) {
    bytes += Buffer.byteLength(message.content, "utf8");
  }
  return (
    CHAT_BASE_TOKENS +
    messages.length * CHAT_MESSAGE_TOKENS +
    Math.ceil(bytes / ESTIMATED_BYTES_PER_TOKEN)
  );
}

/**
 * Fit a conversation into the input budget: keep the system prompt and the
 * newest turns, dropping the oldest history first. The latest user message is
 * always kept (clipped if it alone overflows).
 */
export function fitConversation(
  system: string,
  history: ChatMessage[],
  maxTokens: number,
): ChatMessage[] {
  const systemMessage: ChatMessage = { role: "system", content: system };
  const budget = inputTokenBudget(maxTokens);

  let kept = [...history];
  while (kept.length > 1 && estimateTokens([systemMessage, ...kept]) > budget) {
    kept = kept.slice(1); // drop the oldest turn
  }

  if (kept.length === 1 && estimateTokens([systemMessage, ...kept]) > budget) {
    const overheadTokens =
      CHAT_BASE_TOKENS +
      2 * CHAT_MESSAGE_TOKENS +
      Math.ceil(Buffer.byteLength(system, "utf8") / ESTIMATED_BYTES_PER_TOKEN);
    const maxBytes = Math.max(budget - overheadTokens, 0) * ESTIMATED_BYTES_PER_TOKEN;
    const encoded = Buffer.from(kept[0].content, "utf8");
    kept = [
      {
        role: kept[0].role,
        content: encoded.subarray(0, maxBytes).toString("utf8"),
      },
    ];
  }

  return [systemMessage, ...kept];
}
