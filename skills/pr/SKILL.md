---
name: pr
description: Creates a branch, commits the changes, and opens a pull request whose description summarizes the full diff between base and head. Use when the user asks to create a pull request, open a PR, or submit changes for review.
---

# Pull request creation

## Workflow

1. Create a branch from the base branch. Never commit directly to the default branch.
2. Stage and commit the changes.
3. Open the PR with `gh pr create`.

## PR description

- Compose the description from the **full diff between the PR's base and head**, not from individual commit messages or the original instructions alone.
- Write the full context of the current plan so a reviewer can understand the change without extra explanation.
