"""Drive opencode to review a pull request quickly and post inline comments.

Entry point for ``python -m warden`` / the ``warden`` console script.

Triggered when a pull request is opened/updated (or manually via
``workflow_dispatch``). Each run:

1. Works out **what** to review. warden keeps a hidden state marker comment on
   the PR recording the last commit it reviewed. On the first run it reviews
   the whole diff (merge-base..head); on later runs it reviews **only** the new
   commits (last-reviewed..head), so re-reviews after a push are cheap.
2. Reads ``REVIEW.md`` at the repo root, if present, for maintainer review
   guidance. Absent that, it leans on two defaults: **security** and
   **matching the existing code patterns**.
3. Grabs just enough project context to review well, then reviews the diff —
   it is told to stay fast and not audit the whole codebase.
4. Avoids repeating itself: warden's existing comments on this PR are fed back
   as "already raised, do not repeat", and past warden suggestions that drew a
   👎 or a human reply (on this and recent PRs) are fed back as "this kind of
   suggestion was not wanted — don't make it again".
5. Posts its findings as **inline review comments** on the exact lines, and
   updates the state marker to the head commit.

opencode runs in two phases: a read-only ``plan`` pass that orients and finds
the issues, then a ``build`` pass that writes a structured JSON artifact. This
script validates the findings and posts them, so warden never edits code or
touches git.

Required env: ``GITHUB_REPOSITORY``, ``GITHUB_TOKEN``, and the PR number via
``PR_NUMBER`` (from the event) or ``DISPATCH_PR``.
Optional env: ``OPENCODE_MODEL``, ``OPENCODE_VARIANT`` (default ``high``),
``OPENCODE_PLAN`` (default ``true``), ``REVIEW_FILE`` (default ``REVIEW.md``),
``REVIEW_FOCUS`` (extra emphasis appended to the defaults), ``MAX_COMMENTS``
(default ``25``), ``FEEDBACK_PR_LIMIT`` (recent PRs scanned for past feedback,
default ``20``).
"""

from __future__ import annotations

import itertools
import os
import re
import sys
from dataclasses import dataclass

from github import Github, GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository

from foundry_core import Opencode, env, env_int, log, run
from foundry_core.artifact import read_json_artifact

# opencode writes the review here (in the consumer's checked-out repo).
ARTIFACT = "warden_review.json"

# Hidden markers embedded in warden's own comments so it can recognise them
# later regardless of which token/identity actually authored them.
COMMENT_MARKER = "<!-- warden:review -->"
STATE_MARKER = "<!-- warden:state -->"

SIGNATURE = (
    "\n<sub>🛡️ Reviewed by "
    "[warden-agent](https://github.com/chamoda/agent-foundry), "
    "powered by [opencode](https://opencode.ai).</sub>"
)

DEFAULT_FOCUS = (
    "Pay special attention to:\n"
    "- **Security** — injection, authz/authn mistakes, unsafe input handling, "
    "secrets, unsafe deserialization, path/SSRF issues, and anything that "
    "widens the attack surface.\n"
    "- **Consistency with existing code** — match the patterns, naming, "
    "abstractions and conventions already used in this repository. Flag code "
    "that reinvents something the project already has or diverges from how the "
    "surrounding code does it."
)

PLAN_INSTRUCTIONS = (
    "## First: orient, then find issues (read-only)\n"
    "Spend a SHORT amount of time getting just enough project context to review "
    "the diff well — the conventions of the surrounding code and the subsystems "
    "this change touches. Do NOT audit the whole codebase or review code outside "
    "the diff. Then list the concrete issues worth an inline comment. Do NOT "
    "write any files yet."
)
BUILD_LEAD_IN = "Now write your review."

# How many past warden suggestions (with pushback) to feed back, and how far to
# truncate each, so the prompt stays small.
MAX_FEEDBACK = 15
SNIPPET = 240


@dataclass(frozen=True)
class Settings:
    repo_name: str
    token: str
    pr_number: int
    review_file: str
    extra_focus: str
    max_comments: int
    feedback_pr_limit: int

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            repo_name=env("GITHUB_REPOSITORY", required=True),
            token=env("GITHUB_TOKEN", required=True),
            pr_number=int(env("DISPATCH_PR") or env("PR_NUMBER", required=True)),
            review_file=env("REVIEW_FILE", "REVIEW.md"),
            extra_focus=env("REVIEW_FOCUS", "").strip(),
            max_comments=env_int("MAX_COMMENTS", 25),
            feedback_pr_limit=env_int("FEEDBACK_PR_LIMIT", 20),
        )


