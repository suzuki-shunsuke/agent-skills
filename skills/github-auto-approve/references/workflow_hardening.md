# Hardening the approving workflow

Read this when writing or reviewing the approving reusable workflow and its actions. The AWS
credentials and the PAT live in this job, so mistakes here leak them or let the approval decision be
replaced.

## Reference the decision action with `$/`, never `./`

`$/` refers to the repository at the same ref as the workflow being run. The approving reusable
workflow is always called at the fixed `auto-approve` ref, so an action referenced with `$/` is the
one on the `auto-approve` branch — protected by the Organization Ruleset and reviewed.

```yaml
- uses: $/.github/actions/auto_approve
```

Never reference checked out code:

```yaml
- uses: ./.github/actions/auto_approve # wrong
```

That is the pull request's head, which its author can rewrite, so the decision logic can be replaced
with one that always approves.

https://github.blog/changelog/2026-07-30-reference-same-repository-actions-with-self-repository-syntax/

## Never expand untrusted input in the job holding the PAT

Interpolating `${{ }}` — a pull request title, a branch name — into a `run` step in this job allows
script injection, which exfiltrates the credentials.

- Pass pull request derived values through `env`, not directly into `run`.
- The same applies to a shared reusable workflow's `inputs`. Do not expand them into `run` either.

## Write the logic as an action with tests

Repository specific logic that is anything but trivial should be a composite action or a JS action
called from the reusable workflow, with unit tests.

`run` steps and `github-script` are hard to maintain, and a hole in the approval logic is dangerous.

## Separate the deciding action from the approving action

- The decision becomes testable on its own.
- A third party action used for the decision never receives the PAT, so it cannot leak it.

## Pin the review's `commit_id`

Approve through the API with an explicit `commit_id` rather than `gh pr review -a`. Combined with
the base branch's `Dismiss stale pull request approvals when new commits are pushed` and
`Require approval of the most recent reviewable push`, this is what stops a commit pushed after the
approval from riding along — see [Enabling auto approve on a repository](repository_setup.md).
