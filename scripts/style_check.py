#!/usr/bin/env python3
"""Enforce the cookbook content rules on user-visible text.

Rules:
- No em-dashes or en-dashes anywhere. Use commas, periods, or parentheses.
- No internal product, system, or company names.

Scope: examples/, guides/, demos/, registry.yaml, authors.yaml,
README.md, CONTRIBUTING.md. Dependency directories, build output, and lockfiles
are skipped.

Run in CI on every PR and locally via:

    python3 scripts/style_check.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCOPE = [
    "examples",
    "guides",
    "demos",
    "llms.txt",
    "registry.yaml",
    "authors.yaml",
    "README.md",
    "CONTRIBUTING.md",
]

SKIP_DIRS = {"node_modules", ".venv", "__pycache__", ".next", "dist", "build"}
SKIP_FILES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}

BANNED_CHARS = {
    "—": "em-dash (rewrite with a comma, period, or parentheses)",
    "–": "en-dash (use a plain hyphen or rewrite)",
}

# Case-insensitive. Internal names must never appear in cookbook content.
BANNED_TERMS = [
    "marqo",
    "celeris-apps",
    "diffusion-llm-service",
]


def files_in_scope():
    for entry in SCOPE:
        path = ROOT / entry
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if not child.is_file():
                    continue
                if child.name in SKIP_FILES:
                    continue
                if any(part in SKIP_DIRS for part in child.parts):
                    continue
                yield child


def check_file(path: Path) -> list:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    problems = []
    rel = path.relative_to(ROOT)
    for number, line in enumerate(text.splitlines(), start=1):
        for char, reason in BANNED_CHARS.items():
            if char in line:
                problems.append(f"{rel}:{number}: {reason}")
        lowered = line.lower()
        for term in BANNED_TERMS:
            if term in lowered:
                problems.append(f"{rel}:{number}: forbidden term {term!r}")
    return problems


def main() -> int:
    problems = []
    count = 0
    for path in files_in_scope():
        count += 1
        problems.extend(check_file(path))
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        print(f"\n{len(problems)} style problem(s)", file=sys.stderr)
        return 1
    print(f"style OK ({count} files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
