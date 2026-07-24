// Chat UI: streams from the local server and measures latency in the browser
// (time-to-first-token is the showcase). Rate limits (429) are a first-class
// friendly state, not an error: hosted demos share a low-RPS key.

const transcript = document.getElementById("transcript");
const composer = document.getElementById("composer");
const promptInput = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const notice = document.getElementById("notice");
const apiKeyInput = document.getElementById("api-key");

// [{role, content}], resent whole each turn; the server clips history to the
// model's input budget.
const messages = [];

function addBubble(role) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  transcript.appendChild(bubble);
  transcript.scrollTop = transcript.scrollHeight;
  return bubble;
}

function addStats(text) {
  const stats = document.createElement("div");
  stats.className = "stats";
  stats.textContent = text;
  transcript.appendChild(stats);
  transcript.scrollTop = transcript.scrollHeight;
}

function showNotice(text, kind) {
  notice.textContent = text;
  notice.className = `notice ${kind}`;
  notice.hidden = false;
}

function clearNotice() {
  notice.hidden = true;
}

async function send(text) {
  messages.push({ role: "user", content: text });
  addBubble("user").textContent = text;
  const assistantBubble = addBubble("assistant");
  assistantBubble.classList.add("pending");

  sendButton.disabled = true;
  clearNotice();

  const headers = { "content-type": "application/json" };
  // In-memory only: read the field on each send, never store elsewhere.
  const userKey = apiKeyInput.value.trim();
  if (userKey) headers["x-user-api-key"] = userKey;

  const started = performance.now();
  let firstTokenAt = null;
  let reply = "";

  try {
    const response = await fetch("api/chat", {
      method: "POST",
      headers,
      body: JSON.stringify({ messages }),
    });

    if (response.status === 429) {
      messages.pop();
      assistantBubble.remove();
      showNotice(
        "Rate limited, the shared demo key has a low request cap. " +
          "Wait a few seconds and try again, or expand “Use your own API key” below.",
        "warn",
      );
      return;
    }
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.error ?? `HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      if (firstTokenAt === null) {
        firstTokenAt = performance.now();
        assistantBubble.classList.remove("pending");
      }
      reply += decoder.decode(value, { stream: true });
      assistantBubble.textContent = reply;
      transcript.scrollTop = transcript.scrollHeight;
    }

    messages.push({ role: "assistant", content: reply });
    const total = performance.now() - started;
    const ttft = firstTokenAt === null ? total : firstTokenAt - started;
    const streamMs = total - ttft;
    // celeris-1 is a diffusion model: it usually generates the whole reply in
    // parallel and the stream arrives as one burst, so a chars/s figure over
    // the (near-zero) stream window is meaningless. Only show a rate when the
    // delivery was actually spread out.
    const rate =
      streamMs > 50
        ? ` · ${Math.round(reply.length / (streamMs / 1000))} chars/s`
        : ` · ${reply.length} chars in one burst`;
    addStats(
      `first token ${Math.round(ttft)} ms · total ${Math.round(total)} ms${rate}`,
    );
  } catch (error) {
    messages.pop();
    assistantBubble.remove();
    showNotice(`Request failed: ${error.message}. Check the server logs and try again.`, "error");
  } finally {
    sendButton.disabled = false;
    promptInput.focus();
  }
}

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = promptInput.value.trim();
  if (!text || sendButton.disabled) return;
  promptInput.value = "";
  send(text);
});
