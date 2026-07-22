# Framework compatibility

Celeris serves an OpenAI-compatible chat completions API, so most tooling
that speaks to OpenAI works by pointing it at your Celeris base URL. Two
rules apply everywhere:

1. The SDK-level base URL is your endpoint root **plus `/v1`**.
2. `max_tokens` (whatever the framework calls it) must be a multiple of 256
   between 256 and 1024. See the [latency guide](latency.md) for the full
   budgeting rules.

Every snippet below was run against a live workspace on 2026-07-22.

| Framework | Status | max_tokens parameter | Notes |
| --- | --- | --- | --- |
| OpenAI SDK (Python) | Verified | `max_tokens` | Used across this cookbook. |
| OpenAI SDK (JS/TS) | Verified | `max_tokens` | Used across this cookbook. |
| Vercel AI SDK | Verified | `maxOutputTokens` | Use the `@ai-sdk/openai-compatible` provider. |
| LangChain (Python) | Verified | `extra_body.max_tokens` | Current `langchain-openai` otherwise renames the wire field. |
| LiteLLM | Verified | `max_tokens` | Prefix the model with `openai/`. |
| Instructor | Verified with `Mode.MD_JSON` | `max_tokens` | Tool-calling and `Mode.JSON` modes do not work; see notes. |

## OpenAI SDK (Python)

Install the client with `pip install openai`.

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.environ["CELERIS_BASE_URL"].rstrip("/") + "/v1",
    api_key=os.environ["CELERIS_API_KEY"],
)
reply = client.chat.completions.create(
    model="celeris-1",
    messages=[{"role": "user", "content": "Say hello in five words."}],
    max_tokens=256,
)
print(reply.choices[0].message.content)
```

## OpenAI SDK (JS/TS)

Install the client with `npm install openai`.

```ts
import OpenAI from "openai";

const baseURL = process.env.CELERIS_BASE_URL;
const apiKey = process.env.CELERIS_API_KEY;
if (!baseURL || !apiKey) {
  throw new Error("Set CELERIS_BASE_URL and CELERIS_API_KEY first.");
}

const client = new OpenAI({
  baseURL: baseURL.replace(/\/+$/, "") + "/v1",
  apiKey,
});
const reply = await client.chat.completions.create({
  model: "celeris-1",
  messages: [{ role: "user", content: "Say hello in five words." }],
  max_tokens: 256,
});
console.log(reply.choices[0].message.content);
```

## Vercel AI SDK

Use the `@ai-sdk/openai-compatible` provider. Note the parameter name:
`maxOutputTokens`, same 256-step rule.
Install both packages with `npm install ai @ai-sdk/openai-compatible`.

```ts
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import { generateText } from "ai";

const baseURL = process.env.CELERIS_BASE_URL;
const apiKey = process.env.CELERIS_API_KEY;
if (!baseURL || !apiKey) {
  throw new Error("Set CELERIS_BASE_URL and CELERIS_API_KEY first.");
}

const celeris = createOpenAICompatible({
  name: "celeris",
  baseURL: baseURL.replace(/\/+$/, "") + "/v1",
  apiKey,
});
const { text } = await generateText({
  model: celeris("celeris-1"),
  prompt: "Say hello in five words.",
  maxOutputTokens: 256,
});
```

## LangChain (Python)

Install the integration with `pip install langchain-openai`.
Current versions map the `max_tokens` constructor argument to
`max_completion_tokens`, which the Celeris endpoint does not use. Put the
required wire field in `extra_body` instead:

```python
import os
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="celeris-1",
    base_url=os.environ["CELERIS_BASE_URL"].rstrip("/") + "/v1",
    api_key=os.environ["CELERIS_API_KEY"],
    extra_body={"max_tokens": 256},
)
print(llm.invoke("Say hello in five words.").content)
```

## LiteLLM

Prefix the model name with `openai/` so LiteLLM uses its OpenAI-compatible
path. Install it with `pip install litellm`.

```python
import os
import litellm

response = litellm.completion(
    model="openai/celeris-1",
    api_base=os.environ["CELERIS_BASE_URL"].rstrip("/") + "/v1",
    api_key=os.environ["CELERIS_API_KEY"],
    messages=[{"role": "user", "content": "Say hello in five words."}],
    max_tokens=256,
)
print(response.choices[0].message.content)
```

## Instructor

Instructor's default mode uses native tool calling, which the endpoint does
not support, and `Mode.JSON` sends `response_format`, which currently fails
with a server error. Install the integration with
`pip install instructor openai pydantic`, then use `Mode.MD_JSON`, which is
prompt-based and works:

```python
import os
import instructor
from openai import OpenAI
from pydantic import BaseModel

class City(BaseModel):
    name: str
    country: str

client = instructor.from_openai(
    OpenAI(
        base_url=os.environ["CELERIS_BASE_URL"].rstrip("/") + "/v1",
        api_key=os.environ["CELERIS_API_KEY"],
    ),
    mode=instructor.Mode.MD_JSON,
)
city = client.chat.completions.create(
    model="celeris-1",
    messages=[{"role": "user", "content": "Largest city in Australia?"}],
    response_model=City,
    max_tokens=256,
)
# City(name='Sydney', country='Australia')
```

## Known limits across all frameworks

- **No native tool calling.** The `tools` parameter is rejected by the
  serving configuration. Use prompt-driven JSON tool loops instead (see the
  [alert triage example](../examples/alert-triage-agent)).
- **No `response_format`.** Requests with `response_format` currently fail.
  Ask for JSON in the prompt and validate client-side (every extraction
  example in this cookbook does this).
- **Streaming arrives as one burst.** Framework streaming helpers work, but
  all chunks land together; see the [latency guide](latency.md).
