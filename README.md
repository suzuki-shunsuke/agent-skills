# agent-skills
My Agent Skills.

## Skills

| Skill | What it does |
| --- | --- |
| [create-skill](skills/create-skill) | Turns an OSS project's documentation into skills, so the documentation and the skills share one body instead of being maintained twice. |
| [github-app-private-key-aws-kms](skills/github-app-private-key-aws-kms) | Delegates GitHub App JWT signing to AWS KMS, so the private key never sits in GitHub Secrets. |
| [github-auto-approve](skills/github-auto-approve) | Runs auto approve across an organization so that only pull requests genuinely meeting the intended condition get approved. |
| [github-required-status-check](skills/github-required-status-check) | Registers one status check per `pull_request` workflow, so the branch ruleset never needs editing when a job is added, removed, or renamed. |
| [go](skills/go) | Conventions and commands for Go projects: testing, linting, JSON Schema generation, error handling. |
| [manner](skills/manner) | Baseline rules: write in English, never commit to a default branch, never rewrite history. |
| [pr](skills/pr) | Creates a branch, commits, and opens a pull request whose description is written from the base...head diff. |
