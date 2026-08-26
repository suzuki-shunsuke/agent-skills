---
name: merge-pull-request-workflow
description: Rewrites a repository's GitHub Actions workflows so that each pull_request workflow exposes exactly one required status check job, by merging pull_request workflows together and moving their jobs into wc_*.yaml reusable workflows. Use when asked to consolidate pull_request workflows, add a status-check job, or make GitHub required status checks easier and safer to manage.
---

# Merge pull_request workflows behind a single status check job

Rewrite a repository's workflows so that `Require status checks to pass` needs at most one
check name per `pull_request` workflow, and never has to be updated when a job is added,
removed, or renamed.

Background article (Japanese):
https://zenn.dev/shunsuke_suzuki/articles/how-to-manage-github-actions-required-status-check

## Rules

- Register exactly one job per `pull_request` workflow as a required status check (the
  "status check job"). Never register individual jobs.
- Give the status check job a **different name in every `pull_request` workflow**. Sharing one
  name lets a PR be merged while that job has not started yet in one of the workflows.
  - If a job that already acts as the status check exists under another name and is already
    registered as a required check, keep that name. Do not rename it just to match a convention —
    renaming it forces a branch ruleset update for no benefit.
- Merge `pull_request` workflows into as few workflows as possible. To keep files split, use
  reusable workflows (`on: workflow_call`), not extra `pull_request` workflows.
  - Exception: keep the actionlint workflow independent, so a broken workflow file does not stop
    actionlint from running. But if the actionlint job is **already merged** into the main
    `pull_request` workflow, leave it there — do not split it out.
- Keep only 1 or 2 jobs in a `pull_request` workflow file: the job that calls the reusable
  workflow, and the status check job. Move anything else into the reusable workflow.
- Replace workflow path filters (`on.pull_request.paths` / `paths-ignore`) with job level
  filtering via [dorny/paths-filter](https://github.com/dorny/paths-filter). A skipped workflow
  never reports its required check, so the PR can never be merged.
- A job whose failure should be ignored gets `continue-on-error: true` instead of being left out
  of the status check.

## Naming

- When converting a workflow into a reusable workflow, rename the file with a `wc_` prefix:
  `.github/workflows/test.yaml` → `.github/workflows/wc_test.yaml`.
- Workflow names must be unique. Omit `name:` when it would collide with the caller.

## Workflow

1. Read every file in `.github/workflows/`. For each workflow record: triggers, path filters,
   jobs, `permissions`, `secrets`, `concurrency`, `continue-on-error`.
2. Read the current required status checks of the default branch:

   ```sh
   gh api "repos/{owner}/{repo}/rules/branches/{branch}" \
     --jq '[.[] | select(.type == "required_status_checks")
            | {ruleset_id, checks: [.parameters.required_status_checks[].context]}]'
   ```

   If the repository uses a classic branch protection rule instead:

   ```sh
   gh api "repos/{owner}/{repo}/branches/{branch}/protection/required_status_checks"
   ```

3. Classify each `pull_request` workflow:
   - Covered by a required status check → merge target.
   - actionlint → leave independent (unless already merged, see Rules).
   - Not covered by any required status check, so it can fail without blocking a merge →
     **ask the user** (see Questions).
4. Show the user the plan: which workflows are merged into which, the new file names, the status
   check job names, and the resulting required check names. Get approval before editing.
5. Rewrite the workflows using the templates below.

## Questions

Ask the user about every `pull_request` workflow that is not covered by a required status check,
one workflow at a time:

1. Leave it as is, or merge it into the main `pull_request` workflow?
2. If merging: set `continue-on-error: true` on its jobs (keeping today's "failure does not block
   merge" behaviour), or let it block merges from now on?

Also ask before adding or removing `concurrency` with `cancel-in-progress: true`. It is not
required, and cancelling an in-progress run is harmful for some jobs, such as ones that deploy or
push commits.

## Branch ruleset warning

Merging workflows changes the set of check names that the repository produces. When required
status checks are configured per workflow:

- Tell the user explicitly that the branch ruleset (or branch protection rule) must be updated
  once the PR is merged: drop the check names that no longer exist and add the new status check
  job names.
- Write the same note in the PR description, listing the exact check names to remove and to add.
- Recommend updating the ruleset immediately after merging the PR. Between the merge and the
  ruleset update, other PRs are blocked by required checks that no workflow reports any more.

## Templates

Single job, no reusable workflow needed — just register `status-check`:

```yaml
---
name: test
on: pull_request
permissions: {}
# concurrency is optional. Add it only if the user wants runs cancelled.
concurrency:
  group: ${{ github.workflow }}--${{ github.ref }}
  cancel-in-progress: true
jobs:
  status-check:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions: {}
    steps:
      # ...
```

Multiple jobs — the `pull_request` workflow calls the reusable workflow:

```yaml
---
# .github/workflows/test.yaml
name: test
on: pull_request
permissions: {}
# concurrency is optional. Add it only if the user wants runs cancelled.
concurrency:
  group: ${{ github.workflow }}--${{ github.ref }}
  cancel-in-progress: true
jobs:
  # Don't add jobs to this file. Please add jobs to wc_test.yaml.
  test:
    uses: ./.github/workflows/wc_test.yaml
    permissions:
      contents: read
    # secrets:
    #   APP_ID: ${{secrets.APP_ID}}
  status-check:
    runs-on: ubuntu-24.04
    if: always() && (contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled'))
    timeout-minutes: 10
    permissions: {}
    needs:
      - test
    steps:
      - run: exit 1
  # Don't add jobs to this file. Please add jobs to wc_test.yaml.
```

```yaml
---
# .github/workflows/wc_test.yaml
name: test (workflow_call)
on: workflow_call
jobs:
  foo:
    # ...
  bar:
    # ...
```

`status-check` is skipped when `test` succeeds or is skipped, and fails when `test` fails or is
cancelled. A skipped required check counts as success, so the PR is mergeable exactly when the
reusable workflow succeeded.

## Gotchas

- Use `if: always() && (contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled'))`.
  `if: failure()` is wrong: a GitHub Actions bug can skip the job and let a failing PR be merged.
- A reusable workflow inherits nothing from the caller. Move the callee's `permissions` and
  `secrets` up to the calling job (`secrets: inherit` only when the callee needs many of them).
- `concurrency` is optional. When it is used, keep it in the `pull_request` workflow, not in the
  reusable workflow.
- Remove the `pull_request` trigger from a workflow you convert to `on: workflow_call`, otherwise
  its jobs run twice.
- Jobs called through a reusable workflow report as `<caller job> / <callee job>`. Do not put
  those names in the ruleset — only the status check job name.
- Anyone unaware of this layout may add a job to the `pull_request` workflow file, where its
  failure would not block merges. Keep the `Don't add jobs to this file.` comments.
