# Vision

Long-term directions for agent-foundry. daydream reads this file and turns
unexplored entries into researched issues.

> **Constraint:** Do not propose work that requires editing files under
> `.github/workflows/`. nightwatch's `GITHUB_TOKEN` deliberately lacks the
> `workflows` permission, so it cannot push such changes — see threat #3 in
> [SECURITY.md](SECURITY.md). Any direction here must be implementable without
> touching workflow files (e.g. via `core/`, agent packages, or composite
> actions the workflows merely reference).

- **Pluggable harnesses.** Run the agents on coding agents other than opencode
  (e.g. Claude Code) behind a small `Harness` protocol in `foundry-core`,
  selected via a `harness` action input. opencode stays the default; adding a
  harness should be purely additive (one new module in `core/`, a conditional
  install step in the actions).
- **A real test suite.** Unit tests for `foundry-core` (env parsing, artifact
  parsing, opencode driver) and each agent's pure logic (issue selection,
  scoring, comment rendering), plus a CI workflow running ruff, pyright, and
  the tests on every PR — so agent-generated PRs get checked automatically.
- **Shared setup step.** A composite "setup" action used by all agent
  action.yml files so the uv/opencode install steps aren't duplicated.
- **Scoring-aware nightwatch.** When picking the next issue to work, prefer
  higher lucid scores (`ice-N`/`rice-N` labels) over plain oldest-first.
