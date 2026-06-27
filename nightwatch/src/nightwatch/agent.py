"""Drive opencode to autonomously work an issue (or revise a rejected PR).

Entry point for ``python -m nightwatch`` / the ``nightwatch`` console script.

Modes (selected automatically from ``GITHUB_EVENT_NAME``):

* ``schedule`` / ``workflow_dispatch`` -- pick the oldest open issue that has no
  active PR, and propose a solution as a new PR.
* ``pull_request_review`` -- a reviewer requested changes on a branch the agent
  owns; revise that branch in place and push.

In both modes opencode is fed extra context: the issue discussion, the reviewer
feedback from any previously rejected PRs for the same issue, and (in revision
mode) the current review comments.

Each task runs in two phases at high reasoning effort: a read-only ``plan``
agent first produces a detailed implementation plan, then the ``build`` agent
continues the same session and executes it. Set ``OPENCODE_PLAN=false`` to skip
straight to a single build pass.

Required env: ``GITHUB_REPOSITORY``, ``GITHUB_TOKEN``.
Optional env: ``OPENCODE_MODEL``, ``OPENCODE_VARIANT`` (reasoning effort,
default ``high``), ``OPENCODE_PLAN`` (default ``true``), ``MAX_ATTEMPTS``,
``BRANCH_PREFIX``, ``BOT_NAME``, ``BOT_EMAIL``, ``DISPATCH_ISSUE``,
``PR_NUMBER``, ``PR_BRANCH``.
"""

from __future__ import annotations

import itertools
import subprocess
from dataclasses import dataclass

from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository

from foundry_core import (
    Opencode,
    env,
    env_bool,
    env_int,
    get_score_from_labels,
    log,
    references_issue,
    run,
    working_tree_dirty,
)

PLAN_INSTRUCTIONS = (
    "## First: plan only\n"
    "Explore the codebase and write a detailed, step-by-step implementation "
    "plan: the files to change and the approach. Do NOT edit any files yet."
)
BUILD_LEAD_IN = "Now execute the plan you just produced."


@dataclass(frozen=True)
class Settings:
    repo_name: str
    token: str
    max_attempts: int
    branch_prefix: str
    bot_name: str
    bot_email: str
    event: str
    dispatch_issue: str
    pr_number: str
    pr_branch: str
    prefer_scored: bool

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            repo_name=env("GITHUB_REPOSITORY", required=True),
            token=env("GITHUB_TOKEN", required=True),
            max_attempts=env_int("MAX_ATTEMPTS", 3),
            branch_prefix=env("BRANCH_PREFIX", "nightwatch/issue-"),
            bot_name=env("BOT_NAME", "nightwatch-agent"),
            bot_email=env(
                "BOT_EMAIL", "nightwatch-agent[bot]@users.noreply.github.com"
            ),
            event=env("GITHUB_EVENT_NAME", "schedule"),
            dispatch_issue=env("DISPATCH_ISSUE"),
            pr_number=env("PR_NUMBER"),
            pr_branch=env("PR_BRANCH"),
            prefer_scored=env_bool("PREFER_SCORED", True),
        )

    def branch_for(self, issue_number: int) -> str:
        return f"{self.branch_prefix}{issue_number}"


# --------------------------------------------------------------------------- #
# Context gathering
# --------------------------------------------------------------------------- #


def rejected_pulls(repo: Repository, issue_number: int) -> list[PullRequest]:
    """Closed-but-not-merged PRs that referenced this issue."""
    rejected: list[PullRequest] = []
    closed = repo.get_pulls(state="closed", sort="created", direction="desc")
    for pr in itertools.islice(closed, 100):
        if pr.merged_at is None and references_issue(pr.body, issue_number):
            rejected.append(pr)
    return rejected


def rejected_attempts_context(repo: Repository, issue_number: int) -> str:
    rejected = rejected_pulls(repo, issue_number)
    if not rejected:
        return ""

    lines = [
        "",
        "## IMPORTANT — previous REJECTED attempts for this issue",
        "The pull requests below tried to solve this issue and were closed "
        "without merging. Read the reviewer feedback and do NOT repeat the same "
        "mistakes — take a corrected or different approach.",
    ]
    for pr in rejected:
        lines.append(f"\n### Rejected PR #{pr.number}: {pr.title}")
        lines.append(f"Author's summary: {pr.body or '(none)'}")
        reviews = [
            f"- [{r.state}] {r.user.login}: {r.body or '(no text)'}"
            for r in pr.get_reviews()
        ]
        if reviews:
            lines.append("Reviews:")
            lines.extend(reviews)
        inline = [
            f"- {c.path}:{c.line or c.original_line or '?'} — {c.body}"
            for c in pr.get_review_comments()
        ]
        if inline:
            lines.append("Inline review comments:")
            lines.extend(inline)
        general = [f"- {c.user.login}: {c.body}" for c in pr.get_issue_comments()]
        if general:
            lines.append("General PR comments:")
            lines.extend(general)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Issue mode
