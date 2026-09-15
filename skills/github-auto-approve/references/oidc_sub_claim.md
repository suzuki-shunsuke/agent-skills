# OIDC `sub` claim

Read this when customizing the `sub` claim, or when a workflow fails to assume the IAM role with
`AccessDenied: Not authorized to perform sts:AssumeRoleWithWebIdentity`.

## Why `job_workflow_ref` has to be in `sub`

The PAT must be obtainable only from a trusted workflow. `job_workflow_ref` is the ref path of the
reusable workflow that defines the job, so restricting on it means restricting to a workflow managed
on a protected branch.

https://docs.github.com/en/actions/reference/security/oidc#custom-claims-provided-by-github

The only OIDC condition keys AWS exposes in an assume role policy are `sub`, `aud`, and `amr`.
There is no `token.actions.githubusercontent.com:job_workflow_ref` condition key. That is why
`job_workflow_ref` has to be folded into `sub`.

By default `sub` is `repo:<owner>/<repo>:ref:refs/heads/<branch>` and contains no
`job_workflow_ref`, so customize the organization template:

```sh
gh api -X PUT "/orgs/$ORG/actions/oidc/customization/sub" \
  -f 'include_claim_keys[]=repo' \
  -f 'include_claim_keys[]=job_workflow_ref'
```

`sub` then becomes `repo:<owner>/<repo>:job_workflow_ref:<job_workflow_ref>`.

Specifying the repository and the workflow as two separate conditions would evaluate them as a cross
product, allowing a repository to use a workflow it is not paired with. One combined claim pins the
pair.

https://docs.github.com/en/rest/actions/oidc?apiVersion=2022-11-28#set-the-customization-template-for-an-oidc-subject-claim-for-an-organization

## Each repository has to opt in

Setting the organization template does not apply it. A repository left at `use_default: true` keeps
issuing GitHub's default `sub`.

```sh
gh api -X PUT "/repos/$ORG/$REPO/actions/oidc/customization/sub" \
  --input - <<< '{"use_default":false}'
```

Check the current setting:

```sh
gh api "/repos/$ORG/$REPO/actions/oidc/customization/sub"
```

Forgetting to opt in produces `AccessDenied: Not authorized to perform
sts:AssumeRoleWithWebIdentity` even when the IAM role is correct, because `sub` does not match.

Opting in changes `sub` for *every* workflow in that repository, so any other IAM role conditions
used from it have to be updated as well.

Calling this endpoint with a GitHub App token needs `actions:write`. The REST API documentation only
mentions the classic PAT `repo` scope.

## Immutable subject claims

Repositories created, renamed, or transferred on or after 2026-07-15 get immutable subject claims
automatically. The repository part of `sub` then embeds the owner ID and the repository ID:

```
repo:<owner>@<owner_id>/<repo>@<repo_id>:job_workflow_ref:<job_workflow_ref>
```

e.g.

```
repo:szksh-lab-2@204274656/poc-enterprise-secure-auto-approve@1366980709:job_workflow_ref:szksh-lab-2/poc-enterprise-secure-auto-approve/.github/workflows/auto_approve.yaml@refs/heads/auto-approve
```

IDs are never reused, which prevents subject recycling — another repository claiming the same `sub`
after a rename or a delete and recreate. Customizing `include_claim_keys` cannot remove the IDs from
the repository part.

Only the repository part carries IDs. `job_workflow_ref` stays name based.

The repository part is exactly the `sub_claim_prefix` returned by the GET.

Immutable subject claims are configured separately for the organization and for each repository, and
the repository setting wins. An organization at `use_immutable_subject: false` still issues the
immutable form for a repository set to `true`, so check the repository setting before writing the
assume role policy.

https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/

## Customizing `sub` is a breaking change

`include_claim_keys` applies at once to **every** OIDC token the repository issues. It cannot be
scoped to one workflow. Workflows already using OIDC in that repository will start failing to assume
their roles.

The conditions that break usually live in another repository or under another team, and because the
change is on GitHub's side it does not show up in a Terraform plan. Without an inventory first, the
first sign is a failed deploy or release.

### Default `sub` and `context`

Uncustomized, `sub` is `repo:<owner>/<repo>:<context>`, where `<context>` depends on the event:

| Trigger | `<context>` |
|---|---|
| push to a branch | `ref:refs/heads/<branch>` |
| push of a tag | `ref:refs/tags/<tag>` |
| pull_request | `pull_request` |
| a job using an environment | `environment:<environment>` |

`include_claim_keys` **replaces the whole `sub`**. It does not append. Anything not listed is gone.

