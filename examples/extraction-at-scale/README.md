# Extraction at scale

Extracting structured fields from a large document set with a slow model is
an overnight batch job: at 5 seconds per document, 10,000 documents take 14
hours. At a few hundred milliseconds per document you can reprocess the same
set in under an hour on one worker, and in minutes with modest concurrency.
The job stops being a pipeline you schedule and becomes a function you call.

This example extracts four fields (vendor, invoice number, total, due date)
from a synthetic corpus of messy invoice snippets, measures throughput at
several concurrency levels, and scores accuracy against the known ground
truth.

## Run it

```sh docs-e2e=skip
cd examples/extraction-at-scale
pip install -r requirements.txt

export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
export CELERIS_API_KEY="<your-api-key>"

python3 main.py                      # 40 docs at each of concurrency 1, 4, 8
python3 main.py --docs 20 --levels 1 4
```

Mind your workspace rate limit. The harness backs off politely on 429s and
counts them, but higher concurrency mostly converts into throttling once you
hit the limit.

## Measured results

A real run against a live workspace (2026-07-22), 40 documents per level:

| concurrency | docs/min | p50 ms/doc | mean ms/doc | throttles | repairs | failures | field accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 182 | 279 | 329 | 0 | 4 | 0 | 99% |
| 4 | 229 | 399 | 907 | 8 | 3 | 0 | 99% |
| 8 | 289 | 814 | 1524 | 16 | 5 | 0 | 99% |

Three things worth reading off that table:

- **One worker is already fast.** 182 documents per minute sequentially,
  because each extraction costs about 280 ms. A 10,000-document set is under
  an hour on a single asyncio task.
- **Concurrency helps until the rate limit.** Going from 1 to 8 workers
  added 59 percent throughput and 16 throttles. Your sustained ceiling is
  the workspace rate limit, not the model. Ask for a higher limit before
  adding workers past it.
- **The cheap-repair pattern absorbs formatting misses.** About one in ten
  replies was not valid JSON on the first try. One follow-up call ("fix
  this into valid JSON") repaired every one of them: zero failed documents
  and 99 percent field accuracy across all 480 field checks.

## How it works

- **asyncio + a semaphore.** `AsyncOpenAI` with a semaphore per concurrency
  level. 429s sleep and retry up to twice, and are reported, not hidden.
- **Small canvas per document.** Each snippet plus the instruction fits far
  inside the input budget, and this compact JSON task uses `max_tokens=256` (see the
  [latency guide](../../guides/latency.md) for the budgeting rules).
- **Repair, then give up.** Unparseable output gets exactly one repair call
  with the broken text. At a few hundred milliseconds per attempt, a repair
  costs less than re-queuing the document, and failure stays observable.
- **Ground truth built in.** The corpus is generated with a fixed seed, so
  accuracy is a real measurement, not an eyeball.
