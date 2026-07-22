# The cascade: fast model first, big model when needed

A fast small model answers most requests well and every request quickly. A
large model answers hard requests better and every request slowly. You do
not have to choose once for your whole product. Put celeris-1 in the hot
path, return its answer immediately, and involve a larger model only for
the cases that need it, off the critical path where possible.

## The shape

```text
            request
               |
               v
     +-------------------+   answer in ~300 ms
     |   celeris-1       | ----------------------> user sees a result now
     |   (hot path)      |
     +-------------------+
               |
               |  confidence low, task hard,
               |  or refinement worthwhile
               v
     +-------------------+   seconds, asynchronous
     |   larger model    | ----------------------> refine, escalate, or
     |   (slow path)     |                         audit in the background
     +-------------------+
```

Three common variants:

- **Answer then refine.** Ship the fast answer immediately; replace or
  annotate it when the slow refinement lands. Users get instant feedback
  and better quality a few seconds later.
- **Answer or escalate.** The fast model handles the request unless its own
  output signals low confidence (or fails validation); only then does the
  slow path run, and the user waits only on the hard cases.
- **Gate and audit.** The fast model screens every request in the hot path
  (see the guardrails example); a larger model audits a sample or the
  flagged cases asynchronously.

## A runnable sketch

The fast call blocks; the slow call runs in the background and reports
later. This complete demo uses a delayed local function for the slow model,
replace `call_large_model` with the provider you use in production:

```python
import asyncio
import os

from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url=os.environ["CELERIS_BASE_URL"].rstrip("/") + "/v1",
    api_key=os.environ["CELERIS_API_KEY"],
)


async def fast_answer(question: str) -> str:
    response = await client.chat.completions.create(
        model="celeris-1",
        messages=[{"role": "user", "content": question}],
        max_tokens=256,  # multiple of 256 in [256, 1024]
        temperature=0.2,
    )
    return response.choices[0].message.content or ""


async def call_large_model(question: str, draft: str) -> str:
    """Stand-in for your slower model provider."""
    await asyncio.sleep(1)
    return f"Refined answer for {question!r}: {draft}"


async def publish_update(improved: str) -> None:
    """Replace this with a WebSocket, event, database write, or callback."""
    print(f"refined: {improved}")


async def refine_later(question: str, draft: str) -> None:
    improved = await call_large_model(question, draft)
    await publish_update(improved)


background_tasks: set[asyncio.Task[None]] = set()


async def handle(question: str) -> str:
    draft = await fast_answer(question)  # user waits on the fast path only
    task = asyncio.create_task(refine_later(question, draft))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return draft


async def main() -> None:
    print(f"initial: {await handle('How should I handle a failed payment?')}")
    await asyncio.gather(*background_tasks)


if __name__ == "__main__":
    asyncio.run(main())
```

The task set keeps strong references until each refinement finishes. In a
serverless request handler, enqueue the refinement in a durable job system
instead, because the runtime may stop after returning the fast answer.

## When to use which model

Send to the fast path when the task is one of the bread-and-butter shapes:
classify, route, extract, validate, summarize briefly, fill tool arguments,
draft a short reply. These are most calls in most products, and they are
where waiting seconds hurts most.

Send to the slow path when the task needs long-context reasoning, novel
code, or judgment you would not delegate to a junior teammate on their
first day. Trigger it from the fast path rather than in front of it: on low
confidence, on failed validation, on explicit user request ("improve this
answer"), or on a background schedule.

Decide with data, not vibes: run the [benchmark harness](../examples/benchmark)
on your own tasks, look at the correctness column, and move only the task
types that actually miss.
