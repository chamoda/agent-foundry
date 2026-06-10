# 🛠️ agent-foundry

> A monorepo of continuous AI agents for your GitHub repos, **powered by [opencode](https://opencode.ai)**. Each agent ships as a GitHub Action; they share a common core.

| Agent | What it does | Use it as |
|-------|--------------|-----------|
| 🌙&nbsp;[**nightwatch**](nightwatch/) | Picks up open issues and proposes solutions as pull requests, then revises them when reviewers request changes. | `chamoda/agent-foundry/nightwatch@v1` |
| 💭&nbsp;[**daydream**](daydream/) | Researches the codebase and your `VISION.md`, then files thoughtful, well-researched new issues. | `chamoda/agent-foundry/daydream@v1` |
| 🔮&nbsp;[**lucid**](lucid/) | Triages each newly opened issue: researches it in depth, posts a 1–10 ICE/RICE priority score as a comment, and labels it `ice-7`. | `chamoda/agent-foundry/lucid@v1` |

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
```

No secrets needed: `github-token` defaults to the workflow's `${{ github.token }}` and the default model is the free OpenCode Zen `opencode/mimo-v2.5-free`. Add `opencode-api-key` only if you switch to a model that needs auth.

See each agent's README ([nightwatch](nightwatch/README.md), [daydream](daydream/README.md), [lucid](lucid/README.md)) for inputs, required permissions, and details.

## Development

Repo layout, local development, and the release process are documented in
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
