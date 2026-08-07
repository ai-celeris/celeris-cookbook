// Chat UI: streams from the local server and measures latency in the browser
// (time-to-first-token is the showcase). Rate limits (429) are a first-class
// friendly state, not an error: deployments may deliberately use a low-RPS key.

const transcript = document.getElementById("transcript");
const composer = document.getElementById("composer");
const promptInput = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const notice = document.getElementById("notice");
const apiKeyInput = document.getElementById("api-key");

// [{role, content}], kept only in this page's memory. The standalone server
// clips history to the model's input budget; an injected deployment config can
// impose a smaller client-side request bound too.
const messages = [];

// Where inference requests go. A host may inject another API-compatible base;
// without one, the standalone example uses its own local server.
const API_BASE = window.__CELERIS_APP_CONFIG__?.apiBase ?? "api/";
const CHAT_URL = new URL("chat", new URL(API_BASE, location.href));

// Best effort: make the browser establish DNS/TLS and cache the CORS preflight
// before the first user action. A compatible application server can use this author-issued
// OPTIONS as a signal to warm its own connection to Celeris with /echo.
if (window.__CELERIS_APP_CONFIG__?.prewarm) {
  fetch(CHAT_URL, {
    method: "OPTIONS",
    mode: "cors",
    credentials: "omit",
    headers: {
      "content-type": "application/json",
      "x-celeris-warmup": "1",
    },
  }).catch(() => {});
}

function messagesForRequest() {
  const config = window.__CELERIS_APP_CONFIG__ ?? {};
  const selected = messages.slice(-(config.maxMessages ?? 8));
  const maxBodyBytes = config.maxBodyBytes ?? 7000;
  while (
    selected.length > 1 &&
    new TextEncoder().encode(JSON.stringify({ messages: selected })).byteLength > maxBodyBytes
  ) {
    selected.shift();
  }
  // A clipped conversation must not begin with an orphaned assistant reply.
  if (selected.length > 1 && selected[0].role === "assistant") selected.shift();
  return selected;
}

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
  const userBubble = addBubble("user");
  userBubble.textContent = text;
  const assistantBubble = addBubble("assistant");
  assistantBubble.classList.add("pending");

  sendButton.disabled = true;
  clearNotice();

  const headers = { "content-type": "application/json" };
  // In-memory only: read the field on each send, never store elsewhere. The
  // A deployment that owns credentials outside the page may omit the field.
  const userKey = apiKeyInput?.value.trim() ?? "";
  if (userKey) headers["x-user-api-key"] = userKey;

  const started = performance.now();
  let firstTokenAt = null;
  let reply = "";

  try {
    const response = await fetch(CHAT_URL, {
      method: "POST",
      headers,
      body: JSON.stringify({ messages: messagesForRequest() }),
    });

    if (response.status === 429) {
      messages.pop();
      userBubble.remove();
      assistantBubble.remove();
      showNotice(
        "Rate limited, the shared demo key has a low request cap. " +
          "Wait a few seconds and try again" +
          // The published embed has no own-key panel to point at.
          (apiKeyInput ? ", or expand “Use your own API key” below." : "."),
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
    userBubble.remove();
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