# --------------------------------------------------------------------------- #


def select_issue(repo: Repository, settings: Settings) -> int | None:
    if settings.dispatch_issue:
        return int(settings.dispatch_issue)

    open_prs = list(repo.get_pulls(state="open"))
    open_branches = {pr.head.ref for pr in open_prs}

    def has_open_pr(number: int) -> bool:
        # Skip if we already own a branch for it, OR any open PR references the
        # issue (e.g. "Closes #<n>") regardless of its branch name.
        if settings.branch_for(number) in open_branches:
            return True
        return any(references_issue(pr.body, number) for pr in open_prs)

    eligible = []
    for issue in repo.get_issues(state="open", sort="created", direction="asc"):
        if issue.pull_request is not None:
            continue
        if has_open_pr(issue.number):
            log(f"issue #{issue.number}: already has an open PR, skipping")
            continue
        attempts = len(rejected_pulls(repo, issue.number))
        if attempts >= settings.max_attempts:
            log(
                f"issue #{issue.number}: {attempts} rejected attempts "
                f"(>= {settings.max_attempts}), skipping"
            )
            continue
        eligible.append(issue)

    if not eligible:
        return None

    if settings.prefer_scored:
        eligible.sort(
            key=lambda i: (get_score_from_labels(i) or 0, -i.created_at.timestamp()),
            reverse=True,
        )
    return eligible[0].number


# GitHub refuses any push that creates or updates a file under
# .github/workflows/ unless the token carries the `workflows` permission (App
# token) or `workflow` scope (PAT). Both rejection messages contain this phrase.
# Where the maintainer has granted it, the push just succeeds and this never
# fires; it only triggers when the write is genuinely disallowed. See
# SECURITY.md (threat #3) for why GITHUB_TOKEN is kept off workflow files.
_WORKFLOW_PUSH_REJECTION = "create or update workflow"
_BLOCKED_MARKER = "<!-- nightwatch:workflow-push-blocked -->"


