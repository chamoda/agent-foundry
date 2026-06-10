"""Read JSON artifacts that an opencode build pass was asked to write."""

from __future__ import annotations

import json
import os
import re

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
        match = re.search(r"\{.*\}", raw, re.DOTALL)  # tolerate stray fences/prose
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    log(f"Could not parse {path} as JSON.")
    return None
