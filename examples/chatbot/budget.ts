// Celeris token-window budgeting.
//
// Requests have an 8192-token total window and a separate 2048-token input
// cap. General requests default to 2048 output tokens; explicitly short tasks
// can reserve less.

export const TOTAL_TOKEN_LIMIT = 8192;
export const MAX_INPUT_TOKENS = 2048;
export const DEFAULT_MAX_OUTPUT_TOKENS = 2048;

// Celeris does not expose its tokenizer; ~4 bytes/token is a serviceable
// estimate, with a small allowance for the chat template.
const ESTIMATED_BYTES_PER_TOKEN = 4;
const CHAT_BASE_TOKENS = 8;
const CHAT_MESSAGE_TOKENS = 4;

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

/** Maximum input tokens allowed with this output reservation. */
export function inputTokenBudget(maxTokens = DEFAULT_MAX_OUTPUT_TOKENS): number {
  if (maxTokens <= 0 || maxTokens >= TOTAL_TOKEN_LIMIT) {
    throw new RangeError("maxTokens must be between 1 and 8191");
  }
  return Math.min(MAX_INPUT_TOKENS, TOTAL_TOKEN_LIMIT - maxTokens);
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
