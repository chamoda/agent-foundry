# 🔮 lucid

> A continuous AI agent that **triages every new issue the moment it's filed**. It researches the issue against the actual codebase and your `VISION.md`, scores it **1–10** with **ICE** or **RICE**, posts a compact comment showing the math, and labels the issue `ice-7` / `rice-4`. **Powered by [opencode](https://opencode.ai).** Part of [agent-foundry](../README.md).

lucid completes the loop with [**daydream**](../daydream/README.md) (which files new issues) and [**nightwatch**](../nightwatch/README.md) (which turns issues into PRs): daydream surfaces work, **lucid tells you what it's worth**, nightwatch does it.

## What it does

When an issue is opened (or on manual dispatch):

1. **Reads the issue** — title, body, and any discussion.
2. **Reads `VISION.md`** at your repo root (if present) to judge how well the issue aligns with your long-term direction.
3. **Researches the codebase in depth** — which files and subsystems the issue touches, implementation complexity, blast radius, and the value delivered. Every scoring factor is grounded in real findings, not generic heuristics.
4. **Posts a compact score comment** — the final **1–10 score**, the factor values, the calculation in one line, and per-factor reasoning folded into a collapsible section.
5. **Labels the issue** `ice-<score>` / `rice-<score>` (e.g. `ice-7`), color-coded red/yellow/green by band, replacing any stale score label on re-runs — so you can sort and filter the issue list by priority.

The agent proposes the factor values; the action validates them and computes the final score itself, so the arithmetic in the comment is always consistent.

## Scoring methods

Both methods produce an **integer score from 1 to 10** (higher = prioritize).

**ICE** (default) — quick and simple. Each factor is 1–10:

> score = ∛(Impact × Confidence × Ease) — the geometric mean of the factors, rounded.

**RICE** — more rigorous, effort-aware:

> raw = (Reach × Impact × Confidence) ÷ Effort, then score = log₂(raw + 1), clamped to 1–10.

where Reach is how many users/contributors are affected per quarter, Impact is the effect per person reached (0.25–3), Confidence is 0–1, and Effort is in person-months. Raw RICE is unbounded, so the log scale means each +1 of score ≈ double the value per unit of effort.

Pick with the `method` input (`ice` / `rice`).

## Usage

Add a workflow (see [`examples/lucid-agent.yaml`](../examples/lucid-agent.yaml)):

```yaml
name: lucid-agent
on:
  issues:
    types: [opened]
  workflow_dispatch:
    inputs:
      issue:
        description: "Issue number to score"
        required: true
        type: string

permissions:
  contents: read
  issues: write

jobs:
  lucid:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: chamoda/agent-foundry/lucid@v1
```

That's the whole setup — `github-token` defaults to the workflow's `${{ github.token }}` and the default model is free, so no secrets are required. Set `method: rice` under `with:` to use RICE instead of ICE.

> **Note:** issues created by other workflows running with the default `GITHUB_TOKEN` (e.g. daydream) do **not** trigger `issues: opened` workflows — GitHub deliberately doesn't chain workflows off that token. To have lucid score daydream's issues automatically, give daydream a PAT as its `github-token`; otherwise score them manually via `workflow_dispatch`.

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `github-token` | `${{ github.token }}` | Token used to read the issue and post the comment. |
| `opencode-api-key` | `""` | OpenCode Zen API key, only if the model requires auth. |
| `model` | `opencode/mimo-v2.5-free` | opencode model id (`provider/model`). |
| `variant` | `high` | Reasoning effort (`high`/`max`/`minimal`); empty disables. |
| `plan` | `true` | Research (read-only) before scoring. `false` = single pass. |
| `method` | `ice` | Scoring method: `ice` or `rice`. |
| `vision-file` | `VISION.md` | Path to the maintainer vision file, used to judge impact/alignment. |

## Requirements

- Checkout the repo before this action (it reads code + `VISION.md`).
- **Permissions:** the job needs `contents: read` and `issues: write`.
- **`OPENCODE_API_KEY`** *(optional)* — set it if your chosen model needs auth.

## Example comment

> ### 🔮 ICE score: **7/10**
>
> Impact 7 · Confidence 8 · Ease 6
> <sub>Score = geometric mean of the 1–10 factors: ∛(7 × 8 × 6) = ∛336 ≈ 7.0 → **7**. Higher = prioritize.</sub>
>
> Fixes a data-loss path hit by every offline user; strongly aligned with the sync-reliability goal in VISION.md.
>
> <details><summary>Factor reasoning</summary>
>
> - **Impact** — Fixes a data-loss path in `app/sync.py` hit by every offline user.
> - **Confidence** — The failing code path is clearly identifiable; fix is well-understood.
> - **Ease** — Contained to one module, but needs a migration and new tests.
>
> </details>

…and the issue gets an `ice-7` label.

## License

MIT — see [LICENSE](../LICENSE).
