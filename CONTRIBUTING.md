# Contributing to the Celeris Cookbook

## What makes a good example

- **Self-contained**: one directory under `examples/`, runnable with only
  `CELERIS_BASE_URL` and `CELERIS_API_KEY` set.
- **Small**: a focused script (or two) plus a README that explains what it
  demonstrates and shows the expected output.
- **Budget-aware**: respect the 4096-token total window. `max_tokens` must be a
  multiple of 256 in 256–1024; the rest of the window is your input budget.
  Reuse the normalization helper from `examples/getting-started/main.py`.
- **No secrets**: never commit API keys, traces, or `.env` files.

## Adding an example

1. Create `examples/<kebab-case-name>/` with:
   - `README.md` — title as the first `# heading`, then what it does, how to
     run it, and sample output. This file becomes the website page.
   - Runnable code (`main.py` or similar) and a `requirements.txt` if it needs
     third-party packages.
2. Register it in `registry.yaml`:

   ```yaml
   - title: Human-readable title
     path: examples/<name>/README.md
     slug: <name>
     description: One-sentence description shown on the index page.
     date: YYYY-MM-DD
     authors:
       - your-github-username
     tags:
       - getting-started
   ```

3. Optionally add yourself to `authors.yaml` to customize your display name,
   website, and avatar.
4. Run the checks locally:

   ```sh
   python3 -m pip install -r site/requirements.txt
   python3 scripts/validate.py
   python3 site/build.py
   ```

5. Open a pull request. CI runs the same validation and site build.

## Registry rules

- `path` must exist in the repository.
- `slug` must be unique and URL-safe (`a-z0-9-`).
- `tags` are free-form but reuse existing tags where possible; the site's
  filter list is derived from them.
