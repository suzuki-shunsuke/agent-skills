---
name: github-trusted-tag
description: Makes tags in a GitHub organization creatable only on a trusted SHA (the HEAD of the default branch). Sets up a dedicated GitHub App and reusable workflow that push tags, and Organization Tag Rulesets that forbid anyone but that GitHub App from creating, updating, or deleting tags. The GitHub App private key lives in AWS KMS, guarded by an IAM role pinned on the job_workflow_ref sub claim. Use when preventing tags from being pushed to feature branches or other untrusted commits, when designing, rolling out, or reviewing tag rulesets or a tag-creating reusable workflow, or when the tag-creating workflow fails to assume its IAM role.
---

# Create tags only on trusted SHAs

## Background

- This assumes development within an organization. Personal projects are out of scope.
- On GitHub, anyone with push access can basically push any tag.
- Pushing a tag can trigger a release workflow.
- For some things the release is complete the moment the tag is pushed, without any release workflow:
  - GitHub Actions
  - Go modules
  - Terraform modules
  - etc.

## Goal

Tags can be created only on a trusted SHA — basically the HEAD of the default branch.

## How it works

1. Create a dedicated GitHub App for pushing tags, and a dedicated reusable workflow that pushes tags with it.
1. Forbid tag creation with an Organization Tag Ruleset, and add only the dedicated GitHub App to its bypass list.
1. Add a workflow to each repository that calls the reusable workflow to push tags.
1. Keep the private key in AWS KMS and guard it with AWS IAM, so the GitHub App cannot be abused or used for anything else.

## Trade-offs

- Developers can no longer create tags locally or from the GitHub web UI.
- A tag created by mistake can no longer be deleted.
- Existing tag-creating mechanisms stop working.
  - Inventory them (tagpr, release-please, goreleaser, `gh release create`, etc.) before rolling this out.
- Floating major tags such as `v1`, common in GitHub Actions repositories, can no longer be updated.

## Steps

1. [Protect the default branch with an Organization Branch Ruleset](#1-protect-the-default-branch-with-an-organization-branch-ruleset)
1. [Create a dedicated GitHub App for pushing tags](#2-create-a-dedicated-github-app-for-pushing-tags)
1. [Import the private key into AWS KMS and create the IAM role](#3-import-the-private-key-into-aws-kms-and-create-the-iam-role)
1. [Create the reusable workflow that pushes tags](#4-create-the-reusable-workflow-that-pushes-tags)
1. [Add job_workflow_ref to each repository's subject claim](#5-add-job_workflow_ref-to-each-repositorys-subject-claim)
1. [Add a workflow calling the reusable workflow to each repository](#6-add-a-workflow-calling-the-reusable-workflow-to-each-repository)
1. [Restrict tag creation and changes with Organization Tag Rulesets](#7-restrict-tag-creation-and-changes-with-organization-tag-rulesets)

### 1. Protect the default branch with an Organization Branch Ruleset

"Trusted SHA = HEAD of the default branch" holds only with this protection in place. Skip this step if the default branch is already protected.

- Bypass list: none
- Target repositories: All repositories
- Target branches: Default branch
- Rules
  - Restrict deletions
  - Require a pull request before merging
    - Required approvals: 1 or more
    - Dismiss stale pull request approvals when new commits are pushed
    - (optional) Require review from Code Owners
    - Require approval of the most recent reviewable push
  - Block force pushes

### 2. Create a dedicated GitHub App for pushing tags

- Repository access: All repositories
- Permissions: `contents:write`
- Webhook: disabled

### 3. Import the private key into AWS KMS and create the IAM role

Generate the private key and import it into KMS by following [aws-setup.md](https://github.com/suzuki-shunsuke/agent-skills/blob/main/skills/github-app-private-key-aws-kms/references/aws-setup.md) of the github-app-private-key-aws-kms skill.
The IAM role's trust policy is the exception: instead of listing repositories, restrict it by job_workflow_ref as below.

An example with [terraform-aws-github-app-kms](https://github.com/suzuki-shunsuke/terraform-aws-github-app-kms):

```hcl
module "kms" {
  source   = "github.com/suzuki-shunsuke/terraform-aws-github-app-kms?ref=v0.0.1"
  app_slug = "<app-slug>"
  imported = true
  conditions = [
    {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:<org>/*:job_workflow_ref:<org>/<shared-repo>/.github/workflows/<file>.yaml@refs/heads/<default-branch>"
      ]
    },
  ]
}
```

- Point job_workflow_ref at the default branch. Don't pin it to a SHA.
  - Pinning would force a trust policy update every time the reusable workflow changes.
  - The default branch is protected by the Branch Ruleset from [step 1](#1-protect-the-default-branch-with-an-organization-branch-ruleset).
- Don't restrict anything other than job_workflow_ref.
  - As long as no input of the reusable workflow can change where the tag goes, running it from a malicious branch only creates a tag on the HEAD of the default branch.

### 4. Create the reusable workflow that pushes tags

- inputs
  - `tag` (required)
  - `tag_message` (optional)
  - Never accept the target repository or ref (branch, tag, SHA) as an input. Doing so would let anyone push a tag to a malicious SHA.
- outputs
  - The default branch name
  - The SHA
- Get an installation access token for the dedicated GitHub App with [create-github-app-token-aws-kms](https://github.com/suzuki-shunsuke/create-github-app-token-aws-kms).
  - repositories: `GITHUB_REPOSITORY`
  - permissions: `contents:write`
- Get the default branch and its HEAD SHA from the GitHub API.
- Create an annotated tag with the GitHub API.
  - Fail if the tag already exists.

### 5. Add job_workflow_ref to each repository's subject claim

https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-with-reusable-workflows

```json
{
  "use_default": false,
  "include_claim_keys": ["repo", "context", "job_workflow_ref"]
}
```

> [!WARNING]
> `include_claim_keys` replaces the whole `sub`; it does not append to it.
> The change applies to the `sub` of every workflow in the repository at once, so existing OIDC workflows that assume roles based on the original `sub` may break.

### 6. Add a workflow calling the reusable workflow to each repository

- Any trigger works, but `workflow_dispatch` or similar is the expected one.
- Call the reusable workflow by the default branch, not a pinned SHA, so it matches the trust policy from [step 3](#3-import-the-private-key-into-aws-kms-and-create-the-iam-role).
  - If a linter such as pinact, ghalint, or zizmor enforces pinning, make this call an exception.

### 7. Restrict tag creation and changes with Organization Tag Rulesets

These rulesets stop existing tag-creating mechanisms, so create them only after [step 6](#6-add-a-workflow-calling-the-reusable-workflow-to-each-repository) is done. Create two rulesets:

1. restrict creations
    - Bypass list: the dedicated GitHub App
    - Target repositories: All repositories
    - Target tags: All tags
    - Rules: Restrict creations
1. restrict changes
    - Bypass list: none
    - Target repositories: All repositories
    - Target tags: All tags
    - Rules: Restrict updates, Restrict deletions
