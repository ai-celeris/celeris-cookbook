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
| LangChain (Python) | Verified | `max_tokens` | `langchain-openai` package. |
| LiteLLM | Verified | `max_tokens` | Prefix the model with `openai/`. |
| Instructor | Verified with `Mode.MD_JSON` | `max_tokens` | Tool-calling and `Mode.JSON` modes do not work; see notes. |

## OpenAI SDK (Python)

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

```ts
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: process.env.CELERIS_BASE_URL.replace(/\/+$/, "") + "/v1",
  apiKey: process.env.CELERIS_API_KEY,
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

```ts
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import { generateText } from "ai";

const celeris = createOpenAICompatible({
  name: "celeris",
  baseURL: process.env.CELERIS_BASE_URL.replace(/\/+$/, "") + "/v1",
  apiKey: process.env.CELERIS_API_KEY,
});
const { text } = await generateText({
  model: celeris("celeris-1"),
  prompt: "Say hello in five words.",
  maxOutputTokens: 256,
});
```

## LangChain (Python)

```python
import os
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="celeris-1",
    base_url=os.environ["CELERIS_BASE_URL"].rstrip("/") + "/v1",
    api_key=os.environ["CELERIS_API_KEY"],
    max_tokens=256,
)
print(llm.invoke("Say hello in five words.").content)
```

## LiteLLM

Prefix the model name with `openai/` so LiteLLM uses its OpenAI-compatible
path.

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
with a server error. Use `Mode.MD_JSON`, which is prompt-based and works:

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
