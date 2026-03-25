# How To Avoid 2 Approvals

- [Sign Commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits)
- CI
  - Use [Securefix Action](https://github.com/csm-actions/securefix-action)
  - Use [Update Branch Action](https://github.com/csm-actions/update-branch-action)
    - If approvers use the `Update Branch` button, other approvals are required due to the validation rule `If a committer approves, 2 approvals are required.`
- Add GitHub Apps to `trusted_apps`
- [Not Recommended: Configure `insecure`](config.md#allow-unsigned-commits)

## Use Securefix Action

Securefix Action allows you to create commits and pull requests via GitHub Actions securely.
If you create commits using git commands or GitHub Actions like [stefanzweifel/git-auto-commit-action](https://github.com/stefanzweifel/git-auto-commit-action) and [peter-evans/create-pull-request](https://github.com/peter-evans/create-pull-request), you should replace them with Securefix Action.
And by adding the server GitHub App for Securefix Action to `trusted_apps`, you can avoid 2 approvals.