# --------------------------------------------------------------------------- #
# Git / diff helpers
# --------------------------------------------------------------------------- #


def _git(args: list[str]) -> str:
    """Run a read-only git command, returning stdout (empty on failure)."""
    try:
        out = run(["git", *args], capture_output=True, text=True)
        return (out.stdout or "").strip()
    except Exception as exc:  # pragma: no cover - git availability varies
        log(f"git {' '.join(args)} failed: {exc}")
        return ""


def ensure_commits(*shas: str) -> None:
    """Best-effort fetch so the SHAs we want to diff are present locally."""
    for sha in shas:
        if sha and not _git(["cat-file", "-e", f"{sha}^{{commit}}"]):
            _git(["fetch", "--no-tags", "--depth=200", "origin", sha])


def changed_files(diff_range: str) -> list[str]:
    out = _git(["diff", "--name-only", diff_range])
    return [line for line in out.splitlines() if line]


# --------------------------------------------------------------------------- #
# State marker (what we last reviewed)
# --------------------------------------------------------------------------- #


def find_state_comment(pr: PullRequest):
    for comment in pr.get_issue_comments():
        if STATE_MARKER in (comment.body or ""):
            return comment
    return None


def reviewed_sha(state_comment) -> str | None:
    if state_comment is None:
        return None
    match = re.search(r"warden:sha=([0-9a-f]{7,40})", state_comment.body or "")
    return match.group(1) if match else None


def upsert_state(pr: PullRequest, state_comment, head_sha: str, posted: int) -> None:
    body = (
        f"{STATE_MARKER}\n"
        f"<!-- warden:sha={head_sha} -->\n"
        f"🛡️ **warden** reviewed this PR up to `{head_sha[:7]}` — "
        f"{posted} inline comment(s) on the latest changes.{SIGNATURE}"
    )
    if state_comment is not None:
        state_comment.edit(body)
    else:
        pr.create_issue_comment(body)


# --------------------------------------------------------------------------- #
# Context: what warden already said + what got pushback
# --------------------------------------------------------------------------- #


def strip_markers(body: str) -> str:
    return re.sub(r"<!--.*?-->", "", body or "", flags=re.DOTALL).strip()


def truncate(text: str) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= SNIPPET else text[:SNIPPET] + "…"


def already_raised(pr: PullRequest) -> str:
    """warden's own existing inline comments on this PR — do not repeat them."""
    items = [
        f"- {c.path}:{c.line or c.original_line or '?'} — {truncate(strip_markers(c.body))}"
        for c in pr.get_review_comments()
        if COMMENT_MARKER in (c.body or "")
    ]
    if not items:
        return ""
    return "\n".join(
        [
            "## Already raised on THIS pull request — do NOT repeat these",
            *items,
        ]
    )


def _human_replies(pr: PullRequest) -> dict[int, list]:
    """Map a review-comment id -> list of human (non-warden) replies to it."""
    replies: dict[int, list] = {}
    for c in pr.get_review_comments():
        parent = getattr(c, "in_reply_to_id", None)
        if parent and COMMENT_MARKER not in (c.body or ""):
            replies.setdefault(parent, []).append(c)
    return replies


def _dismissed_in_pr(pr: PullRequest, budget: int) -> list[str]:
    """warden comments in `pr` that drew a human reply or a 👎 reaction."""
    out: list[str] = []
    replies = _human_replies(pr)
    for c in pr.get_review_comments():
        if budget <= 0:
            break
        if COMMENT_MARKER not in (c.body or ""):
            continue
        signal = ""
        if c.id in replies:
            signal = "reply: " + truncate(strip_markers(replies[c.id][0].body))
        else:
            try:
                if any(r.content == "-1" for r in c.get_reactions()):
                    signal = "got a 👎"
            except GithubException:
                pass
        if signal:
            out.append(f"- ({c.path}) “{truncate(strip_markers(c.body))}” → {signal}")
            budget -= 1
    return out


