# Getting started with the Celeris API

Make your first chat completion against the Celeris API, with the two things
every Celeris client must get right:

1. **`max_tokens` normalization.** The wire `max_tokens` value must be a
   multiple of 256 in the range 256–1024. Anything else is rejected, so round
   your requested output budget up to the nearest supported step.
2. **Input budgeting.** Requests share a **4096-token total window** between
   input and output. Reserving `max_tokens` for output leaves
   `4096 - max_tokens` tokens for all input messages combined — budget your
   prompt to fit.

## Run it

```sh
export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
export CELERIS_API_KEY="<your-api-key>"

python3 -m pip install -r requirements.txt
python3 main.py "Explain what a context window is, in two sentences."
```

Expected output looks like:

```text
model: celeris-1
max_tokens: 512 (input budget: 3584 tokens)

A context window is the total amount of text — measured in tokens — that a
model can consider at once, covering both your input and its output. ...
```

## How it works

The API is an OpenAI-compatible chat completions endpoint:

```text
POST {CELERIS_BASE_URL}/v1/chat/completions
Authorization: Bearer {CELERIS_API_KEY}
```

with a JSON body of `model`, `messages`, `max_tokens`, and `temperature`.

The interesting part is the budget math in `main.py`:

```python
TOTAL_TOKEN_LIMIT = 4096
MIN_OUTPUT_TOKENS = 256
MAX_OUTPUT_TOKENS = 1024
OUTPUT_TOKEN_STEP = 256


def normalize_max_tokens(requested: int) -> int:
    """Round up to a supported 256-token step, clamped to [256, 1024]."""
    if requested <= MIN_OUTPUT_TOKENS:
        return MIN_OUTPUT_TOKENS
    if requested >= MAX_OUTPUT_TOKENS:
        return MAX_OUTPUT_TOKENS
    step = OUTPUT_TOKEN_STEP
    return ((requested + step - 1) // step) * step


def input_token_budget(max_tokens: int) -> int:
    """Tokens left for ALL input messages after the output reservation."""
    return TOTAL_TOKEN_LIMIT - normalize_max_tokens(max_tokens)
```

Rounding **up** avoids silently giving yourself less output room than you
asked for. The script estimates its prompt size (~4 bytes per token plus a
small allowance for the chat template) and clips the user message if it would
overflow the input budget, so the request always fits the window.

## Next steps

- Tune `max_tokens` to your use case: summaries usually fit in 256, generation
  tasks may want the full 1024 — at the cost of 768 fewer input tokens.
- For long inputs, clip or summarize *before* sending; the API will not do it
  for you.
