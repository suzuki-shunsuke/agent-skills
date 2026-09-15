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

## The approving workflow

The shape of an approving reusable workflow — decide, fetch the PAT only if the decision passed,
then approve. Each comment records why a line is the way it is; keep them.

```yaml
---
name: auto-approve
on:
  workflow_call: {}
jobs:
  approve:
    runs-on: ubuntu-24.04
    permissions:
      contents: read # To resolve the action in this repository
      pull-requests: read # To list the updated files of the pull request
      id-token: write # To get an OIDC token to assume the AWS IAM role
    timeout-minutes: 10
    steps:
      # Check whether this pull request can be approved automatically.
      # $/ resolves to this repository at the commit which is running.
      # This workflow is called by a fixed ref, so the action is resolved by the same ref.
      # https://github.blog/changelog/2026-07-30-reference-same-repository-actions-with-self-repository-syntax/
      - uses: $/.github/actions/auto_approve
        id: check

      # Only this workflow gets the access token to approve pull requests.
      # The AWS IAM role restricts the access by job_workflow_ref, so the token isn't
      # available from workflows other than this one.
      - name: Get PAT from AWS Secrets Manager
        if: steps.check.outputs.ok == 'true'
        id: token
        uses: suzuki-shunsuke/aws-secrets-manager-get-action@364e6a3b804becfded0751ab2d3ec7d42f84521a # v0.2.0
        with:
          role_to_assume: arn:aws:iam::<account id>:role/github_auto_approve
          secrets: |
            - secret_id: arn:aws:secretsmanager:<region>:<account id>:secret:github-auto-approve-<suffix>
              values:
                - key: GITHUB_TOKEN
                  output_name: token

      # commit_id fixes the commit to approve.
      # Without it the review would be created against the head at this moment,
      # which can be a commit newer than the one the check validated.
      - name: Approve
        if: steps.check.outputs.ok == 'true'
        shell: bash
        run: |
          gh api "repos/$GITHUB_REPOSITORY/pulls/$PR_NUMBER/reviews" \
            -f event=APPROVE \
            -f commit_id="$HEAD_SHA" \
            -f body="$REVIEW_BODY"
        env:
          GH_TOKEN: ${{steps.token.outputs.token}}
          PR_NUMBER: ${{github.event.pull_request.number}}
          HEAD_SHA: ${{github.event.pull_request.head.sha}}
          REVIEW_BODY: This pull request updates only files under staging/, so it is approved automatically.
```

Working example:
https://github.com/szksh-lab-2/poc-enterprise-secure-auto-approve/blob/auto-approve/.github/workflows/auto_approve.yaml

### Fetching the PAT

[suzuki-shunsuke/aws-secrets-manager-get-action](https://github.com/suzuki-shunsuke/aws-secrets-manager-get-action)
assumes the IAM role with the GitHub OIDC token itself and keeps the AWS credentials inside the
action, so no later step of the job can read them. That matters here: the job already holds the PAT,
and exporting AWS credentials into it would give any subsequent step a second route to the secret.

- `secret_id` accepts an ARN, which carries the region, so `region` can be omitted.
- `values` reads individual keys out of a secret stored as a JSON object. Each one is published
  under its `output_name`, here `token`.
- An unknown field in the `secrets` input is an error rather than being ignored, so a typo cannot
  quietly read the wrong thing.

The alternative is `aws-actions/configure-aws-credentials` followed by the AWS CLI, which exports
the credentials as environment variables for the whole job.

### Notes on the example

- The PAT never reaches a `run` step's command line; it is passed through `env` as `GH_TOKEN`, and
  so are the pull request derived values. See
  [Hardening the approving workflow](workflow_hardening.md).
- Both the token step and the approve step are guarded by `steps.check.outputs.ok == 'true'`, so a
  pull request that fails the check never causes the PAT to be fetched at all.
- Replace the account id, region and secret suffix placeholders. Do not copy another organization's
  ARNs.

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
