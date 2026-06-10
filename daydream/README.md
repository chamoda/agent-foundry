# 💭 daydream

> A continuous AI agent that **daydreams up new work** for your repo. It researches the codebase and your `VISION.md`, then files thoughtful, well-researched GitHub issues. **Powered by [opencode](https://opencode.ai).** Part of [agent-foundry](../README.md).

daydream is the day-shift companion to [**nightwatch**](../nightwatch/README.md) (which turns issues into PRs). Together they keep your project's momentum going: daydream surfaces *what* to do, nightwatch *does* it.

## What it does

Each run:

1. **Reads existing issues** (open + recently closed) so it understands what already exists and never files duplicates.
2. **Reads `VISION.md`** at your repo root — your maintainer's long-term vision. It prefers an idea from there that hasn't been turned into an issue yet, and **researches it in depth** before filing.
3. **Falls back to a balanced split** when `VISION.md` is absent or fully explored: roughly half **new ideas**, half **maintenance / project-health** issues (tests, refactors, dependency upgrades, docs, CI, performance, security, tech debt). The ratio is configurable (`idea-ratio`, default `0.5`) and self-balances over time using label counts.

Internally, opencode runs in two phases — a read-only `plan` agent researches and decides, then a `build` agent writes a structured issue, which the action turns into a real GitHub issue labeled by category.

## The VISION.md file

`VISION.md` is a free-form file at your repo root where maintainers jot down long-term vision and directions. There's no required format — bullet points work great:

```markdown
# Vision

- A public read-only API for quotations
- Dark mode for the dashboard
- Export invoices to the local tax authority's e-invoice format
```

daydream picks an unexplored entry, researches how it'd fit *this* codebase, and files a fleshed-out issue (problem, approach, affected files, acceptance criteria). Once every idea has a matching issue, it switches to the idea/maintenance fallback.

## Usage

Add a workflow (see [`examples/daydream-agent.yaml`](../examples/daydream-agent.yaml)):

```yaml
name: daydream-agent
on:
  schedule:
    - cron: "0 12 * * *" # daily at noon UTC
  workflow_dispatch:

permissions:
  contents: read
  issues: write

jobs:
  daydream:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: chamoda/agent-foundry/daydream@v1
```

That's the whole setup — `github-token` defaults to the workflow's `${{ github.token }}` and the default model is free, so no secrets are required.

> **Note:** `schedule` only runs from the workflow on your **default branch**.

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `github-token` | `${{ github.token }}` | Token used to create issues. |
| `opencode-api-key` | `""` | OpenCode Zen API key, only if the model requires auth. |
| `model` | `opencode/mimo-v2.5-free` | opencode model id (`provider/model`). |
| `variant` | `high` | Reasoning effort (`high`/`max`/`minimal`); empty disables. |
| `plan` | `true` | Research (read-only) before writing. `false` = single pass. |
| `max-issues` | `1` | Max issues to open per run. |
| `idea-ratio` | `0.5` | Target fraction of new-idea vs maintenance issues once `VISION.md` is exhausted. |
| `vision-file` | `VISION.md` | Path to the maintainer vision file. |
| `idea-label` | `daydream-idea` | Label for new-idea issues. |
| `maintenance-label` | `daydream-maintenance` | Label for maintenance issues. |
| `base-label` | `daydream` | Label applied to every issue it files. |

## Requirements

- Checkout the repo before this action (it reads code + `VISION.md`).
- **Permissions:** the job needs `contents: read` and `issues: write`.
- **`OPENCODE_API_KEY`** *(optional)* — set it if your chosen model needs auth.

## License

MIT — see [LICENSE](../LICENSE).
