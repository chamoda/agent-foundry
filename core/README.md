# foundry-core

Shared core library for the [agent-foundry](https://github.com/chamoda/agent-foundry) agents. Everything the individual agents have in common lives here.

## Modules

- **config** — Environment-variable configuration helpers (`env`, `env_bool`, `env_int`, `env_float`).
- **shell** — Logging (`log`) and subprocess helpers (`run`, `working_tree_dirty`).
- **opencode** — The opencode driver: runs prompts non-interactively, optionally plan-first.
- **gh** — Small GitHub utilities (`ensure_label`, `references_issue`).
- **artifact** — Reads JSON artifacts written by an opencode build pass.
