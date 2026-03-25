---
name: validate-pr-review-app
description: |
  Use this skill when working with validate-pr-review-app, a self-hosted GitHub App that validates Pull Request reviews to ensure PRs cannot be merged without proper approvals.
  Use this skill when the user wants to:
  - Update the configuration of validate-pr-review-app (e.g. make an app trusted, add untrusted_machine_users, change approval requirements)
  - Understand why a PR requires two approvals or how to avoid the two-approval requirement
  - Troubleshoot PR merge failures related to approval validation
  Even if the user doesn't mention "validate-pr-review-app" by name — if they ask about PR approval requirements, trusted apps, or merge validation, this skill applies.

---

- [How It Works](references/how-it-works.md)
- [Validation Rules](references/validation-rules.md)
- [Merge Queue Support](references/merge-queue.md)
- [Environment Variables](references/env.md)
- [Config](references/config.md)
- [Secrets](references/secret.md)
- [How To Avoid 2 Approvals](references/how-to-avoid-2-approvals.md)
- [Why are 2 approvals required for a pull request?](references/why-2-approvals-required.md)
