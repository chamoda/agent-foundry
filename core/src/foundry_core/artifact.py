"""Read JSON artifacts that an opencode build pass was asked to write."""

from __future__ import annotations

import json
import os

from foundry_core.shell import log


def read_json_artifact(path: str) -> dict | None:
    """Read and delete a JSON artifact, tolerating stray prose/fences.

    Returns ``None`` (after logging) when the file is missing or unparsable.
    """
    if not os.path.isfile(path):
        log(f"opencode did not write {path}.")
        return None
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    os.remove(path)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        while start >= 0:
            depth = 0
            for i, c in enumerate(raw[start:], start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw[start : i + 1])
                        except json.JSONDecodeError:
                            break
            start = raw.find("{", start + 1)
    log(f"Could not parse {path} as JSON.")
    return None
