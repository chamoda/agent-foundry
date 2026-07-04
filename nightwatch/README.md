# 🌙 nightwatch

> A continuous AI agent that keeps watch over your repo — it picks up open issues and proposes solutions as pull requests, then revises them when you request changes. **Powered by [opencode](https://opencode.ai).** Part of [agent-foundry](../README.md).

nightwatch is built to **keep your project moving forward**. On a schedule (e.g. nightly), it grabs an open issue, plans a fix, and opens a PR for you to review in the morning. It learns from history: previously **rejected** PRs and their review feedback are fed back in so it doesn't repeat mistakes.

Its companion, [**daydream**](../daydream/README.md), does the opposite shift — it researches the codebase and files *new* issues.

## What it does

- **Scheduled / manual run** → picks the highest-scored open issue (by `ice-N`/`rice-N` labels from lucid, falling back to oldest-first) and opens a pull request that `Closes #<n>`.
- **Reviewer requests changes** → automatically revises the PR branch to address the feedback and asks for re-review.
- **Two-phase, high reasoning** → a read-only `plan` agent drafts an implementation plan, then a `build` agent executes it in the same session.
- **Learns from rejections** → closed-unmerged PRs for the same issue (and their review comments) are included as "do not repeat these mistakes" context. After `max-attempts` rejections it leaves an issue alone.

## Usage

Add a workflow to your repo (see [`examples/nightwatch-agent.yaml`](../examples/nightwatch-agent.yaml)):

```yaml
name: nightwatch-agent
on:
  schedule:
    - cron: "0 0 * * *" # daily at midnight UTC
  workflow_dispatch:
    inputs:
      issue:
        description: "Issue number (blank = auto-pick oldest)"
        required: false
        type: string
  pull_request_review:
    types: [submitted]

concurrency:
  group: nightwatch-agent
  cancel-in-progress: false

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  nightwatch:
    runs-on: ubuntu-24.04
    if: >
      github.event_name == 'schedule' ||
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'pull_request_review' &&
       github.event.review.state == 'changes_requested' &&
       startsWith(github.event.pull_request.head.ref, 'nightwatch/'))
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: chamoda/agent-foundry/nightwatch@v1
```

That's the whole setup — `github-token` defaults to the workflow's `${{ github.token }}` and the default model is free, so no secrets are required. To get CI runs on the agent's PRs, pass a PAT instead (see the PAT note below):

```yaml
      - uses: chamoda/agent-foundry/nightwatch@v1
        with:
          github-token: ${{ secrets.NIGHTWATCH_GH_PAT }}
```

> **Note:** `schedule` only runs from the workflow on your **default branch**, so this must be merged to `main` to start firing.

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `github-token` | `${{ github.token }}` | Token for the issues/PR API. See the PAT note below. |
| `opencode-api-key` | `""` | OpenCode Zen API key, only if the model requires auth. |
| `model` | `opencode/mimo-v2.5-free` | opencode model id (`provider/model`). |
| `variant` | `high` | Reasoning effort (`high`/`max`/`minimal`); empty disables. |
| `plan` | `true` | Plan (read-only) before building. `false` = single build pass. |
| `max-attempts` | `3` | Stop retrying an issue after this many rejected PRs. |
| `branch-prefix` | `nightwatch/issue-` | Prefix for branches the agent pushes. |
| `bot-name` | `nightwatch-agent` | Git commit author name. |
| `bot-email` | `nightwatch-agent[bot]@users.noreply.github.com` | Git commit author email. |
| `prefer-scored` | `true` | Prefer issues with higher lucid scores (`ice-N`/`rice-N` labels) over oldest-first. |

## Requirements & secrets

- **Checkout with `fetch-depth: 0`** before this action so it can fetch/switch PR branches.
- **Permissions:** the job needs `contents: write`, `pull-requests: write`, `issues: write`.
- **Allow Actions to create PRs:** in the repo (or org) **Settings → Actions → General → Workflow permissions**, enable **"Allow GitHub Actions to create and approve pull requests"**. Without it, opening a PR fails with `403: GitHub Actions is not permitted to create or approve pull requests`. This is separate from the `pull-requests: write` permission above — you need both. For organizations, the org-level toggle can override the per-repo one, so enable it there too. *(Not required if you use a `NIGHTWATCH_GH_PAT` — a PAT bypasses this policy.)*
- **`OPENCODE_API_KEY`** *(optional)* — set it if your chosen model needs auth.
- **`NIGHTWATCH_GH_PAT`** *(optional)* — the default `GITHUB_TOKEN` cannot trigger other workflows, so PRs it opens **won't run your CI**. Provide a PAT to get CI on the agent's PRs.

## How model auth works

The default model is the free OpenCode Zen model `opencode/mimo-v2.5-free`. If a run fails with an auth error, create a key at [opencode.ai](https://opencode.ai) and set it as the `OPENCODE_API_KEY` secret — opencode picks it up automatically.

## License

MIT — see [LICENSE](../LICENSE).
