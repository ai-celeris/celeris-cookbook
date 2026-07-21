#!/usr/bin/env python3
"""Getting started with the Celeris API.

Makes one chat completion, demonstrating the two rules every Celeris client
must follow:

- max_tokens must be a multiple of 256 in [256, 1024].
- Input and output share a 4096-token total window: reserving max_tokens for
  output leaves 4096 - max_tokens tokens for all input messages combined.

Usage:
    export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
    export CELERIS_API_KEY="<your-api-key>"
    python3 main.py "Explain what a context window is, in two sentences."
"""

import os
import sys

import requests

# --- Celeris token window constants -----------------------------------------

TOTAL_TOKEN_LIMIT = 4096
MIN_OUTPUT_TOKENS = 256
MAX_OUTPUT_TOKENS = 1024
OUTPUT_TOKEN_STEP = 256

# The service does not expose its tokenizer; ~4 bytes/token is a serviceable
# estimate, with a small allowance for the provider's chat template.
ESTIMATED_BYTES_PER_TOKEN = 4
CHAT_BASE_TOKENS = 8
CHAT_MESSAGE_TOKENS = 4


def normalize_max_tokens(requested: int) -> int:
    """Round up to a supported 256-token step, clamped to [256, 1024].

    Rounding up avoids silently giving the caller less output room than
    requested.
    """
    if requested <= MIN_OUTPUT_TOKENS:
        return MIN_OUTPUT_TOKENS
    if requested >= MAX_OUTPUT_TOKENS:
        return MAX_OUTPUT_TOKENS
    step = OUTPUT_TOKEN_STEP
    return ((requested + step - 1) // step) * step


def input_token_budget(max_tokens: int) -> int:
    """Tokens left for ALL input messages after the output reservation."""
    return TOTAL_TOKEN_LIMIT - normalize_max_tokens(max_tokens)


def estimate_input_tokens(*contents: str) -> int:
    """Estimate the complete chat input, including the chat template."""
    total_bytes = sum(len(content.encode("utf-8")) for content in contents)
    content_tokens = -(-total_bytes // ESTIMATED_BYTES_PER_TOKEN)  # ceil div
    return CHAT_BASE_TOKENS + len(contents) * CHAT_MESSAGE_TOKENS + content_tokens


def fit_input(system: str, user: str, max_tokens: int) -> str:
    """Clip the user message so the full request fits the 4096-token window."""
    overhead = CHAT_BASE_TOKENS + 2 * CHAT_MESSAGE_TOKENS
    system_tokens = -(-len(system.encode("utf-8")) // ESTIMATED_BYTES_PER_TOKEN)
    user_budget_tokens = input_token_budget(max_tokens) - overhead - system_tokens
    max_user_bytes = max(user_budget_tokens, 0) * ESTIMATED_BYTES_PER_TOKEN
    encoded = user.encode("utf-8")
    if len(encoded) <= max_user_bytes:
        return user
    return encoded[:max_user_bytes].decode("utf-8", errors="ignore")


# --- The request -------------------------------------------------------------


def main() -> int:
    base_url = os.environ.get("CELERIS_BASE_URL", "").strip()
    api_key = os.environ.get("CELERIS_API_KEY", "").strip()
    if not base_url or not api_key:
        print("Set CELERIS_BASE_URL and CELERIS_API_KEY first.", file=sys.stderr)
        return 2

    model = os.environ.get("CELERIS_MODEL", "celeris-1")
    system = "You are a concise assistant. Answer directly."
    user = sys.argv[1] if len(sys.argv) > 1 else (
        "Explain what a context window is, in two sentences."
    )

    # Reserve output room, then budget the input around it.
    max_tokens = normalize_max_tokens(512)
    user = fit_input(system, user, max_tokens)
    print(f"model: {model}")
    print(f"max_tokens: {max_tokens} (input budget: {input_token_budget(max_tokens)} tokens)")
    print()

    response = requests.post(
        f"{base_url}/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        },
        timeout=60,
    )
    response.raise_for_status()
    body = response.json()

    print(body["choices"][0]["message"]["content"].strip())
    usage = body.get("usage", {})
    if usage:
        print()
        print(
            f"[usage: {usage.get('prompt_tokens', '?')} prompt + "
            f"{usage.get('completion_tokens', '?')} completion tokens]"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