def try_push(branch: str, *, force: bool) -> bool:
    """Push `branch` to origin. Return True on success, False if the push was
    rejected solely because the token may not write under .github/workflows/.
    Any other push failure is re-raised."""
    cmd = ["git", "push"]
    if force:
        cmd.append("--force-with-lease")
    cmd += ["origin", branch]
    try:
        run(cmd, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        if stderr:
            log(stderr)
        if _WORKFLOW_PUSH_REJECTION in stderr:
            return False
        raise


def workflow_blocked_comment() -> str:
    return (
        f"{_BLOCKED_MARKER}\n"
        "🌙 nightwatch-agent built a solution but **could not push it**: the diff "
        "changes files under `.github/workflows/`, and the token running this agent "
        "is not allowed to write workflow files (GitHub blocks this unless the token "
        "has the `workflows` permission — see SECURITY.md).\n\n"
        "To let the agent handle changes like this, either grant `workflows: write` "
        "in the agent's workflow `permissions:` block (trusted / private setups only), "
        "or pass a PAT with the `workflow` scope as `github-token`. Otherwise this "
        "needs a human-authored PR."
    )


def already_blocked(existing) -> bool:
    return any(_BLOCKED_MARKER in (c.body or "") for c in existing)


def run_issue_mode(repo: Repository, settings: Settings, opencode: Opencode) -> None:
    issue_number = select_issue(repo, settings)
    if issue_number is None:
        log("No eligible open issue to work on. Nothing to do.")
        return

    issue = repo.get_issue(issue_number)
    branch = settings.branch_for(issue_number)
    log(f"Working on issue #{issue_number}: {issue.title}")

    context = "\n".join(
        [
            f"You are an autonomous software engineer working in the repository {settings.repo_name}.",
            "Your goal is a complete, working solution for the GitHub issue below.",
            "Follow the conventions in CLAUDE.md / AGENTS.md and match the existing code style.",
            "",
            f"# Issue #{issue_number}: {issue.title}",
            issue.body or "(no description)",
            "",
            "## Discussion on the issue",
            *[f"- {c.user.login}: {c.body}" for c in issue.get_comments()],
            rejected_attempts_context(repo, issue_number),
        ]
    )
    build_instructions = "\n".join(
        [
            "Implement a focused, minimal, correct solution, scoped to this issue only.",
            "Do NOT create commits or branches and do NOT touch git — just edit files",
            "in the working tree. The agent commits and opens the PR.",
        ]
    )
    opencode.plan_then_build(
        context,
        build_instructions,
        plan_instructions=PLAN_INSTRUCTIONS,
        build_lead_in=BUILD_LEAD_IN,
    )

    if not working_tree_dirty():
        log(f"opencode produced no changes for issue #{issue_number}.")
        issue.create_comment(
            "🌙 nightwatch-agent looked at this issue but did not produce any changes "
            "this run. It will retry on the next scheduled run."
        )
        return

    run(["git", "switch", "-C", branch])
    run(["git", "add", "-A"])
    run(
        [
            "git",
            "commit",
            "-m",
            (
                f"nightwatch: propose solution for #{issue_number}\n\n{issue.title}\n\n"
                "Automated proposal generated by nightwatch-agent (opencode). Prior "
                "rejected attempts (if any) were taken into account."
            ),
        ]
    )
    if not try_push(branch, force=True):
        log(f"Issue #{issue_number} needs workflow-file changes this token can't push.")
        if not already_blocked(issue.get_comments()):
            issue.create_comment(workflow_blocked_comment())
        return

    body = (
        f"🌙 **Automated proposal by [nightwatch-agent](https://github.com/chamoda/agent-foundry)** for #{issue_number}.\n\n"
        "Generated while it kept watch. The agent was given the issue text, the issue "
        "discussion, and the reviewer feedback from any previously rejected attempts.\n\n"
        f"Closes #{issue_number}\n\n"
        "> Reviewers: request changes via a PR review and the agent will automatically "
        "pick up your feedback and revise this branch.\n\n"
        "<sub>Powered by [opencode](https://opencode.ai).</sub>"
    )
    pr = repo.create_pull(
        title=f"{issue.title} (#{issue_number})",
        body=body,
        base=repo.default_branch,
        head=branch,
    )
    log(f"Opened PR #{pr.number} for issue #{issue_number}: {pr.html_url}")


# --------------------------------------------------------------------------- #
# Revision mode
# --------------------------------------------------------------------------- #


def run_revision_mode(repo: Repository, settings: Settings, opencode: Opencode) -> None:
    if not settings.pr_number or not settings.pr_branch:
        raise SystemExit("Missing required env var: PR_NUMBER / PR_BRANCH")
    pr_number = int(settings.pr_number)
    branch = settings.pr_branch
    log(f"Revising PR #{pr_number} on branch {branch}")

    run(["git", "fetch", "origin", branch])
    run(["git", "switch", branch])

    pr = repo.get_pull(pr_number)

    def review_summaries() -> list[str]:
        out = []
        for r in pr.get_reviews():
            if r.state in ("CHANGES_REQUESTED", "COMMENTED") and r.body:
                out.append(f"- {r.user.login}: {r.body}")
        return out

    context = "\n".join(
        [
            f"You are an autonomous software engineer working in the repository {settings.repo_name}.",
            f'You previously opened pull request #{pr_number} ("{pr.title}").',
            "A reviewer requested changes. The current working tree already contains",
            "your previous work. You must address ALL of the feedback below.",
            "",
            "## Reviewer feedback",
            "### Review summaries",
            *review_summaries(),
            "",
            "### Inline review comments",
            *[
                f"- {c.path}:{c.line or c.original_line or '?'} — {c.body}"
                for c in pr.get_review_comments()
            ],
            "",
            "### General PR comments",
            *[f"- {c.user.login}: {c.body}" for c in pr.get_issue_comments()],
        ]
    )
    build_instructions = "\n".join(
        [
            "Edit files to fully address the feedback. Keep the change focused.",
            "Do NOT create commits or touch git — the agent commits and pushes.",
        ]
    )
    opencode.plan_then_build(
        context,
        build_instructions,
        plan_instructions=PLAN_INSTRUCTIONS,
        build_lead_in=BUILD_LEAD_IN,
    )

    if not working_tree_dirty():
        log(f"opencode produced no changes for PR #{pr_number}.")
        pr.create_issue_comment(
            "🌙 nightwatch-agent reviewed the feedback but did not produce any changes this run."
        )
        return

    run(["git", "add", "-A"])
    run(["git", "commit", "-m", f"nightwatch: address review feedback on #{pr_number}"])
    if not try_push(branch, force=False):
        log(f"PR #{pr_number} needs workflow-file changes this token can't push.")
        if not already_blocked(pr.get_issue_comments()):
            pr.create_issue_comment(workflow_blocked_comment())
        return
    pr.create_issue_comment(
        "🌙 nightwatch-agent pushed changes addressing the latest review feedback. Please re-review."
    )
    log(f"Updated PR #{pr_number}.")


# --------------------------------------------------------------------------- #


def main() -> None:
    settings = Settings.from_env()
    opencode = Opencode.from_env()

    run(["git", "config", "user.name", settings.bot_name])
    run(["git", "config", "user.email", settings.bot_email])

    repo = Github(settings.token).get_repo(settings.repo_name)
    if settings.event == "pull_request_review":
        run_revision_mode(repo, settings, opencode)
    else:
        run_issue_mode(repo, settings, opencode)


if __name__ == "__main__":
    main()
