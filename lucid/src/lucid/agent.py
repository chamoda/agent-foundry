"""Drive opencode to research a newly opened issue and score its priority.

Entry point for ``python -m lucid`` / the ``lucid`` console script.

Triggered when an issue is opened (or manually via ``workflow_dispatch``).
Each run:

1. Reads the issue (title, body, discussion).
2. Reads ``VISION.md`` at the consuming project's root, if present, to judge
   how well the issue aligns with the maintainer's long-term direction.
3. Researches the codebase in depth: which files/subsystems the issue touches,
   how hard it is to implement, and how much value it delivers.
4. Scores the issue with **ICE** (Impact × Confidence × Ease, the default) or
   **RICE** ((Reach × Impact × Confidence) ÷ Effort), normalizes the result to
   an integer **1–10**, posts a compact comment with the calculation, and adds
   an ``ice-<n>`` / ``rice-<n>`` label to the issue.

opencode runs in two phases: a read-only ``plan`` agent researches, then the
``build`` agent writes a structured score artifact. This script validates the
factors and computes the final score itself, so the arithmetic in the comment
is always consistent. Normalization to 1–10: ICE takes the geometric mean of
the three 1–10 factors; RICE (unbounded) is mapped with ``log2(raw + 1)`` and
clamped, so each +1 means roughly double the value per unit of effort.

Required env: ``GITHUB_REPOSITORY``, ``GITHUB_TOKEN``, and the issue number
via ``ISSUE_NUMBER`` (set from the event) or ``DISPATCH_ISSUE``.
Optional env: ``OPENCODE_MODEL``, ``OPENCODE_VARIANT`` (default ``high``),
``OPENCODE_PLAN`` (default ``true``), ``SCORE_METHOD`` (``ice``/``rice``,
default ``ice``), ``VISION_FILE`` (default ``VISION.md``).
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass

from github import Github
from github.Issue import Issue

from foundry_core import Opencode, RunResult, ensure_label, env, log, write_summary
from foundry_core.artifact import read_json_artifact
from lucid import __version__

# opencode writes the score here (in the consumer's checked-out repo).
ARTIFACT = "lucid_score.json"

PLAN_INSTRUCTIONS = (
    "## First: research only\n"
    "Explore the codebase in depth to ground every scoring factor in real "
    "findings: which files and subsystems the issue touches, how complex the "
    "change is, and how much value it delivers. Do NOT write any files yet."
)
BUILD_LEAD_IN = "Now write the score you decided on."

ICE_RUBRIC = "\n".join(
    [
        "## Scoring method: ICE",
        "Score three factors, each a number from 1 (lowest) to 10 (highest):",
        '- "impact": how much value solving this issue delivers — user value, '
        "project health, and alignment with the maintainer vision.",
        '- "confidence": how certain you are about your impact and ease '
        "estimates, given what your research actually confirmed.",
        '- "ease": how easy the change is to implement (10 = trivial, 1 = a '
        "huge, risky effort).",
    ]
)

RICE_RUBRIC = "\n".join(
    [
        "## Scoring method: RICE",
        "Score four factors:",
        '- "reach": how many users/contributors/events this affects per '
        "quarter — a number, estimated from the project's nature and audience.",
        '- "impact": effect per person reached: 3 = massive, 2 = high, '
        "1 = medium, 0.5 = low, 0.25 = minimal.",
        '- "confidence": how sure you are of the estimates, from 0 to 1 '
        "(1.0 = high, 0.8 = medium, 0.5 = low).",
        '- "effort": estimated person-months of work, greater than 0 '
        "(fractional is fine).",
    ]
)


@dataclass(frozen=True)
class Settings:
    repo_name: str
    token: str
    issue_number: int
    method: str
    vision_file: str

    @classmethod
    def from_env(cls) -> Settings:
        method = env("SCORE_METHOD", "ice").strip().lower()
        if method not in ("ice", "rice"):
            sys.exit(f"SCORE_METHOD must be 'ice' or 'rice', got {method!r}")
        return cls(
            repo_name=env("GITHUB_REPOSITORY", required=True),
            token=env("GITHUB_TOKEN", required=True),
            issue_number=int(
                env("DISPATCH_ISSUE") or env("ISSUE_NUMBER", required=True)
            ),
            method=method,
            vision_file=env("VISION_FILE", "VISION.md"),
        )


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #


def vision_section(settings: Settings) -> str:
    path = os.path.join(os.getcwd(), settings.vision_file)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return f"## Maintainer vision — {settings.vision_file}\n{fh.read()}"
    return (
        f"## Maintainer vision — {settings.vision_file}\n"
        f"{settings.vision_file} is not present in this repository; judge "
        "impact from the code and the project's apparent goals."
    )


def build_prompt(issue: Issue, settings: Settings) -> str:
    rubric = ICE_RUBRIC if settings.method == "ice" else RICE_RUBRIC
    return "\n".join(
        [
            f"You are a product-minded engineer triaging issues for the repository {settings.repo_name}.",
            "Your job is to research the GitHub issue below in depth and score how it should be prioritized.",
            "",
            f"# Issue #{issue.number}: {issue.title}",
            issue.body or "(no description)",
            "",
            "## Discussion on the issue",
            *[f"- {c.user.login}: {c.body}" for c in issue.get_comments()],
            "",
            vision_section(settings),
            "",
            rubric,
            "",
            "## Research",
            "Explore the codebase thoroughly: find the files and subsystems this "
            "issue touches, judge implementation complexity and blast radius, and "
            "weigh the value it delivers (including alignment with the maintainer "
            "vision above). Ground every factor in real findings from THIS "
            "project, not generic heuristics.",
        ]
    )


def build_instructions(method: str) -> str:
    if method == "ice":
        keys = [
            '  - "impact", "confidence", "ease": numbers from 1 to 10',
            '  - "rationale": object with keys "impact", "confidence", "ease" — '
            "1–3 sentences each, citing what you found",
        ]
    else:
        keys = [
            '  - "reach": estimated number affected per quarter',
            '  - "reach_unit": short label for the reach unit (e.g. "active users/quarter")',
            '  - "impact": 3, 2, 1, 0.5 or 0.25',
            '  - "confidence": 0 to 1',
            '  - "effort": estimated person-months, greater than 0',
            '  - "rationale": object with keys "reach", "impact", "confidence", '
            '"effort" — 1–3 sentences each, citing what you found',
        ]
    return "\n".join(
        [
            f"Write your score to ./{ARTIFACT} in the repository root as valid "
            "JSON ONLY (no surrounding prose, no markdown fences), with keys:",
            *keys,
            '  - "summary": a 1–2 sentence overall assessment, including how '
            "the issue aligns with the maintainer vision",
            "Do NOT comment on the issue yourself and do NOT touch git.",
        ]
    )


# --------------------------------------------------------------------------- #
# Validation + rendering
# --------------------------------------------------------------------------- #


def fmt(value: float) -> str:
    return f"{value:g}"


def number(data: dict, key: str, lo: float, hi: float) -> float | None:
    try:
        value = float(data.get(key))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        log(f"Invalid or missing {key!r} in artifact.")
        return None
    if not (lo <= value <= hi):
        log(f"{key} = {value} is out of range [{fmt(lo)}, {fmt(hi)}].")
        return None
    return value


def oneline(text: object) -> str:
    return str(text).replace("\n", " ").strip()


def rationale_for(data: dict, key: str) -> str:
    rationale = data.get("rationale") or {}
    return oneline(rationale.get(key) or "(no rationale given)")


def clamp_1_10(value: float) -> int:
    return max(1, min(10, round(value)))


def comment_body(
    method: str,
    score: int,
    factor_line: str,
    calc_line: str,
    data: dict,
    rationale_keys: list[str],
) -> str:
    summary = oneline(data.get("summary") or "")
    lines = [
        f"### 🔮 {method.upper()} score: **{score}/10**",
        "",
        factor_line,
        f"<sub>{calc_line}</sub>",
    ]
    if summary:
        lines += ["", summary]
    lines += [
        "",
        "<details><summary>Factor reasoning</summary>",
        "",
        *[f"- **{key.capitalize()}** — {rationale_for(data, key)}" for key in rationale_keys],
        "",
        "</details>",
    ]
    return "\n".join(lines)


def render_ice(data: dict) -> tuple[int, str] | None:
    impact = number(data, "impact", 1, 10)
    confidence = number(data, "confidence", 1, 10)
    ease = number(data, "ease", 1, 10)
    if impact is None or confidence is None or ease is None:
        return None
    raw = impact * confidence * ease
    score = clamp_1_10(math.cbrt(raw))
    factor_line = (
        f"Impact {fmt(impact)} · Confidence {fmt(confidence)} · Ease {fmt(ease)}"
    )
    calc_line = (
        f"Score = geometric mean of the 1–10 factors: "
        f"∛({fmt(impact)} × {fmt(confidence)} × {fmt(ease)}) = ∛{fmt(raw)} ≈ "
        f"{math.cbrt(raw):.1f} → **{score}**. Higher = prioritize."
    )
    return score, comment_body(
        "ice", score, factor_line, calc_line, data, ["impact", "confidence", "ease"]
    )


def render_rice(data: dict) -> tuple[int, str] | None:
    reach = number(data, "reach", 0, 1e9)
    impact = number(data, "impact", 0.25, 3)
    confidence = number(data, "confidence", 0, 100)
    effort = number(data, "effort", 0.01, 1000)
    if reach is None or impact is None or confidence is None or effort is None:
        return None
    if confidence > 1:  # tolerate percentages (e.g. 80 instead of 0.8)
        confidence /= 100
    raw = reach * impact * confidence / effort
    score = clamp_1_10(math.log2(raw + 1))
    reach_unit = oneline(data.get("reach_unit") or "per quarter")
    factor_line = (
        f"Reach {fmt(reach)} ({reach_unit}) · Impact {fmt(impact)} · "
        f"Confidence {fmt(confidence * 100)}% · Effort {fmt(effort)} person-months"
    )
    calc_line = (
        f"Raw RICE = (Reach × Impact × Confidence) ÷ Effort = "
        f"({fmt(reach)} × {fmt(impact)} × {fmt(confidence)}) ÷ {fmt(effort)} = "
        f"{fmt(round(raw, 1))}; score = log₂(raw + 1) ≈ {math.log2(raw + 1):.1f}, "
        f"clamped to 1–10 → **{score}** (each +1 ≈ double the value per effort)."
    )
    return score, comment_body(
        "rice",
        score,
        factor_line,
        calc_line,
        data,
        ["reach", "impact", "confidence", "effort"],
    )


# --------------------------------------------------------------------------- #
# Labels
# --------------------------------------------------------------------------- #


def label_color(score: int) -> str:
    if score >= 7:
        return "0e8a16"  # green
    if score >= 4:
        return "fbca04"  # yellow
    return "d93f0b"  # orange/red


def apply_score_label(issue: Issue, method: str, score: int) -> None:
    """Add ``ice-<n>``/``rice-<n>``, replacing any stale score label."""
    label = f"{method}-{score}"
    for existing in issue.labels:
        if existing.name.startswith(("ice-", "rice-")) and existing.name != label:
            issue.remove_from_labels(existing)
    ensure_label(issue.repository, label, label_color(score))
    issue.add_to_labels(label)
    log(f"Labeled issue #{issue.number} with {label}.")


# --------------------------------------------------------------------------- #


def main() -> None:
    t0 = time.monotonic()
    log(
        "⚠️ DEPRECATION: lucid-agent is deprecated and no longer actively "
        "maintained. It still runs when pinned to @v1 but may be removed in a "
        "future major release (v2)."
    )
    settings = Settings.from_env()
    opencode = Opencode.from_env()

    repo = Github(settings.token).get_repo(settings.repo_name)
    issue = repo.get_issue(settings.issue_number)
    if issue.pull_request is not None:
        log(f"#{settings.issue_number} is a pull request; lucid only scores issues.")
        write_summary(RunResult(
            agent="lucid",
            version=__version__,
            action="Skipped — target is a pull request",
            url=issue.html_url,
            duration_s=time.monotonic() - t0,
            model=opencode.model,
        ))
        return
    log(f"Scoring issue #{issue.number} ({settings.method.upper()}): {issue.title}")

    opencode.plan_then_build(
        build_prompt(issue, settings),
        build_instructions(settings.method),
        plan_instructions=PLAN_INSTRUCTIONS,
        build_lead_in=BUILD_LEAD_IN,
    )

    data = read_json_artifact(os.path.join(os.getcwd(), ARTIFACT))
    if data is None:
        sys.exit("lucid: opencode did not produce a usable score artifact.")

    render = render_ice if settings.method == "ice" else render_rice
    result = render(data)
    if result is None:
        sys.exit("lucid: score artifact failed validation; no comment posted.")
    score, comment = result

    comment += (
        "\n<sub>🔮 Scored by [lucid-agent](https://github.com/chamoda/agent-foundry), "
        "powered by [opencode](https://opencode.ai).</sub>"
    )
    issue.create_comment(comment)
    apply_score_label(issue, settings.method, score)
    log(
        f"Posted {settings.method.upper()} score {score}/10 on issue #{issue.number}."
    )
    write_summary(RunResult(
        agent="lucid",
        version=__version__,
        action=f"Scored issue #{issue.number} ({settings.method.upper()}: {score}/10)",
        url=issue.html_url,
        duration_s=time.monotonic() - t0,
        model=opencode.model,
    ))


if __name__ == "__main__":
    main()
