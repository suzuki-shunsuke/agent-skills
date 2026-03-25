---
name: validate-pr-review-app
description: |
  A SKILL for https://github.com/suzuki-shunsuke/validate-pr-review-app.
  It is used when modifying the configuration file of validate-pr-review-app, as well as for answering questions and troubleshooting related to it.
  For example, it can help answer questions such as why this PR requires two approvals, or whether it is possible to configure it so that two approvals are not required.
---

- [How It Works](references/how-it-works.md)
- [Validation Rules](references/validation-rules.md)
- [Merge Queue Support](references/merge-queue.md)
- [Environment Variables](references/env.md)
- [Config](references/config.md)
- [Secrets](references/secret.md)
- [How To Avoid 2 Approvals](references/how-to-avoid-2-approvals.md)
- [Why are 2 approvals required for a pull request?](references/why-2-approvals-required.md)

## What's validate-pr-review-app?

Validate PR Review App is a self-hosted GitHub App that validates Pull Request reviews.
It helps organizations improve governance and security by ensuring PRs cannot be merged without proper approvals while keeping developer experience.
