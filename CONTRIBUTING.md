# Contributing to agent-foundry

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

> **Note:** GitHub Marketplace only lists actions whose `action.yml` is at the
> repository root, so the agents in this monorepo are not Marketplace-listed.
> Referencing them by path works for every repo regardless.
