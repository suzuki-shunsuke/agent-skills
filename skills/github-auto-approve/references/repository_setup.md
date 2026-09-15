# Enabling auto approve on a repository

Read this when enabling auto approve on a repository, or when auditing one that has it.

Order:

1. Opt in to the OIDC `sub` claim template.
2. Protect the base branch with a branch ruleset.
3. Give the machine user push access and add it to CODEOWNERS.
4. If repository specific logic is needed, create the `auto-approve` branch and its reusable
   workflow (organization admins only).
5. Call the reusable workflow from the workflow that should approve.

## 1. Opt in to the `sub` claim template

```sh
gh api -X PUT "/repos/$ORG/$REPO/actions/oidc/customization/sub" \
  --input - <<< '{"use_default":false}'
```

This changes `sub` for every workflow in the repository, not just the approving one. Inventory the
repository's other OIDC users first — see [OIDC `sub` claim](oidc_sub_claim.md).

## 2. Protect the base branch

On the base branch of the pull requests that will be auto approved:

- `Require review from Code Owners`. Without it, any user or bot with push access can approve and
  merge.
- Empty bypass list.
- `Dismiss stale pull request approvals when new commits are pushed`
- `Require approval of the most recent reviewable push`

The last two are what stop a commit pushed *after* the approval from being merged unchecked. The
approving workflow pins the review's `commit_id` for the same reason; pinning only means something
in combination with these settings.

## 3. Machine user push access and CODEOWNERS

Adding an account to CODEOWNERS requires push access to the repository, so grant it.

Add the machine user to the CODEOWNERS on the base branch, limited to the files that auto approved
pull requests may change.

```
staging/** @approve-bot
```

### Choosing the paths

This is the most consequential decision in the whole scheme. Merging any of the following without
human review has large consequences, so think hard before including them:

- `.github/` — workflows are code that CI executes, so this grants arbitrary code execution with the
  repository's secrets. If CODEOWNERS lives at `.github/CODEOWNERS`, it also means rewriting
  CODEOWNERS.
- `CODEOWNERS` — rewrites who owns subsequent pull requests.
- Dependency lock files and manifests — pulls in a malicious dependency.
- Build configuration and scripts (`Makefile`, `package.json` `scripts`, …) — arbitrary code
  execution in CI.

As a rule, limit it to directories holding data only, and keep out any path from which code can run.

What is at risk here is not the auto approve mechanism but the repository's CI being taken over. The
decision logic and the approving steps live on the `auto-approve` branch and are referenced with
`$/`, so rewriting these files cannot swap them out.

### When paths are not enough: Dependabot and Renovate

Auto merging action updates from Dependabot or Renovate is a realistic requirement, and path
restrictions alone do not express it. The condition then also involves the pull request's author and
the content of its commits, which is harder to judge than paths. At minimum:

- Verify that *every* commit in the pull request comes from the trusted bot.
  - The author alone is not enough: other users can push to a bot's branch.
  - Commit author and committer emails can be set freely, so verify the signature
    (`verification.verified` and the signer) instead.
- Constrain the change itself. Limiting it to "action SHA and version comment updates only" removes
  the dependence on the bot being trustworthy.

Workflows in Dependabot pull requests do honour the `permissions` key, so `id-token: write` can be
requested and this scheme works there.

- https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-on-actions
- https://github.blog/changelog/2021-10-06-github-actions-workflows-triggered-by-dependabot-prs-will-respect-permissions-key-in-workflows/

## 4. Create the `auto-approve` branch

Only organization admins can do this, because of the Organization Ruleset that restricts branch
creation — see [Organization setup](organization_setup.md).

Needed only when the repository requires its own approval logic.

Create an orphan branch:

```sh
git switch --orphan auto-approve
```

Push CODEOWNERS first, e.g. requiring the security team for every file on the branch:

```
* @szksh-lab-2/security
```

```sh
git add CODEOWNERS
git commit -m "chore: initialize auto-approve branch"
git push -u origin auto-approve
```

Do not include the reusable workflow in that first push — the push that creates a branch is not
subject to the pull request requirement, so anything in it goes in unreviewed. Add the workflow
afterwards through a pull request against `auto-approve`.

Resulting layout:

```
README.md
CODEOWNERS
.github/
  workflows/
    auto_approve.yaml # the approving reusable workflow
  actions/
    auto_approve/ # repository specific approval decision logic
      action.yaml
      ...
```

Example:

- https://github.com/szksh-lab-2/poc-enterprise-secure-auto-approve/tree/auto-approve
- https://github.com/szksh-lab-2/poc-enterprise-secure-auto-approve/blob/auto-approve/.github/workflows/auto_approve.yaml
- https://github.com/szksh-lab-2/poc-enterprise-secure-auto-approve/tree/auto-approve/.github/actions/auto_approve

Protecting the `auto-approve` branch with
[validate-pr-review-app](https://github.com/suzuki-shunsuke/validate-pr-review-app) as well is
recommended.

## 5. Call the reusable workflow

Add a job to the workflow that should approve.

```yaml
# .github/workflows/test.yaml
on: pull_request
jobs:
  approve:
    uses: szksh-lab-2/poc-enterprise-secure-auto-approve/.github/workflows/auto_approve.yaml@auto-approve
    permissions:
      contents: read # To resolve the action in the reusable workflow's repository
      pull-requests: read # To list the updated files of the pull request
      id-token: write # To get an OIDC token to assume the AWS IAM role
```

Reference it by branch. Pinning to a full-length commit SHA would mean updating the OIDC
`job_workflow_ref` condition on every SHA bump, which is not worth it — the branch is protected by
the Organization Ruleset, which is what makes the reference trustworthy.
