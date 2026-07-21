#!/usr/bin/env python3
"""Validate registry.yaml and authors.yaml.

Checks (beyond the JSON schemas): registered paths exist, slugs are unique,
and authors.yaml keys are well-formed. Run in CI on every PR and locally via:

    python3 scripts/validate.py
"""

import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent


def fail(errors):
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    print(f"\n{len(errors)} validation error(s)", file=sys.stderr)
    return 1


def main():
    errors = []

    registry = yaml.safe_load((ROOT / "registry.yaml").read_text()) or []
    authors = yaml.safe_load((ROOT / "authors.yaml").read_text()) or {}

    # Dates load as datetime.date via PyYAML; stringify for schema validation.
    normalized = [
        {**entry, "date": str(entry.get("date", ""))} for entry in registry
    ]

    registry_schema = json.loads((ROOT / ".github/registry_schema.json").read_text())
    authors_schema = json.loads((ROOT / ".github/authors_schema.json").read_text())

    for i, entry in enumerate(normalized):
        for error in jsonschema.Draft7Validator(registry_schema["items"]).iter_errors(entry):
            errors.append(f"registry.yaml entry {i}: {error.message}")

    for error in jsonschema.Draft7Validator(authors_schema).iter_errors(authors):
        errors.append(f"authors.yaml: {error.message}")

    slugs = [entry.get("slug") for entry in registry]
    for slug in {s for s in slugs if slugs.count(s) > 1}:
        errors.append(f"duplicate slug: {slug}")

    for entry in registry:
        path = entry.get("path", "")
        if path and not (ROOT / path).is_file():
            errors.append(f"registry path does not exist: {path}")

    if errors:
        return fail(errors)

    print(f"registry.yaml OK ({len(registry)} example(s)), authors.yaml OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
