#!/usr/bin/env python3
"""Query understanding in front of search, fast enough to run per keystroke pause.

Rewrites a natural-language query into search keywords with celeris-1, then
runs both the original and rewritten query against a toy in-memory index.
The index is deliberately simple keyword matching; the model call is the
point. Measures rewrite latency per query.

Usage:
    export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
    export CELERIS_API_KEY="<your-api-key>"
    pip install -r requirements.txt
    python3 main.py                  # run the built-in demo queries
    python3 main.py --interactive    # type queries yourself
"""

import argparse
import json
import os
import re
import sys
import time

from openai import APIStatusError, OpenAI

# --- Toy corpus and keyword index --------------------------------------------

DOCS = [
    ("Resetting your password", "Use the account settings page to reset a forgotten password or rotate credentials."),
    ("API key rotation", "Rotate API keys from the console. Old keys keep working for one hour after rotation."),
    ("Rate limits and 429 responses", "Requests over your workspace limit return HTTP 429 with a Retry-After header."),
    ("Retry strategies", "Use exponential backoff with jitter when a request fails with 429 or 5xx."),
    ("Billing and invoices", "Invoices are issued monthly. Download PDF invoices from the billing page."),
    ("Refund policy", "Unused prepaid credits are refundable within 30 days of purchase."),
    ("Team roles and permissions", "Owners can invite members and change roles. Viewers have read-only access."),
    ("Webhook delivery", "Webhooks retry failed deliveries five times with increasing delay."),
    ("Streaming responses", "Set stream true to receive the reply as server-sent events."),
    ("Request timeouts", "The default client timeout is 60 seconds. Long requests should stream."),
    ("Data retention", "Request and response bodies are retained for 30 days, then deleted."),
    ("Exporting usage data", "Usage exports are available as daily CSV files per workspace."),
    ("Single sign-on setup", "Configure SAML SSO from the security settings. SCIM sync is optional."),
    ("Error codes reference", "4xx codes are request problems. 5xx codes are service problems. 429 is rate limiting."),
    ("Deleting your account", "Account deletion removes all workspace data after a 7 day grace period."),
    ("Regions and data residency", "Workspaces pin to one region. Data does not leave the pinned region."),
]

WORD = re.compile(r"[a-z0-9]+")


def search(query_terms: list, limit: int = 3) -> list:
    """Score docs by how many query terms appear in the title or body."""
    terms = {term.lower() for term in query_terms if term.strip()}
    scored = []
    for title, body in DOCS:
        haystack = set(WORD.findall(f"{title} {body}".lower()))
        score = len(terms & haystack)
        if score:
            scored.append((score, title))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [title for _, title in scored[:limit]]


# --- Query rewriting ----------------------------------------------------------

def celeris_base_url() -> str:
    """Return the full SDK base URL, accepting legacy endpoint roots too."""
    base = (
        os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or ""
    ).rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


REWRITE_PROMPT = (
    "Rewrite this search query into 3 to 6 lowercase keywords for a keyword "
    "search over product documentation. Expand abbreviations and add close "
    'synonyms. Reply with ONLY a JSON object: {"keywords": ["...", "..."]}\n\n'
    "Query: "
)


def parse_keywords(output: str) -> list | None:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", output.strip())
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    keywords = parsed.get("keywords") if isinstance(parsed, dict) else None
    if not isinstance(keywords, list) or not keywords:
        return None
    return [str(keyword) for keyword in keywords]


def rewrite(client: OpenAI, model: str, query: str) -> tuple:
    """One rewrite call. On a 429, back off once and retry; a per-pause tool
    must degrade politely under throttling rather than crash."""
    started = time.monotonic()
    for attempt in (1, 2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": REWRITE_PROMPT + query}],
                max_tokens=256,  # short query rewrite; general default is 2048
                temperature=0.0,
            )
            break
        except APIStatusError as error:
            if error.status_code == 429 and attempt == 1:
                time.sleep(2.5)
                continue
            return None, (time.monotonic() - started) * 1000
    latency_ms = (time.monotonic() - started) * 1000
    keywords = parse_keywords(response.choices[0].message.content or "")
    return keywords, latency_ms


def run_query(client: OpenAI, model: str, query: str) -> None:
    raw_results = search(WORD.findall(query.lower()))
    keywords, latency_ms = rewrite(client, model, query)
    print(f'\nquery: "{query}"')
    print(f"  raw keyword match:  {raw_results or ['(no results)']}")
    if keywords is None:
        print(f"  rewrite failed ({latency_ms:.0f} ms), keeping raw results")
        return
    # The model may return multi-word keywords; split them for the index.
    terms = [word for keyword in keywords for word in WORD.findall(keyword.lower())]
    print(f"  rewritten in {latency_ms:.0f} ms: {keywords}")
    print(f"  results after rewrite: {search(terms) or ['(no results)']}")


DEMO_QUERIES = [
    "why do I keep getting told to slow down",
    "getting my money back",
    "let a coworker see dashboards but not change anything",
    "hook that tells my server when stuff happens",
    "how long do you keep what I send",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--interactive", action="store_true", help="type queries instead of the demo set")
    args = parser.parse_args()

    if not (os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL")):
        print("Set CELERIS_BASE_URL and CELERIS_API_KEY first.", file=sys.stderr)
        return 2

    client = OpenAI(
        base_url=celeris_base_url(),
        api_key=os.environ.get("CELERIS_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        max_retries=0,
    )
    model = os.environ.get("CELERIS_MODEL", "celeris-1")

    if args.interactive:
        print("Type a query (empty line to quit).")
        while True:
            try:
                query = input("\n> ").strip()
            except EOFError:
                break
            if not query:
                break
            run_query(client, model, query)
        return 0

    for query in DEMO_QUERIES:
        run_query(client, model, query)
        time.sleep(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
