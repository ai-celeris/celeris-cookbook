# Task fit: bring your own prompts

"Is a fast, moderate-intelligence model enough for my task?" is the right
question, and nobody should answer it with vibes. This tool answers it with
your own prompts: drop a JSONL file of tasks with objective checkers, run
them repeatedly against Celeris-1, and read a per-task verdict. It is built
to tell the truth in both directions; a poor-fit answer saves you a bad
launch, a strong-fit answer saves you a larger bill.

## Run it

```sh docs-e2e=skip
cd examples/task-fit
pip install -r requirements.txt

export CELERIS_BASE_URL="https://inference.celeris.ai/celeris-1/v1"
export CELERIS_API_KEY="<your-api-key>"

python3 main.py tasks/good-fit-classification.jsonl
python3 main.py your-tasks.jsonl --repetitions 5
```

Task file format (one JSON object per line):

```json docs-e2e=skip
{"id": "route-1", "prompt": "...", "checker": "label_set",
 "labels": ["billing", "technical"], "expected": "billing",
 "max_tokens": 256}
```

Checkers: `exact`, `contains`, `json_keys` (with `expected_keys`),
`label_set` (with `labels`), or `none` (latency and reliability only). The
optional `max_tokens` field defaults to 2048; the shipped tasks set it to 256
because they all request a short sentence, label, or compact JSON object. The
measurement loop, checkers, and percentile math are imported from the
[benchmark harness](../benchmark), not duplicated.

## What it found on the two shipped sets (live, 2026-07-22)

**Classification and extraction set** (the kind of task this model is for):

| task | checker | accuracy | p50 ms | empties | verdict |
| --- | --- | --- | --- | --- | --- |
| route-billing | label_set | 67% | 723 | 1 | partial fit |
| route-technical | label_set | 100% | 724 | 0 | strong fit |
| sentiment-positive | label_set | 100% | 717 | 0 | strong fit |
| sentiment-neutral | label_set | 100% | 713 | 0 | strong fit |
| extract-order | json_keys | 100% | 722 | 0 | strong fit |
| extract-meeting | json_keys | 100% | 732 | 0 | strong fit |
| fact-capital | contains | 100% | 689 | 0 | strong fit |
| arithmetic-simple | contains | 100% | 693 | 0 | strong fit |

Seven of eight strong. The one partial was a single empty reply in three
repetitions, which is exactly the kind of reliability detail this tool
exists to surface (and the reason production callers keep a retry).

**Hard reasoning set** (built to probe the model's limits):

| task | checker | accuracy | p50 ms | empties | verdict |
| --- | --- | --- | --- | --- | --- |
| math-multistep | contains | 33% | 750 | 0 | poor fit |
| letters-count | contains | 100% | 704 | 0 | strong fit |
| letters-reverse | contains | 0% | 695 | 0 | poor fit |
| logic-order | contains | 100% | 709 | 0 | strong fit |
| math-remainder | contains | 100% | 716 | 0 | strong fit |
| calendar-reasoning | contains | 100% | 675 | 0 | strong fit |

The tool discriminates per task rather than damning a category: simple
logic, a power-mod question, and calendar arithmetic all passed, while
multi-step word-problem arithmetic (33%) and character reversal (0%) are
genuinely wrong for this model. The summary says so and points at the
[cascade guide](../../guides/cascade.md): keep the fits on the fast path,
send the misses to a slower, more intelligent model.

## Reading the verdicts

- **strong fit**: at least 90 percent accuracy and no reliability flags.
  Run your real traffic next.
- **partial fit**: 60 to 90 percent. Usually prompt phrasing, a missing
  repair step, or an occasional empty reply. Cheap to fix; measure again.
- **poor fit**: under 60 percent. Believe it. Use a slower, more intelligent
  model for this task, or restructure the task into checkable smaller steps.

Latency comes free with every run (p50 and p95 across all repetitions), so
the same report answers both halves of the decision: is it right enough,
and is it fast enough to change how your product feels.