### Whether to include `context`

`["repo", "job_workflow_ref"]` drops `<context>` entirely:

```
repo:<owner>/<repo>:job_workflow_ref:<owner>/<repo>/.github/workflows/x.yaml@refs/heads/main
```

Branch, tag, environment, and pull_request are no longer distinguishable from `sub`, so every
existing condition that relied on the default `sub` dies.

Including `context` keeps the default `sub` as a prefix:

```
# ["repo", "context", "job_workflow_ref"] / push
repo:<owner>/<repo>:ref:refs/heads/master:job_workflow_ref:<owner>/<repo>/.github/workflows/x.yaml@refs/heads/master
# ["repo", "context", "job_workflow_ref"] / pull_request
repo:<owner>/<repo>:pull_request:job_workflow_ref:<owner>/<repo>/.github/workflows/x.yaml@refs/pull/31/merge
```

Existing conditions migrate by appending `:job_workflow_ref:*`, and branch or environment
restrictions survive. For a repository already using OIDC, this is normally the right choice.

`ref` is also accepted as a key — the API rejects unknown keys with
`400 The template has one or more unsupported claim keys.`, so this is a meaningful result, and it
is absent from the official examples. There is almost no reason to use it: on push it duplicates
`context` exactly, and on pull_request it is `refs/pull/<N>/merge`, which changes per pull request.

### Which conditions break

It depends on how the cloud side wrote the condition:

| Condition style | `["repo","job_workflow_ref"]` | `["repo","context","job_workflow_ref"]` |
|---|---|---|
| `StringEquals`, exact match | breaks | breaks |
| `StringLike`, no trailing wildcard (`repo:o/r:ref:refs/heads/main`) | breaks | breaks |
| `StringLike`, trailing wildcard (`repo:o/r:ref:refs/heads/main*`) | breaks | survives |
| broad wildcard such as `repo:o/r:*` or `repo:o/*:*` | survives | survives |

`StringLike` matches the whole string, so once a segment is appended it no longer matches without a
trailing wildcard. This is the case most often missed.

IAM's `*` matches `:` as well, so `repo:<owner>/*:*` keeps matching through a format change — but
surviving is not the same as being safe. Such a condition does not restrict the repository at all.

Failures appear as `AccessDenied: Not authorized to perform sts:AssumeRoleWithWebIdentity`. It is
fail closed, so it never widens permissions, but every workflow using OIDC in that repository stops
at once.

Including `environment` in `include_claim_keys` makes an environment mandatory: jobs that use no
environment can no longer get a token.

### Safe migration

For a repository that already uses OIDC:

1. Take inventory.
   1. Find every workflow in the repository using OIDC (grep for `id-token: write`).
   2. Identify the IAM role each one assumes.
   3. Trace where each assume role policy is managed — often another repository.
   4. Classify each condition against the table above.
2. Observe the `sub` actually issued, using a throwaway repository. Check both push and
   pull_request; the values differ.
3. Widen the assume role policies first, so they accept both the old and the new `sub`. Do not touch
   GitHub yet.
4. Switch the template **per repository, not at the organization level**.
   `PUT /repos/{owner}/{repo}/actions/oidc/customization/sub` accepts `include_claim_keys` as well as
   `use_default`, so one repository can be tried without touching the organization. The blast radius
   is that repository, and rolling back is a PUT of `{"use_default": true}`.
5. Run the inventoried workflows for real, on both push and pull request events.
6. Drop the old form from the conditions.
7. Promote to the organization template last, and only if needed. Changing it affects every opted in
   repository simultaneously.

## Checking the `sub` that was actually issued

When assume role fails, start here. The format depends on the combination of organization and
repository settings, so writing the policy from guesswork is hard to get right.

In AWS it is recorded in the CloudTrail `AssumeRoleWithWebIdentity` event. Failed events record the
`sub` too, which makes this the easiest route.

```sh
aws cloudtrail lookup-events --region us-east-1 \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity \
  --start-time 2026-09-13T13:00:00Z \
  --query 'Events[].CloudTrailEvent' --output text |
  tr '\t' '\n' |
  jq -r '.eventTime + " " + (.errorCode // "OK") + " " + .userIdentity.userName'
```

`userIdentity.userName` is the `sub`. With the global STS endpoint the events land in `us-east-1`.
CloudTrail takes a few minutes to catch up.

To check from the GitHub side, [github/actions-oidc-debugger](https://github.com/github/actions-oidc-debugger)
prints the token's claims. It writes claims to the log, so use it only while investigating and
remove it afterwards.
