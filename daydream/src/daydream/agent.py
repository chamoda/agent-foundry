"""Drive opencode to research the project and file well-thought-out new issues.

Entry point for ``python -m daydream`` / the ``daydream`` console script.

Each run:

1. Gathers the repo's **existing issues** so opencode knows what already exists
   and avoids duplicates: open issues, recently completed ones, and — kept
   permanently in context — issues **closed as "not planned"**, which the
   prompt treats as explicitly rejected ideas never to be re-proposed.
2. Reads **VISION.md** at the consuming project's root, if present — the place
   maintainers record their long-term vision for new work. opencode prefers an
   idea from there that has not yet been turned into an issue, and researches it
   in depth.
3. If VISION.md is absent, or every idea in it already has a corresponding issue,
   it falls back to a configurable **idea / maintenance split** (default 50/50,
   ``IDEA_RATIO``): roughly half brand-new ideas, half maintenance / project
   health issues (tests, refactors, deps, docs, CI, performance, security).

opencode runs in two phases: a read-only ``plan`` agent researches and drafts,
then the ``build`` agent writes a structured issue artifact which this script
turns into a real GitHub issue (with category labels).

Required env: ``GITHUB_REPOSITORY``, ``GITHUB_TOKEN``.
Optional env: ``OPENCODE_MODEL``, ``OPENCODE_VARIANT`` (default ``high``),
``OPENCODE_PLAN`` (default ``true``), ``MAX_ISSUES`` (default ``1``),
``IDEA_RATIO`` (default ``0.5``), ``VISION_FILE`` (default ``VISION.md``),
``IDEA_LABEL``, ``MAINTENANCE_LABEL``, ``BASE_LABEL``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import islice

from github import Github
from github.Repository import Repository

from foundry_core import (
    Harness,
    ensure_label,
    env,
    env_float,
    env_int,
    get_harness,
    log,
)
from foundry_core.artifact import read_json_artifact

# opencode writes the chosen issue here (in the consumer's checked-out repo).
ARTIFACT = "daydream_issue.json"

PLAN_INSTRUCTIONS = (
    "## First: research only\n"
    "Explore the codebase (and the web if useful) and decide on the single "
    "best issue to propose per the policy above. Do NOT write any files yet."
)
BUILD_LEAD_IN = "Now write the issue you decided on."

LABEL_COLORS = {
    "base": "5319e7",
    "idea": "1d76db",
    "maintenance": "0e8a16",
}


@dataclass(frozen=True)
class Settings:
    repo_name: str
    token: str
    max_issues: int
    idea_ratio: float
    vision_file: str
    idea_label: str
    maintenance_label: str
    base_label: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            repo_name=env("GITHUB_REPOSITORY", required=True),
            token=env("GITHUB_TOKEN", required=True),
            max_issues=env_int("MAX_ISSUES", 1),
            idea_ratio=env_float("IDEA_RATIO", 0.5),
            vision_file=env("VISION_FILE", "VISION.md"),
            idea_label=env("IDEA_LABEL", "daydream-idea"),
            maintenance_label=env("MAINTENANCE_LABEL", "daydream-maintenance"),
            base_label=env("BASE_LABEL", "daydream"),
        )


# --------------------------------------------------------------------------- #
# Context gathering
# --------------------------------------------------------------------------- #


def snippet_line(issue, limit: int) -> str:
    body = (issue.body or "").strip().replace("\r", "")
    snippet = body[:limit] + ("…" if len(body) > limit else "")
    return f"- #{issue.number} {issue.title}\n  {snippet}".rstrip()


def existing_issues_context(repo: Repository, settings: Settings) -> str:
    open_lines: list[str] = []
    for issue in islice(repo.get_issues(state="open", sort="created", direction="desc"), 100):
        if issue.pull_request is not None:  # skip PRs
            continue
        open_lines.append(snippet_line(issue, 400))

    completed_lines: list[str] = []
    rejected_lines: dict[int, str] = {}
    for issue in islice(repo.get_issues(state="closed", sort="updated", direction="desc"), 50):
        if issue.pull_request is not None:
            continue
        if issue.state_reason == "not_planned":
            rejected_lines[issue.number] = snippet_line(issue, 200)
        else:
            completed_lines.append(f"- #{issue.number} {issue.title}")

    # Rejections are durable signal: always include every not-planned issue the
    # agent itself filed, even ones that scrolled out of the recent-50 window.
    for issue in repo.get_issues(state="closed", labels=[settings.base_label]):
        if issue.pull_request is None and issue.state_reason == "not_planned":
            rejected_lines.setdefault(issue.number, snippet_line(issue, 200))

    parts = ["## Existing OPEN issues (do not duplicate these)"]
    parts.append("\n".join(open_lines) if open_lines else "(none)")
    parts.append("\n## Recently CLOSED issues — completed (already done; do not re-file)")
    parts.append("\n".join(completed_lines) if completed_lines else "(none)")
    parts.append(
        "\n## Issues closed as NOT PLANNED — the maintainer REJECTED these\n"
        "Do not propose these again, and do not propose close variations of "
        "the same idea. Treat the corresponding ideas as explicitly declined, "
        "even if they appear in the maintainer vision file."
    )
    parts.append("\n".join(rejected_lines.values()) if rejected_lines else "(none)")
    return "\n".join(parts)


def read_vision_file(settings: Settings) -> str | None:
    path = os.path.join(os.getcwd(), settings.vision_file)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    return None


def category_counts(repo: Repository, settings: Settings) -> tuple[int, int]:
    """How many idea vs maintenance issues the agent has filed so far (all states)."""
    idea = repo.get_issues(state="all", labels=[settings.idea_label]).totalCount
    maint = repo.get_issues(state="all", labels=[settings.maintenance_label]).totalCount
    return idea, maint


def fallback_category(idea_count: int, maint_count: int, idea_ratio: float) -> str:
    total = idea_count + maint_count
    if total == 0:
        return "idea"
    return "idea" if (idea_count / total) < idea_ratio else "maintenance"


# --------------------------------------------------------------------------- #
# Prompt + artifact
# --------------------------------------------------------------------------- #


def build_prompt(repo: Repository, settings: Settings) -> str:
    vision_md = read_vision_file(settings)
    vision_name = settings.vision_file
    idea_count, maint_count = category_counts(repo, settings)
    fallback = fallback_category(idea_count, maint_count, settings.idea_ratio)

    ideas_section = (
        f"## Maintainer vision — {vision_name}\n{vision_md}"
        if vision_md
        else f"## Maintainer vision — {vision_name}\n{vision_name} is not present in this repository."
    )

    return "\n".join(
        [
            f"You are a product-minded engineer and maintainer for the repository {settings.repo_name}.",
            "Your job is to propose ONE new, high-quality GitHub issue after deep research.",
            "",
            existing_issues_context(repo, settings),
            "",
            ideas_section,
            "",
            "## How to choose what to propose (follow in order)",
            f"1. If {vision_name} is present and contains an idea/direction NOT yet "
            "represented by any existing issue above, choose that and research it. "
            'Set "category" to "idea".',
            f"2. Otherwise ({vision_name} absent, or every idea in it already has a "
            "corresponding issue), pick a category to keep an overall "
            f"{settings.idea_ratio:.0%}/{1 - settings.idea_ratio:.0%} idea/maintenance balance. "
            f"So far the agent has filed ideas={idea_count}, maintenance={maint_count}. "
            f'To move toward the target, use category "{fallback}" this run.',
            '   - "idea": a brand-new feature/product idea that fits the project direction.',
            '   - "maintenance": a project-health issue grounded in the code — tests, '
            "refactors, dependency upgrades, docs, CI, performance, security, tech debt.",
            "",
            "## Research",
            "Explore the codebase thoroughly; use web research where it helps. Base the "
            "proposal on real findings in THIS project, not generic advice. Make sure it "
            "is not a duplicate of any existing issue listed above.",
        ]
    )


def build_instructions() -> str:
    return "\n".join(
        [
            f"Write the chosen issue to ./{ARTIFACT} in the repository root as valid "
            "JSON ONLY (no surrounding prose, no markdown fences), with keys:",
            '  - "title": a concise issue title',
            '  - "category": "idea" or "maintenance"',
            '  - "body": a thorough markdown issue body with these sections: '
            "Problem/Motivation, Proposed approach, Relevant files/areas (with paths), "
            "Acceptance criteria, and any references.",
            'If you conclude no worthwhile issue should be created, write {"category": "none"}.',
            "Do NOT create the GitHub issue yourself and do NOT touch git.",
        ]
    )


# --------------------------------------------------------------------------- #
# Issue creation
# --------------------------------------------------------------------------- #


def create_issue(repo: Repository, settings: Settings, data: dict) -> bool:
    category = (data.get("category") or "").lower()
    if category == "none":
        log("opencode decided there is no worthwhile issue to create this run.")
        return False
    if category not in ("idea", "maintenance"):
        log(f"Skipping: unknown category {category!r}.")
        return False

    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    if not title or not body:
        log("Skipping: artifact missing title or body.")
        return False

    category_label = (
        settings.idea_label if category == "idea" else settings.maintenance_label
    )
    ensure_label(repo, settings.base_label, LABEL_COLORS["base"])
    ensure_label(repo, category_label, LABEL_COLORS[category])

    body += "\n\n<sub>💭 Filed by [daydream-agent](https://github.com/chamoda/agent-foundry), powered by [opencode](https://opencode.ai).</sub>"

    issue = repo.create_issue(title=title, body=body)
    issue.set_labels(settings.base_label, category_label)
    log(f"Opened {category} issue #{issue.number}: {issue.title} — {issue.html_url}")
    return True


# --------------------------------------------------------------------------- #


def propose_one(repo: Repository, settings: Settings, harness: Harness) -> bool:
    harness.plan_then_build(
        build_prompt(repo, settings),
        build_instructions(),
        plan_instructions=PLAN_INSTRUCTIONS,
        build_lead_in=BUILD_LEAD_IN,
    )
    data = read_json_artifact(os.path.join(os.getcwd(), ARTIFACT))
    if data is None:
        return False
    return create_issue(repo, settings, data)


def main() -> None:
    settings = Settings.from_env()
    harness = get_harness()

    repo = Github(settings.token).get_repo(settings.repo_name)
    created = 0
    for _ in range(settings.max_issues):
        if propose_one(repo, settings, harness):  # counts/context recomputed each round to rebalance
            created += 1
        else:
            log("Nothing to create this round; stopping.")
            break
    log(f"daydream-agent created {created} issue(s).")


if __name__ == "__main__":
    main()
