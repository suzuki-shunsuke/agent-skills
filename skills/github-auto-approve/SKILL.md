---
name: github-auto-approve
description: Sets up and audits secure auto approve for pull requests across a GitHub organization, so that only pull requests genuinely meeting the intended conditions get approved, and the mechanism cannot be turned into a way to merge anything else. Covers the dedicated machine user and its CODEOWNERS paths, the fine-grained PAT held in AWS Secrets Manager and reachable only through OIDC pinned on the job_workflow_ref sub claim, the protected auto-approve branch, and the branch rulesets that make an approval mean something. Use when building auto approve, when reviewing an existing auto approve setup for holes, or when a workflow fails to assume the approve IAM role.
---

# Secure auto approve on GitHub

Source (Japanese):
https://github.com/szksh-lab-2/poc-enterprise-secure-auto-approve

## Scope

- A standardized scheme, governed centrally and applied uniformly across an organization's
  repositories rather than configured per repository. It earns its cost once auto approve is
  spreading to enough repositories that reviewing each one's configuration by hand is no longer
  realistic. OSS and personal projects are out of scope.
- Forks are not used. Allowing forks in an enterprise risks source code leaking and should be
  avoided regardless.
- Which conditions justify auto approving is out of scope. This is about guaranteeing that the
  condition you chose is the one that actually decides.
- AWS Secrets Manager holds the PAT. Google Cloud or another secret store works the same way.

## What is being protected

Auto approve skips human review for pull requests that meet conditions under which skipping it is
acceptable — a dependency bump limited to an action SHA and its version comment, say, or a change
confined to a data-only directory.

So an auto approved pull request is, by design, not reviewed by a person. What makes that acceptable
is the condition, and nothing else. The property to protect is therefore narrow and worth stating
exactly:

> A pull request is approved only when it genuinely satisfies the intended condition.

Everything in this skill exists to keep that true — to stop the mechanism being turned into a way to
merge a pull request that does not satisfy it. Deciding which conditions are acceptable in the first
place is a separate question, and out of scope here.

## How it gets bypassed

Three patterns hand a malicious insider, or a supply chain attack, a way to merge a pull request
that never met the condition:

1. Any pull request can be merged with no approval at all — the condition never has to be evaluated.
2. Any bot's approval is enough to merge — a different bot, judging by different rules, can approve
   in place of the intended one.
3. The PAT of the machine user that is a codeowner can be read out of an Organization Secret by
   anyone who can add a workflow — the approval can then be issued directly, with no condition
   evaluated at all.

## The security model

- The base branch of any auto approved pull request is protected by a branch ruleset. Prefer an
  Organization Ruleset; fall back to a Repository Ruleset only when that is impractical.
- A machine user exists solely to approve. Nothing else uses it.
- Its PAT lives in AWS Secrets Manager, and only workflows allowed by OIDC can read it. The `sub`
  claim is customized so that one claim pins the repository and the workflow together. Setting the
  organization template is not enough — each repository has to opt in.
- Reusable logic (fetching the PAT, approving, evaluating common conditions) lives in a dedicated
  repository as actions and reusable workflows.
- The approving reusable workflow of each repository lives on a dedicated `auto-approve` branch of
  that repository, protected by an Organization Ruleset that requires a security team review.

## Procedure

Once per organization:

1. [Create the two Organization Rulesets that protect the `auto-approve` branch](references/organization_setup.md)
2. [Customize the organization's OIDC `sub` claim template](references/oidc_sub_claim.md)
3. [Build the shared actions and reusable workflows in a dedicated repository](references/organization_setup.md)

Once per machine user:

4. [Create the machine user, the IAM role, the Secrets Manager secret and its resource policy, and
   store a fine-grained PAT in it](references/aws_secret.md)

Per repository:

5. [Opt in to the `sub` claim template, protect the base branch, give the machine user push access
   and add it to CODEOWNERS, create the `auto-approve` branch and its reusable workflow, then call
   that workflow](references/repository_setup.md)

When writing or reviewing the approving workflow and its actions, read
[Hardening the approving workflow](references/workflow_hardening.md).

## Rules

These are the load bearing parts. An auto approve setup that breaks any of them is not secure, no
matter what else is in place.

- Reference the decision logic action with `$/`, never `./`. `./` is the pull request's head, which
  its author controls.
- Never use a wildcard on both the repository and the `job_workflow_ref` halves of the `sub`
  condition. That lets one repository be approved by another repository's looser logic.
- The bypass list of every ruleset involved is empty.
- The base branch ruleset has `Require review from Code Owners`, `Dismiss stale pull request
  approvals when new commits are pushed`, and `Require approval of the most recent reviewable push`.
  Without all three, a commit pushed after the approval is merged unchecked.
- The job that holds the PAT never expands untrusted input (`${{ }}` from the pull request, or
  reusable workflow `inputs`) into a `run` step.
- Auto approvable paths contain no file from which code can run.

## Gotchas

- A GitHub App cannot be a codeowner. That is why this needs a machine user and a PAT rather than an
  app token.
- `Require a pull request before merging` does not apply to the push that *creates* a branch. That
  is why branch creation is restricted separately, and why the first push to `auto-approve` must
  contain nothing but CODEOWNERS.
- `include_claim_keys` replaces the whole `sub`; it does not append to it. Customizing it changes
  `sub` for **every** workflow in the repository at once and will break other workflows already
  assuming roles by OIDC. Inventory them first — [OIDC `sub` claim](references/oidc_sub_claim.md).
- Setting the organization's `sub` template applies to nothing on its own. Each repository has to
  opt in with `use_default: false`.
- CODEOWNERS is read from the base branch, so the CODEOWNERS governing the `auto-approve` branch has
  to live on `auto-approve` itself.

## Monitoring

Prevention can fail, so make failures visible.

- Record every approval by the machine user and alert on approvals in unexpected repositories or
  paths.
- Alert when the machine user does anything other than approve — pushing, opening pull requests,
  changing settings.
- Watch the organization audit log for `auto-approve` branch creations and ruleset changes.
- In AWS, record role assumptions and secret reads in CloudTrail.

## References

- [Organization setup](references/organization_setup.md) — read when configuring the organization,
  or checking whether it is configured: the two Organization Rulesets on `auto-approve`, the shared
  action / reusable workflow repository, and a complete approving workflow to copy from.
- [OIDC `sub` claim](references/oidc_sub_claim.md) — read when customizing the `sub` claim, or when
  `AssumeRoleWithWebIdentity` fails: `job_workflow_ref`, per-repository opt in, immutable subject
  claims, and how to migrate without breaking existing OIDC users.
- [Machine user, IAM role, and the PAT](references/aws_secret.md) — read when creating or reviewing
  any of those, and when asked why GitHub Secrets is not used instead. Terraform example code sits
  in [`references/terraform/`](references/terraform).
- [Enabling auto approve on a repository](references/repository_setup.md) — read when switching a
  repository on: base branch ruleset, CODEOWNERS path selection, the `auto-approve` branch, and the
  caller job.
- [Hardening the approving workflow](references/workflow_hardening.md) — read when writing or
  reviewing that workflow or its actions.

## Further reading

- https://zenn.dev/shunsuke_suzuki/articles/secure-github-actions-by-job-workflow-ref
- https://zenn.dev/shunsuke_suzuki/scraps/1d711e9708e6cc
