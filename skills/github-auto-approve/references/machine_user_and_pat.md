# Machine user, IAM role, and the PAT

Read this when creating or reviewing the machine user, the IAM role, the Secrets Manager secret, or
the PAT — and when asked why GitHub Secrets is not used instead.

Terraform example code: [`terraform/`](terraform) next to this file (`locals.tf`, `iam.tf`,
`secretsmanager.tf`). The comments in it explain each condition.

## The machine user

A GitHub App cannot be a codeowner, so approving requires a real user account.

Create a machine user used for nothing but approving. If the same account is used elsewhere, every
one of those uses is another way for its PAT to leak, and that PAT approves pull requests. Manage
the account and its PAT strictly.

One shared machine user across repositories is the practical choice — one per repository does not
scale past a handful.

## AWS resources

- IAM role that can read the secret.
  - Assume role policy: OIDC, allowing the pair of repository and `job_workflow_ref`.
  - Keep the repository list in a local value so adding a repository is a one line change.
- IAM role policy: `secretsmanager:GetSecretValue`.
- Secrets Manager secret. Do not manage the secret value in Terraform — `aws_secretsmanager_secret_version`
  writes it into the state file in plaintext. Set it out of band with the AWS CLI or the console.
- Secret resource policy: allow `secretsmanager:GetSecretValue` from the dedicated role, and deny it
  from every other principal. The deny matters because SREs often hold broad identity-based
  permissions; a resource policy is what actually stops them.

## Enumerate the repositories, do not glob

List repositories one by one in the assume role policy. A wildcard that allows any repository lets
someone add a rogue workflow to a repository that has no `auto-approve` branch and abuse the PAT
from there. Requiring a review to add a repository to the list is the control that prevents this.

The `sub` has the form
`repo:<A>:pull_request:job_workflow_ref:<B>/.github/workflows/auto_approve.yaml@refs/heads/auto-approve`.
If both A and B are wildcards, combinations where A and B differ also match — repository A gets its
pull requests approved by repository B's logic. The organization then effectively runs on its
loosest repository's standard. Always pair the repository with its own workflow.

A workflow shared by several repositories is the one case where the workflow file name is a
wildcard, so restrict it by prefix (`auto_approve_*.yaml`) and keep the repository half exact.
The caller's branch does not have to be restricted there: the shared workflow fetches the pull
request and decides for itself whether it may be approved, so a caller can only choose which pull
request is evaluated. That holds only as long as the shared workflow never interpolates its inputs
into a `run` block — see [Hardening the approving workflow](workflow_hardening.md).

### Generating the list from a data source

Terraform's `github_repositories` data source can produce the list, pairing each repository with its
own workflow automatically. The trade-off is that newly created repositories are then added on every
apply, which removes the review step.

Where immutable subject claims are enabled, the repository half of the `sub` contains numeric owner
and repository IDs, so repository names alone are not enough — the data source has to supply the
IDs. Whether immutable claims are on can differ per repository, so confirm the `sub` that is
actually issued before building the values. See [OIDC `sub` claim](oidc_sub_claim.md).

## The fine-grained PAT

- Permissions: `pull-requests:write` only.
- Repository access: only the repositories that need auto approve. With a shared machine user, this
  setting is what bounds the damage if the PAT leaks. `All repositories` means every pull request in
  the organization can be approved.
- Fine-grained PATs always expire, so plan the rotation:
  - Notify before expiry, so auto approve stopping is not the first sign.
  - Make renewal nothing more than replacing the Secrets Manager secret value.

## Protecting the Terraform itself

Manage the Terraform code under a branch ruleset too. Without it, the PAT can be obtained by editing
the policies. Leave an audit trail and monitor it — notify Slack when an assume role policy or a
resource based policy changes, for example.

## Why not GitHub Secrets

The whole scheme depends on only the approving reusable workflow being able to read the PAT, and
GitHub Secrets has no way to express "only this workflow may read this".

- Organization Secrets — can be scoped to repositories, but not to a branch or a workflow. Anyone
  who can add a workflow to a targeted repository can read it.
- Repository Secrets — same workflow problem, plus a secret per repository, which makes managing and
  rotating the PAT painful.
- Environment Secrets — deployment branch policies and required reviewers do protect them, but the
  approving job runs in a pull request context, which does not fit branch based restrictions, and
  required reviewers reintroduce a human approval, defeating the point. Adding another workflow that
  references the environment still gets at the secret, and it is per repository like the above.
- Dependabot Secrets — tempting because Actions secrets are unavailable in Dependabot pull requests,
  but it behaves like the others: no workflow level restriction.

None of them leave an access log either. Secrets Manager reads are recorded in CloudTrail, so
unexpected access can be detected.

## Upstream

https://github.com/szksh-lab-2/poc-enterprise-secure-auto-approve/tree/main/skills/setup-auto-approve/references
