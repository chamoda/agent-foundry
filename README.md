# 🛠️ agent-foundry

> A monorepo of continuous AI agents for your GitHub repos, **powered by [opencode](https://opencode.ai)**. Each agent ships as a GitHub Action.

| Agent | What it does | Use it as |
|-------|--------------|-----------|
| 💭&nbsp;[**daydream**](daydream/) | Researches the codebase and your `VISION.md`, then files thoughtful, well-researched new issues. | `chamoda/agent-foundry/daydream@v1` |
| 🔮&nbsp;[**lucid**](lucid/) ⚠️&nbsp;_deprecated_ | Triages each newly opened issue: researches it in depth, posts a 1–10 ICE/RICE priority score as a comment, and labels it `ice-7`. _No longer maintained; may be removed in `v2`._ | `chamoda/agent-foundry/lucid@v1` |
| 🌙&nbsp;[**nightwatch**](nightwatch/) | Picks up open issues and proposes solutions as pull requests, then revises them when reviewers request changes. | `chamoda/agent-foundry/nightwatch@v1` |
| 🛡️&nbsp;[**warden**](warden/) | Reviews each pull request fast and posts inline comments — biased toward security and matching your existing patterns, re-reviewing only new commits on each push. | `chamoda/agent-foundry/warden@v1` |

Together they keep a project's momentum going: daydream surfaces *what* to do, lucid says *what it's worth*, nightwatch *does* it, and warden *reviews* it.

## Quick start

Copy a workflow from [`examples/`](examples/) into `.github/workflows/` of your repo. Minimal daydream setup:

```yaml
jobs:
  daydream:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: chamoda/agent-foundry/daydream@v1
```

No secrets needed: `github-token` defaults to the workflow's `${{ github.token }}` and the default model is the free OpenCode Zen `opencode/mimo-v2.5-free`. Add `opencode-api-key` only if you switch to a model that needs auth.

See each agent's README ([nightwatch](nightwatch/README.md), [daydream](daydream/README.md), [lucid](lucid/README.md), [warden](warden/README.md)) for inputs, required permissions, and details.

## Security

These agents run an LLM with shell access on inputs the public can write
(issues, reviews). Read [SECURITY.md](SECURITY.md) — especially before
enabling them on a public repo.

## Development

Repo layout, local development, and the release process are documented in
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
