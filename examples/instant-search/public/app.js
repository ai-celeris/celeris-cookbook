const DEBOUNCE_MS = 250;
const API_BASE = window.__CELERIS_APP_CONFIG__?.apiBase ?? "api/";
const SEARCH_URL = new URL("search", new URL(API_BASE, location.href));

if (window.__CELERIS_APP_CONFIG__?.prewarm) {
  fetch(SEARCH_URL, { method: "OPTIONS", mode: "cors", credentials: "omit" }).catch(() => {});
}

const form = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const apiKeyInput = document.getElementById("api-key");
const searchButton = document.getElementById("search-button");
const status = document.getElementById("status");
const rawResults = document.getElementById("raw-results");
const understoodResults = document.getElementById("understood-results");
const keywords = document.getElementById("keywords");
const latency = document.getElementById("latency");

let timer = null;
let inFlight = null;

function setStatus(message, isError = false) {
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function renderResults(target, documents) {
  target.replaceChildren();
  if (!documents.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No matching documents";
    target.appendChild(empty);
    return;
  }
  for (const result of documents) {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    const body = document.createElement("p");
    title.textContent = result.title;
    body.textContent = result.body;
    item.append(title, body);
    target.appendChild(item);
  }
}

function renderKeywords(items) {
  keywords.replaceChildren();
  for (const item of items ?? []) {
    const term = document.createElement("span");
    term.className = "keyword";
    term.textContent = item;
    keywords.appendChild(term);
  }
}

async function search() {
  const query = queryInput.value.trim();
  if (!query) {
    setStatus("Enter a question to search.", true);
    return;
  }

  inFlight?.abort();
  const controller = new AbortController();
  inFlight = controller;
  searchButton.disabled = true;
  setStatus("Understanding your query…");

  try {
    const headers = { "content-type": "application/json" };
    if (apiKeyInput.value.trim()) headers["x-user-api-key"] = apiKeyInput.value.trim();
    const response = await fetch(SEARCH_URL, {
      method: "POST",
      headers,
      body: JSON.stringify({ query }),
      signal: controller.signal,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(
        body.error === "misconfigured"
          ? "This demo needs a Celeris API key."
          : "Search failed. Try again.",
      );
    }

    renderResults(rawResults, body.raw_results ?? []);
    renderResults(understoodResults, body.results ?? []);
    renderKeywords(body.keywords);
    latency.textContent = `${body.server_ms} ms model time`;
    setStatus(body.fallback ?? `Rewritten as ${body.keywords.join(", ")}`);
  } catch (error) {
    if (error.name !== "AbortError") setStatus(error.message, true);
  } finally {
    if (inFlight === controller) {
      inFlight = null;
      searchButton.disabled = false;
    }
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  clearTimeout(timer);
  search();
});

queryInput.addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(search, DEBOUNCE_MS);
});

for (const example of document.querySelectorAll("[data-query]")) {
  example.addEventListener("click", () => {
    queryInput.value = example.dataset.query;
    search();
  });
}

search();
