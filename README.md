# 🛠️ agent-foundry

> A monorepo of continuous AI agents for your GitHub repos, **powered by [opencode](https://opencode.ai)**. Each agent ships as a GitHub Action; they share a common core.

| Agent | What it does | Use it as |
|-------|--------------|-----------|
| 🌙 [**nightwatch**](nightwatch/) | Picks up open issues and proposes solutions as pull requests, then revises them when reviewers request changes. | `chamoda/agent-foundry/nightwatch@v1` |
| 💭 [**daydream**](daydream/) | Researches the codebase and your `VISION.md`, then files thoughtful, well-researched new issues. | `chamoda/agent-foundry/daydream@v1` |
| 🔮 [**lucid**](lucid/) | Triages each newly opened issue: researches it in depth and posts an ICE/RICE priority score as a comment. | `chamoda/agent-foundry/lucid@v1` |

Together they keep a project's momentum going: daydream surfaces *what* to do, lucid says *what it's worth*, nightwatch *does* it.

## Quick start

Copy a workflow from [`examples/`](examples/) into `.github/workflows/` of your repo. Minimal daydream setup:

```yaml
jobs:
  daydream:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: chamoda/agent-foundry/daydream@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          opencode-api-key: ${{ secrets.OPENCODE_API_KEY }}
```

See each agent's README ([nightwatch](nightwatch/README.md), [daydream](daydream/README.md)) for inputs, required permissions, and details.

## Repo layout

A [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with one shared lockfile:

```
core/        foundry-core  — shared library (env config, shell helpers,
             the opencode driver, GitHub utilities, artifact parsing)
nightwatch/  action.yml + nightwatch-agent package (depends on foundry-core)
daydream/    action.yml + daydream-agent package  (depends on foundry-core)
lucid/       action.yml + lucid-agent package     (depends on foundry-core)
examples/    ready-to-copy consumer workflows
```

Each agent directory contains its `action.yml`, so consumers reference the
subdirectory: `uses: chamoda/agent-foundry/<agent>@v1`. At run time the action
executes `uv run --project "$GITHUB_ACTION_PATH" python -m <agent>` from the
consumer's checked-out repo; uv discovers the workspace root and resolves
`foundry-core` from the shared lockfile.

> **Note:** GitHub Marketplace only lists actions whose `action.yml` is at the
> repository root, so the agents in this monorepo are not Marketplace-listed.
> Referencing them by path (as above) works for every repo regardless.

## Migrating from the standalone actions

These agents previously lived in the standalone `chamoda/nightwatch-agent` and
`chamoda/daydream-agent` repos (their tags keep working). To migrate, change
the `uses:` line:

```diff
-      - uses: chamoda/nightwatch-agent@v1
+      - uses: chamoda/agent-foundry/nightwatch@v1
```

Changes from the standalone actions:

- **daydream:** the deprecated `IDEAS.md` fallback and `IDEAS_FILE` env var are
  gone. Name your vision file `VISION.md` (or set the `vision-file` input).

All other inputs and defaults are unchanged.

## Development

```bash
uv sync --all-packages   # set up the workspace venv
uv run python -m nightwatch   # needs GITHUB_REPOSITORY / GITHUB_TOKEN etc.
```

Adding a new agent: create `<agent>/` with an `action.yml`, a `pyproject.toml`
that depends on `foundry-core = { workspace = true }`, and a `src/<agent>/`
package; add the directory to `[tool.uv.workspace] members` in the root
`pyproject.toml`; run `uv lock`.

## Releasing (maintainers)

Versioning follows the standard GitHub Actions convention: **immutable
patch/minor tags** plus a **mutable major tag** consumers pin to. Tags are
repo-wide, so one release covers all agents.

- `v1.0.1` — a specific, **immutable** release. Never moved.
- `v1` — a **mutable** pointer force-moved to the newest `v1.x` on every
  release (this is how `actions/checkout@v4` works). Consumers pin `@v1`.

### Cut a release

1. Bump the version in each changed package's `pyproject.toml` and
   `src/<pkg>/__init__.py` (keep them in sync), then `uv lock`.
2. Commit and push to `main`.
3. Create the **immutable** tag:
   `gh release create v1.0.1 --target main --title v1.0.1 --notes "..."`.
4. **Move the major tag:** `git tag -f v1 v1.0.1 && git push -f origin v1`.

> ⚠️ Force-push only the moving major tag (`v1`). Never force-move a full
> version tag like `v1.0.1` — those are permanent.

Breaking changes → bump the major (`v2`) and start a new `v2` tag, leaving `v1`
untouched.

## License

MIT — see [LICENSE](LICENSE).
