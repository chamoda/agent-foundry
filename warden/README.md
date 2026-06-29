# 🛡️ warden

> A continuous AI agent that **reviews every pull request and leaves inline comments** — fast. It grabs just enough project context, reviews the diff with a bias toward **security** and **matching your existing code patterns**, and posts its findings on the exact lines. On a new push it re-reviews **only the new commits**. **Powered by [opencode](https://opencode.ai).** Part of [agent-foundry](../README.md).

warden stands at the gate of the issue→PR loop: [**daydream**](../daydream/README.md) files issues, [**lucid**](../lucid/README.md) scores them, [**nightwatch**](../nightwatch/README.md) opens PRs — and **warden reviews them** before they merge.

## What it does

When a pull request is opened or updated (or on manual dispatch):

1. **Works out what to review.** warden keeps a hidden state marker on the PR recording the last commit it reviewed. The first run reviews the whole diff (`merge-base..head`); later runs review **only the new commits** (`last-reviewed..head`), so re-reviews after a push are cheap and fast.
2. **Reads `REVIEW.md`** at your repo root (if present) for maintainer review guidance. Without it, warden falls back to two defaults: **security** and **consistency with the existing codebase**.
3. **Reviews quickly** — it gets just enough context to understand the conventions and the subsystems the change touches, then reviews the diff. It is explicitly told *not* to audit the whole codebase or nitpick what a linter would catch.
4. **Doesn't repeat itself.** Its existing comments on the PR are fed back as *"already raised, do not repeat."* And past warden suggestions that drew a 👎 or a human reply — on this PR and recent ones — are fed back as *"this kind of suggestion was not wanted; don't make it again."*
5. **Posts inline comments** on the exact lines as a single PR review, then updates the marker to the head commit. If any finding is **security** severity, warden submits the review as **Request changes** (a blocking review); otherwise it's a plain comment review.

opencode runs read-only in two phases — a `plan` agent orients and finds the issues, then a `build` agent writes a structured findings artifact, which the action turns into inline review comments. warden never edits your code or touches git.

## The REVIEW.md file

`REVIEW.md` is a free-form file at your repo root where maintainers describe what they care about in review — there's no required format. Bullet points work great:

```markdown
# Review guidance
- Treat any new SQL string built with f-strings as a blocker.
- We use Result types, not exceptions, in the `core/` package.
- Public API changes must update `docs/api.md` in the same PR.
- Don't comment on test naming — we don't care.
```

When `REVIEW.md` is present, warden follows it above all else. When it's absent, warden defaults to security + matching existing patterns (extend that with the `review-focus` input).

## Incremental re-reviews

The first time warden sees a PR it reviews the full diff. After that, each push triggers a re-review of **only the commits added since** — warden diffs `last-reviewed..head`, reviews just those lines, and skips anything it already commented on. If the head commit hasn't changed since its last run, warden does nothing and spends no tokens. This keeps long-lived PRs cheap to keep reviewing.

> Re-reviews rely on full git history, so check out with `fetch-depth: 0`.

## Usage

Add a workflow (see [`examples/warden-agent.yaml`](../examples/warden-agent.yaml)):

```yaml
name: warden-agent
on:
  pull_request:
    types: [opened, synchronize, reopened]
  workflow_dispatch:
    inputs:
      pr:
        description: "PR number to review"
        required: true
        type: string

concurrency:
  group: warden-agent-${{ github.event.pull_request.number || github.event.inputs.pr }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: write

jobs:
  warden:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: chamoda/agent-foundry/warden@v1
```

That's the whole setup — `github-token` defaults to the workflow's `${{ github.token }}` and the default model is free, so no secrets are required.

> **Note:** PRs opened by other workflows running with the default `GITHUB_TOKEN` (e.g. nightwatch) do **not** trigger `pull_request` workflows — GitHub deliberately doesn't chain workflows off that token. To have warden review nightwatch's PRs automatically, give nightwatch a PAT as its `github-token`; otherwise review them manually via `workflow_dispatch`.

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `github-token` | `${{ github.token }}` | Token used to read the PR/diff and post inline comments. |
| `opencode-api-key` | `""` | OpenCode Zen API key, only if the model requires auth. |
| `model` | `opencode/mimo-v2.5-free` | opencode model id (`provider/model`). |
| `variant` | `high` | Reasoning effort (`high`/`max`/`minimal`); empty disables. |
| `plan` | `true` | Orient (read-only) before reviewing. `false` = single pass. |
| `review-file` | `REVIEW.md` | Path to the maintainer review-guidance file. |
| `review-focus` | `""` | Extra emphasis appended to the defaults when no review-file is present. |
| `max-comments` | `25` | Maximum inline comments posted per run. |
| `feedback-pr-limit` | `20` | Recent PRs scanned for past suggestions that drew pushback. |

## Requirements

- Check out the repo **with `fetch-depth: 0`** before this action (it diffs commit ranges and reads `REVIEW.md`).
- **Permissions:** the job needs `contents: read` and `pull-requests: write`.
- **`OPENCODE_API_KEY`** *(optional)* — set it if your chosen model needs auth.

## License

MIT — see [../LICENSE](../LICENSE).
