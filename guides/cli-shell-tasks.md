# Shell tasks with the celeris CLI

The shell is where latency pays off most. A command that answers in a few
hundred milliseconds feels like part of the pipeline; a command that takes
five seconds breaks your flow, and a per-line loop over a thousand lines
becomes lunch. celeris-1 returns small completions fast enough that semantic
operations (classify, extract, rewrite, summarize) can sit inside ordinary
shell one-liners next to `grep` and `jq`.

`celeris` is the official CLI. It reads stdin, writes plain text to stdout,
streams by default where it helps, and keeps diagnostics on stderr, so it
composes with pipes the way you expect.

## Setup

```sh docs-e2e=skip
brew install ai-celeris/tools/celeris

export CELERIS_API_KEY="<your-api-key>"
```

The CLI uses the global production endpoint by default. Set
`CELERIS_BASE_URL` only to override it; unlike the SDK examples, the CLI
expects that override without `/v1`.

The quick command is `celeris q`: arguments form the instruction, piped
stdin is appended as context, and the answer streams back as plain text.

```sh docs-e2e=skip
celeris q "Reply with one word: the capital of France."
```

```text docs-e2e=skip
Paris
```

Every recipe below also works with the full-fidelity form,
`celeris chat:completions create --format json`, when you want the whole
response object. `q` defaults to `max_tokens=256`; see the
[latency guide](latency.md) before increasing it.

## Commit messages from the staged diff

```sh docs-e2e=skip
git diff --staged | celeris q "Write a one-line conventional commit message for this diff. Reply with only the message."
```

Wrap it in a function and it becomes a habit:

```sh docs-e2e=skip
gcm() {
  git commit -m "$(git diff --staged | celeris q 'Write a one-line conventional commit message for this diff. Reply with only the message.')" -e
}
```

The `-e` flag opens the proposed message in your editor, so you approve
every commit rather than trusting the model blindly.

## Log triage

Summarize the interesting part of a noisy log:

```sh docs-e2e=skip
tail -200 app.log | celeris q "List the distinct errors in this log, one per line, most frequent first. Ignore INFO lines."
```

Classify records one at a time when you need a per-line verdict. At
sub-second latency a serial loop over a few hundred lines is a coffee sip,
not a batch job:

```sh docs-e2e=skip
grep ERROR app.log | sort -u | while IFS= read -r line; do
  verdict=$(printf '%s' "$line" | celeris q "Is this error caused by user input, our code, or a dependency? Reply with exactly one word: user, code, or dependency.")
  printf '%s\t%s\n' "$verdict" "$line"
done | sort
```

## Semantic filtering

`grep` matches strings; sometimes you need to match meaning. Keep the answer
contract tiny (one word) and filter on it:

```sh docs-e2e=skip
cat feedback.txt | while IFS= read -r item; do
  ans=$(printf '%s' "$item" | celeris q "Is this feedback about pricing or billing? Reply yes or no only.")
  [ "$ans" = "yes" ] && printf '%s\n' "$item"
done
```

## Extraction into jq

Ask for JSON only and pipe straight into `jq`. Temperature 0 and a seed keep
reruns stable:

```sh docs-e2e=skip
cat order-email.txt | celeris q --temperature 0 --seed 7 \
  "Extract items, quantities, and the delivery date from this email as JSON with keys items (array of {name, qty}) and delivery_date. Reply with JSON only." \
  | jq '.items[].name'
```

If the model ever wraps the JSON in prose, tighten the prompt ("Reply with
JSON only, no code fences") or switch to
`celeris chat:completions create --format json` and extract
`.choices[0].message.content` with `jq -r` before parsing.

## Quick transforms

Anything you would paste into a browser chat fits better in the pipe you are
already standing in:

```sh docs-e2e=skip
# Explain a cron expression before you deploy it.
echo "17 3 * * 1-5" | celeris q "Explain this cron schedule in one sentence."

# Turn a curl command into equivalent Python.
pbpaste | celeris q "Rewrite this curl command as Python requests code. Reply with code only."

# Bulk-rename messy filenames without writing the sed by hand.
ls *.MOV | celeris q "Write mv commands that rename these files to lowercase kebab-case, keeping the extension. Reply with the commands only."
```

## Scripting patterns

A few conventions make the CLI dependable inside scripts:

- **Pin the sampling.** `--temperature 0 --seed 7` makes reruns repeatable
  in the common case, which matters once output feeds `jq` or a test.
- **Demand a format.** End prompts with "Reply with only X". Small answer
  contracts keep fast responses fast, and they make parsing
  trivial.
- **Check exit codes.** `celeris` exits 0 on success, 1 when the request or
  API fails, and 2 on a bad invocation, and errors go to stderr, so
  `set -e` pipelines and `if celeris q ...; then` behave correctly.
- **Budget tokens.** Loops multiply cost and latency. `q` defaults to
  `--max-tokens 256`, the smallest step the API accepts; keep it there
  unless the answer genuinely needs more room.
- **Mind rate limits.** Workspace tiers cap sustained request rate. For big
  loops add a small `sleep` between calls, and see the
  [latency guide](latency.md) before parallelizing with `xargs -P`.
