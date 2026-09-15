# Organization setup

Read this when configuring the organization, or when auditing whether it is configured correctly.

## Protecting the `auto-approve` branch

Each repository keeps its approving reusable workflow on a branch named `auto-approve`. Leaving that
protection to each repository's own ruleset makes it impossible to govern, so it is applied centrally
with two Organization Rulesets.

### Ruleset 1

- Ruleset Name: `auto_approve`
- Bypass list: empty
- Target repositories: All repositories
- Target branches: `auto-approve`
- `Restrict deletions`
- `Require signed commits`
- `Require a pull request before merging`
  - `Dismiss stale pull request approvals when new commits are pushed`
  - `Require review from Code Owners`
  - `Require approval of the most recent reviewable push`
- `Require status checks to pass`
  - One check, named anything (`status-check` for example). Add a job that tests the reusable
    workflow.
- `Block force pushes`

CODEOWNERS is read from the base branch of the pull request, so the CODEOWNERS that governs the
`auto-approve` branch has to live on the `auto-approve` branch itself. Alternatively, use
`Require review from specific teams` in the Organization Ruleset and set the reviewing team
uniformly for the whole organization.

### Ruleset 2

- Ruleset Name: `forbid_create_auto_approve_branch`
- Bypass list: Organization admin
- Target repositories: All repositories
- Target branches: `auto-approve`
- `Restrict creations`

### Why two rulesets

`Require a pull request before merging` in ruleset 1 does not apply to the push that *creates* a
branch. That has an upside — the `auto-approve` branch can still be created while ruleset 1 is
active — and a serious downside: whoever creates the branch can put a workflow that abuses the PAT
in that first push, unreviewed.

So branch creation is restricted to organization admins. It is a separate ruleset because organization
admins must not be allowed to bypass ruleset 1 itself.

### The required status check

Require exactly one fixed job. To require several jobs, collapse them into one status check job
first — see the `github-required-status-check` skill, or
https://zenn.dev/shunsuke_suzuki/articles/how-to-manage-github-actions-required-status-check

## The shared action and reusable workflow repository

Put everything reusable in its own repository:

- Common approval checks, such as "approve if only these files changed".
- Fetching the PAT from AWS Secrets Manager.
- Approving. Call the API directly rather than `gh pr review -a`, because the review's `commit_id`
  has to be pinned.

Keep the deciding action and the approving action separate. The decision is then testable on its
own, and a third party action used in the decision never receives the PAT.

When the IAM role allows a shared reusable workflow by `job_workflow_ref`, restrict the file names,
for example to `auto_approve_*.yaml`. This repository will also hold workflows unrelated to auto
approve, and without that restriction those workflows could assume the role too.

Protect this repository's branch with an Organization Ruleset as well.

## Why this layout

### Why each repository's approving workflow lives in that repository

A workflow implementing repository specific logic stays in its own repository, with a security team
review made mandatory. Collecting them all into one dedicated repository does not scale once there
are many of them, and becomes awkward to manage.

Only genuinely reusable code goes in the shared repository.

### Why a dedicated `auto-approve` branch

- It can be protected by an Organization Ruleset uniformly, without depending on each repository's
  own branch conventions.
- A fixed branch name is convenient for the OIDC restriction.

Compared with keeping the workflow on the default branch, the downsides are:

- The auto approve workflow cannot be changed in the same pull request as a default branch change.
- It is easy to forget the corresponding `auto-approve` side change when modifying the default
  branch.

If the whole organization uses one default branch name and one branch flow, the default branch is a
reasonable choice too. At a certain size that tends not to hold.
