// Live regex synthesis. On every typing pause (400 ms), send the description
// to the local server, cancel any in-flight request, and re-check the test
// strings against the new regex right here in the browser. The regex check is
// deterministic and local; only the synthesis calls the model.

const DEBOUNCE_MS = 400;

const description = document.getElementById("description");
const tests = document.getElementById("tests");
const regexOutput = document.getElementById("regex");
const explanation = document.getElementById("explanation");
const latency = document.getElementById("latency");
const status = document.getElementById("status");
const testResults = document.getElementById("test-results");

let debounceTimer = null;
let inFlight = null;
let currentRegex = null;

function showStatus(text) {
  status.textContent = text;
  status.hidden = !text;
}

function runTests() {
  testResults.innerHTML = "";
  if (!currentRegex) return;
  let compiled;
  try {
    compiled = new RegExp(currentRegex);
  } catch (error) {
    const item = document.createElement("li");
    item.className = "invalid";
    item.textContent = `Regex does not compile: ${error.message}`;
    testResults.appendChild(item);
    return;
  }
  for (const line of tests.value.split("\n")) {
    if (!line.trim()) continue;
    const item = document.createElement("li");
    const matched = compiled.test(line);
    item.className = matched ? "match" : "no-match";
    item.textContent = `${matched ? "matches" : "no match"}  ${line}`;
    testResults.appendChild(item);
  }
}

async function synthesize() {
  const text = description.value.trim();
  if (!text) return;

  if (inFlight) inFlight.abort();
  const controller = new AbortController();
  inFlight = controller;

  showStatus("synthesizing…");
  const started = performance.now();
  try {
    const response = await fetch("api/synthesize", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ description: text }),
      signal: controller.signal,
    });
    if (response.status === 429) {
      showStatus("Rate limited. Pause a moment and keep typing.");
      return;
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      showStatus(`Synthesis failed (${body.error ?? response.status}). Keep typing to retry.`);
      return;
    }
    const body = await response.json();
    const totalMs = Math.round(performance.now() - started);

    currentRegex = body.regex;
    regexOutput.textContent = body.regex;
    explanation.textContent = body.explanation;
    latency.textContent = `synthesized in ${totalMs} ms (${body.server_ms} ms model time)`;
    showStatus("");
    runTests();
  } catch (error) {
    if (error.name !== "AbortError") {
      showStatus(`Request failed: ${error.message}`);
    }
  } finally {
    if (inFlight === controller) inFlight = null;
  }
}

description.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(synthesize, DEBOUNCE_MS);
});

tests.addEventListener("input", runTests);