def dismissed_feedback(repo: Repository, settings: Settings) -> str:
    """Past warden suggestions that were pushed back on — avoid their kind."""
    items: list[str] = []
    pulls = repo.get_pulls(state="all", sort="updated", direction="desc")
    for pr in itertools.islice(pulls, settings.feedback_pr_limit):
        items += _dismissed_in_pr(pr, MAX_FEEDBACK - len(items))
        if len(items) >= MAX_FEEDBACK:
            break
    if not items:
        return ""
    return "\n".join(
        [
            "## Feedback on PAST warden reviews — do NOT make these kinds of "
            "suggestions again",
            "Each line is a previous warden comment and the pushback it got. "
            "Treat the underlying *kind* of suggestion as unwelcome here.",
            *items,
        ]
    )


def review_guidance(settings: Settings) -> str:
    path = os.path.join(os.getcwd(), settings.review_file)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return (
                f"## Review guidance — {settings.review_file}\n"
                "Follow this maintainer guidance above all else:\n\n" + fh.read()
            )
    focus = DEFAULT_FOCUS
    if settings.extra_focus:
        focus += f"\n- {settings.extra_focus}"
    return (
        f"## Review focus ({settings.review_file} not present)\n"
        f"No {settings.review_file} in this repo, so use these defaults.\n\n{focus}"
    )


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #


def build_prompt(
    pr: PullRequest,
    settings: Settings,
    diff_range: str,
    files: list[str],
    incremental: bool,
) -> str:
    scope = (
        "This is a RE-REVIEW of only the newest commits pushed since your last "
        f"review. Review ONLY the changes in `{diff_range}` — do not re-examine "
        "code you already reviewed, and keep it quick."
        if incremental
        else f"Review the changes in `{diff_range}` (the full pull request diff)."
    )
    file_list = (
        "## Files changed in this range\n" + "\n".join(f"- {f}" for f in files)
        if files
        else ""
    )
    return "\n".join(
        filter(
            None,
            [
                f"You are warden, a fast, security-minded code reviewer for the "
                f"repository {settings.repo_name}.",
                "Review the pull request below. Be efficient: surface only "
                "issues that genuinely warrant an inline comment — correctness "
                "and security bugs first, then clear violations of the "
                "project's existing conventions. Do not nitpick formatting a "
                "linter would catch, and do not comment to praise.",
                "",
                f"# Pull request #{pr.number}: {pr.title}",
                pr.body or "(no description)",
                "",
                f"## What to review\n{scope}",
                "Inspect the diff with git (e.g. `git diff " + diff_range + "`). "
                "Only comment on lines that appear in this diff.",
                "",
                file_list,
                "",
                review_guidance(settings),
                "",
                already_raised(pr),
                "",
                dismissed_feedback(pr.base.repo, settings),
            ],
        )
    )


def build_instructions(settings: Settings) -> str:
    return "\n".join(
        [
            f"Write your review to ./{ARTIFACT} in the repository root as valid "
            "JSON ONLY (no surrounding prose, no markdown fences), with keys:",
            '  - "summary": 1–2 sentence overall assessment of these changes.',
            '  - "comments": an array (possibly empty) of inline comments, each '
            "an object with keys:",
            '      - "path": file path exactly as it appears in the diff',
            '      - "line": the line number in the NEW version of the file '
            "(for a deleted line, the old line number)",
            '      - "side": "RIGHT" for added/context lines, "LEFT" for a '
            "deleted line (default RIGHT)",
            '      - "severity": one of "security", "bug", "maintainability", "nit"',
            '      - "body": the review comment (markdown). Be specific and '
            "actionable; suggest the fix.",
            f"Include at most {settings.max_comments} comments — the most "
            "important ones. Only comment on lines present in the diff you were "
            "asked to review. Do NOT comment on the PR yourself and do NOT touch "
            "git.",
        ]
    )


# --------------------------------------------------------------------------- #
# Posting the review
# --------------------------------------------------------------------------- #


