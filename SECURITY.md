# Security

The agents in this repo run an LLM coding agent ([opencode](https://opencode.ai))
**with shell access** on a GitHub Actions runner, fed in part by
**untrusted input** (issue text, issue comments, PR review comments — anything
the public can write on a public repo). Understand this threat model before
enabling them, especially on a public repository.

## Threat model

### 1. Prompt injection → arbitrary code on the runner

opencode runs with `bash` and `webfetch` allowed. Text written by outsiders
flows into its prompts:

| Agent | Untrusted input | Exposure |
|-------|-----------------|----------|
| 🔮 lucid | The issue being scored (body, comments) | **Direct** — auto-triggers on `issues: opened`, so an attacker's text reaches the model unreviewed. |
| 🌙 nightwatch | The issue being worked; review comments on its PRs | **Direct** — it picks the oldest open issue as its work queue, and anyone can submit a "changes requested" review on a public PR. |
| 💭 daydream | Existing issue titles/bodies (duplicate-avoidance context) | Indirect. |

A successful injection means the attacker chooses what runs in the job. The
blast radius is whatever the job can reach — which is what the rest of this
document is about.

### 2. Secret exfiltration

The job environment contains `OPENCODE_API_KEY` if you configured one, and
`GITHUB_TOKEN`. An injected model can read the environment and send it
anywhere (bash + webfetch).

- **Mitigation:** on public repos, prefer the free default model and do not
  set `OPENCODE_API_KEY`. Then there is nothing valuable to steal:
  `GITHUB_TOKEN` is job-scoped, expires when the run ends, and for
  lucid/daydream it can only read a public repo and write issues.

### 3. `contents: write` abuse (nightwatch)

nightwatch's job needs `contents: write` to push PR branches, and
`actions/checkout` persists the token in `.git/config`. An injected model
could `git push` to `main` or move release tags directly, bypassing the
script.

- **Mitigations:** branch protection on `main` (require PRs); a repository
  ruleset protecting release tags (`v*`). Note that `GITHUB_TOKEN` cannot
  modify `.github/workflows/` (it lacks the `workflows` scope), which closes
  the worst self-modification loop. nightwatch detects this specific push
  rejection and exits cleanly with a comment rather than failing, so the
  boundary holds without manual cleanup.

  **Overriding the boundary (don't, on public repos):** granting
  `workflows: write` in the agent's `permissions:` block, or passing a PAT with
  the `workflow` scope as `github-token`, lets the agent push workflow files —
  reopening exactly this self-modification loop. Only do this on private repos
  or otherwise trusted setups; on a public repo an injected or steered agent
  could then rewrite CI to run arbitrary code with your secrets.

### 4. Reviewed-but-malicious output (the social attack)

Even with zero injection, the *intended* output of these agents is
attacker-steerable: a plausible-sounding issue can lead nightwatch to generate
a plausible-looking PR containing a subtle backdoor. The maintainer review of
the agent's PRs is the only gate.

- This matters most for repos that are **themselves dependencies of others**
  (like this one — it's an action consumed by other repos, so a bad merge
  here plus a moved major tag ships to every consumer). Review agent PRs with
  the same suspicion you'd give a PR from an unknown contributor, because via
  the issue text, it may effectively be one.

### 5. Resource burn

Every opened issue triggers a lucid run; spam issues burn runner minutes (free
but capped on public repos) and model credits (zero with the free model).

## Recommended hardening for public repos

1. **No `OPENCODE_API_KEY` secret** — use the free default model.
2. **Gate auto-triggered runs by author association**, with manual dispatch as
   the override for outsider content you've read first:

   ```yaml
   jobs:
     lucid:
       if: >
         github.event_name == 'workflow_dispatch' ||
         contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'),
                  github.event.issue.author_association)
   ```

   For nightwatch's review trigger, gate on
   `github.event.review.author_association` the same way.
3. **Branch protection on `main`** and a ruleset protecting `v*` tags.
4. **`persist-credentials: false`** on the checkout step for daydream and
   lucid — they never push, so the token has no business in `.git/config`.
5. Keep `concurrency` groups on the workflows (the examples include them where
   it matters) so runs don't pile up.

On a **private repo** with trusted collaborators, the untrusted-input surface
mostly disappears and the defaults are reasonable as-is.

## Reporting a vulnerability

Open a [security advisory](https://github.com/chamoda/agent-foundry/security/advisories/new)
or email the maintainer. Please do not file exploitable details as a public
issue — not least because the agents read the issues.
