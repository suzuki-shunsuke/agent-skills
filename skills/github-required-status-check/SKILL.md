---
name: github-required-status-check
description: Designs and manages GitHub Branch Rulesets' "Require status checks to pass" so the ruleset never needs updating when a job is added, removed, or renamed, by registering one status check job per pull_request workflow instead of every job. Also covers rewriting a repository's existing workflows into that layout - merging pull_request workflows and moving their jobs into wc_*.yaml reusable workflows. Use when setting up or auditing required status checks, branch rulesets, or branch protection, when deciding which checks to require, when consolidating pull_request workflows or adding a status-check job, or when a failing job did not block a merge.
---

# Manage GitHub required status checks

Source article (Japanese):
https://zenn.dev/shunsuke_suzuki/articles/how-to-manage-github-actions-required-status-check

## The problem

Registering every job in `Status checks that are required` means the branch ruleset has to be
edited every time a job is added, removed, or renamed. That is tedious, and a missed update is
a silent failure: a job fails and the PR is still mergeable.

## The design

Register exactly one check per `pull_request` workflow — a job that succeeds only when every
other job in that workflow succeeded. Call it the status check job. Adding, removing, or
renaming jobs then never touches the ruleset.

GitHub cannot require a *workflow*, only a *job*. So the trick is to move every job into a
reusable workflow (`on: workflow_call`), call it from one job in the `pull_request` workflow,
and add a status check job whose result depends on that call.

## Rules

- One required check per `pull_request` workflow. Never register individual jobs.
- Give the status check job a different name in every `pull_request` workflow. With a shared
  name a PR can be merged while that job has not started yet in one of the workflows. This
  applies even to a workflow with a single job — job startup can be delayed.
  - If a job already acting as the status check exists under another name and is already
    registered as a required check, keep that name. Renaming it only forces a ruleset update
    for no benefit.
- Keep `pull_request` workflows to as few files as possible. To split files, use reusable
  workflows, not extra `pull_request` workflows.
  - Exception: keep the actionlint workflow separate. If the other workflows break, actionlint
    must still run, so it should stay as simple and independent as possible. But if the
    actionlint job is *already* merged into the main `pull_request` workflow, leave it there —
    do not split it out.
- Keep only 1 or 2 jobs in a `pull_request` workflow file: the job calling the reusable
  workflow, and the status check job. Everything else goes in the reusable workflow.
- Never use workflow path filters (`on.pull_request.paths` / `paths-ignore`) on a workflow whose
  job is required. A skipped workflow reports nothing, so the required check never passes and
  the PR can never be merged. Filter at job level with
  [dorny/paths-filter](https://github.com/dorny/paths-filter) instead.
- A job whose failure should be ignored gets
  [`continue-on-error: true`](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions#jobsjob_idcontinue-on-error),
  so it does not fail the workflow. Do not leave it out of the status check instead.

## Naming

- Name a reusable workflow file with a `wc_` prefix: `.github/workflows/test.yaml` →
  `.github/workflows/wc_test.yaml`.
- Workflow names must be unique. Omit `name:` when it would collide with the caller.

## Setting it up

1. Move the jobs of the `pull_request` workflow into a new `on: workflow_call` workflow.
2. Call that reusable workflow from a single job in the `pull_request` workflow. Reusable
   workflows inherit nothing, so pass `permissions` and `secrets` explicitly at the call site.
3. Add the status check job to the `pull_request` workflow.
4. Enable `Require status checks to pass` and register only the status check job names.

## Rewriting an existing repository

1. Read every file in `.github/workflows/`. For each workflow record: triggers, path filters,
   jobs, `permissions`, `secrets`, `concurrency`, `continue-on-error`.
2. Read the current required status checks of the default branch (see
   [Inspecting the current configuration](#inspecting-the-current-configuration)).
3. Classify each `pull_request` workflow:
   - Covered by a required status check → merge target.
   - actionlint → leave independent (unless already merged, see Rules).
   - Not covered by any required status check, so it can fail without blocking a merge →
     ask the user (see Questions).
4. Show the user the plan: which workflows are merged into which, the new file names, the status
   check job names, and the resulting required check names. Get approval before editing.
5. Rewrite the workflows using the templates below.

### Questions

Ask the user about every `pull_request` workflow that is not covered by a required status check,
one workflow at a time:

1. Leave it as is, or merge it into the main `pull_request` workflow?
2. If merging: set `continue-on-error: true` on its jobs (keeping today's "failure does not block
   merge" behaviour), or let it block merges from now on?

Also ask before adding or removing `concurrency` with `cancel-in-progress: true`. It is not
required, and cancelling an in-progress run is harmful for some jobs, such as ones that deploy or
push commits.

### Branch ruleset warning

Merging workflows changes the set of check names the repository produces. When required status
checks are configured per workflow:

- Tell the user explicitly that the branch ruleset (or branch protection rule) must be updated
  once the PR is merged: drop the check names that no longer exist and add the new status check
  job names.
- Write the same note in the PR description, listing the exact check names to remove and to add.
- Recommend updating the ruleset immediately after merging the PR. Between the merge and the
  ruleset update, other PRs are blocked by required checks that no workflow reports any more.

## Templates

One job and no reusable workflow — register `status-check` directly:

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

## Why it works

A job ends as success, failure, skipped, or cancelled. A skipped required check
[counts as success](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks),
so `status-check` blocks the merge exactly when `test` did not pass:

| status of test | status of status-check | mergeable |
| --- | --- | --- |
| success | skipped | true |
| failure | failure | false |
| skipped | skipped | true |
| cancelled | cancelled | false |

## Gotchas

- Use `if: always() && (contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled'))`.
  `if: failure()` is wrong: a GitHub Actions bug can skip the job, letting a failing PR merge.
- A reusable workflow inherits nothing from the caller. Move the callee's `permissions` and
  `secrets` up to the calling job (`secrets: inherit` only when the callee needs many of them).
- `concurrency` is optional. When it is used, keep it in the `pull_request` workflow, not in the
  reusable workflow.
- Remove the `pull_request` trigger from a workflow converted to `on: workflow_call`, or its
  jobs run twice.
- Jobs reached through a reusable workflow report as `<caller job> / <callee job>`. Do not put
  those names in the ruleset — only the status check job name.
- Someone unaware of this layout may add a job to the `pull_request` workflow file, where its
  failure does not block merges. Keep the `Don't add jobs to this file.` comments. Validating it
  in CI is possible but fiddly.

## Inspecting the current configuration

```sh
gh api "repos/{owner}/{repo}/rules/branches/{branch}" \
  --jq '[.[] | select(.type == "required_status_checks")
         | {ruleset_id, checks: [.parameters.required_status_checks[].context]}]'
```

For a classic branch protection rule:

```sh
gh api "repos/{owner}/{repo}/branches/{branch}/protection/required_status_checks"
```