def valid_comments(data: dict, settings: Settings) -> list[dict]:
    raw = data.get("comments")
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        try:
            line = int(item.get("line"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        body = str(item.get("body") or "").strip()
        if not path or line < 1 or not body:
            continue
        side = "LEFT" if str(item.get("side", "")).upper() == "LEFT" else "RIGHT"
        severity = str(item.get("severity") or "").lower()
        out.append(
            {"path": path, "line": line, "side": side, "body": body, "severity": severity}
        )
        if len(out) >= settings.max_comments:
            break
    return out


def _wrap(body: str, severity: str | None = None) -> str:
    tag = {"security": "🔒", "bug": "🐞", "maintainability": "🧱", "nit": "💬"}
    prefix = tag.get(str(severity or "").lower(), "")
    head = f"{prefix} " if prefix else ""
    return f"{COMMENT_MARKER}\n{head}{body}"


def post_review(
    repo: Repository,
    pr: PullRequest,
    head_sha: str,
    summary: str,
    comments: list[dict],
) -> int:
    """Post inline comments as one review; fall back to individual comments.

    A ``security`` finding makes warden **request changes** (a blocking review);
    otherwise it leaves a plain ``COMMENT`` review. GitHub won't let a token
    request changes on its own PR, so the fallback degrades to a comment.
    """
    commit = repo.get_commit(head_sha)
    blocking = any(c.get("severity") == "security" for c in comments)
    event = "REQUEST_CHANGES" if blocking else "COMMENT"
    note = (
        "\n\n⛔ **Requesting changes** — at least one **security** issue is "
        "flagged inline below."
        if blocking
        else ""
    )
    body = (summary or "warden reviewed the latest changes.") + note + SIGNATURE
    if not comments:
        pr.create_review(commit=commit, body=body, event="COMMENT")
        return 0

    review_comments = [
        {
            "path": c["path"],
            "line": c["line"],
            "side": c["side"],
            "body": _wrap(c["body"], c.get("severity")),
        }
        for c in comments
    ]
    try:
        pr.create_review(
            commit=commit, body=body, event=event, comments=review_comments
        )
        return len(review_comments)
    except GithubException as exc:
        log(f"Batched review failed ({exc}); posting comments individually.")

    posted = 0
    for c in comments:
        try:
            pr.create_review_comment(
                body=_wrap(c["body"], c.get("severity")),
                commit=commit,
                path=c["path"],
                line=c["line"],
                side=c["side"],
            )
            posted += 1
        except GithubException as exc:
            log(f"Skipped comment on {c['path']}:{c['line']} ({exc}).")
    # Register the overall review verdict after the standalone comments. If even
    # that is refused (e.g. reviewing our own PR), leave the summary as a note.
    try:
        pr.create_review(commit=commit, body=body, event=event)
    except GithubException as exc:
        log(f"Could not submit {event} review ({exc}); posting summary comment.")
        pr.create_issue_comment(body)
    return posted


# --------------------------------------------------------------------------- #


def main() -> None:
    settings = Settings.from_env()
    opencode = Opencode.from_env()

    repo = Github(settings.token).get_repo(settings.repo_name)
    pr = repo.get_pull(settings.pr_number)
    if pr.state != "open":
        log(f"PR #{pr.number} is {pr.state}; warden only reviews open PRs.")
        return

    head_sha = pr.head.sha
    state_comment = find_state_comment(pr)
    last_sha = reviewed_sha(state_comment)

    if last_sha == head_sha:
        log(f"PR #{pr.number} already reviewed at {head_sha[:7]}; nothing to do.")
        return

    incremental = last_sha is not None
    base_sha = pr.base.sha
    ensure_commits(base_sha, head_sha, last_sha or "")
    diff_range = f"{last_sha}..{head_sha}" if incremental else f"{base_sha}...{head_sha}"
    files = changed_files(diff_range)
    if not files:
        log(f"No changed files in {diff_range}; updating state and stopping.")
        upsert_state(pr, state_comment, head_sha, 0)
        return

    log(
        f"Reviewing PR #{pr.number} ({'incremental' if incremental else 'full'}): "
        f"{diff_range} ({len(files)} file(s))"
    )

    opencode.plan_then_build(
        build_prompt(pr, settings, diff_range, files, incremental),
        build_instructions(settings),
        plan_instructions=PLAN_INSTRUCTIONS,
        build_lead_in=BUILD_LEAD_IN,
    )

    data = read_json_artifact(os.path.join(os.getcwd(), ARTIFACT))
    if data is None:
        sys.exit("warden: opencode did not produce a usable review artifact.")

    comments = valid_comments(data, settings)
    summary = " ".join(str(data.get("summary") or "").split())
    posted = post_review(repo, pr, head_sha, summary, comments)
    upsert_state(pr, state_comment, head_sha, posted)
    log(f"Posted {posted} inline comment(s) on PR #{pr.number}.")


if __name__ == "__main__":
    main()
