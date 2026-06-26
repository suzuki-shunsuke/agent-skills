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

Read the reference file that matches the task:

- [How It Works](references/how-it-works.md) — to understand the overall mechanism.
- [Validation Rules](references/validation-rules.md) — what the app validates and when a PR passes or fails.
- [Why are 2 approvals required for a pull request?](references/why-2-approvals-required.md) — to explain why a PR needs two approvals.
- [How To Avoid 2 Approvals](references/how-to-avoid-2-approvals.md) — to reduce a PR's approval requirement.
- [Config](references/config.md) — to change configuration (trusted_apps, untrusted_machine_users, approval/unsigned-commit rules).
- [Customize footer](references/customize-footer.md) — to customize the footer shown on the Checks tab.
- [Environment Variables](references/env.md) — to configure how the app runs.
- [Secrets](references/secret.md) — to set up the app's secrets.
- [Merge Queue Support](references/merge-queue.md) — when the repository uses a merge queue.
