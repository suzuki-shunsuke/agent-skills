# AWS setup (once per GitHub App)

How to register a GitHub App private key in AWS KMS and let GitHub Actions sign with it via OIDC.
Once this is done for a GitHub App, it does not need to be repeated when adding or modifying workflows.

The workflow changes are described in [SKILL.md](../SKILL.md).

## Requirements

- AWS CLI
- Terraform (when managing this with Terraform)
- jq
- openssl
- xxd
- base64
- bash

Required AWS permissions:

- Importing the private key: `kms:DescribeKey`, `kms:GetParametersForImport`, `kms:ImportKeyMaterial`
- Creating the KMS key and alias with the CLI: `kms:CreateKey`, `kms:CreateAlias`
- Creating the IAM role and policy: `iam:CreateRole`, `iam:PutRolePolicy`, and so on

## Steps

1. Create an empty AWS KMS key
2. Set up the IAM role
3. Import the private key into KMS
4. Register the GitHub Variables
5. Delete the local copy of the private key

> [!WARNING]
> Adjust the resource names in the sample code as appropriate.

> [!WARNING]
> Confirm the values for the placeholders wrapped in `<<>>` with the user before substituting them.

Placeholders

- `<<GITHUB_APP>>`: a string identifying the GitHub App. Used in Terraform resource IDs and similar.
- `<<KMS_ALIAS>>`: the KMS alias
- `<<OWNER>>` / `<<REPO>>`: the repository holding the workflow that generates the token

## 1. Create an empty AWS KMS key

`RSA_2048` and `SIGN_VERIFY` are not a matter of choice.
GitHub App JWT signing is fixed to RS256 (RSASSA-PKCS1-v1_5 + SHA-256, RSA 2048).

### With Terraform

Use `aws_kms_external_key`, not `aws_kms_key`.
`aws_kms_key` has no argument for setting the origin to `EXTERNAL`, so KMS generates its own key material and the import in step 3 fails.
Note that the argument is named `key_spec`, not `customer_master_key_spec`.

```tf
resource "aws_kms_external_key" "github_app_<<GITHUB_APP>>" {
  description  = "GitHub App JWT signing key"
  key_spec     = "RSA_2048"
  key_usage    = "SIGN_VERIFY"
  multi_region = false

  # Until the key material is imported the key is PendingImport, where only false is allowed.
  # Change this to true and apply again once the import in step 3 is done.
  enabled = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_kms_alias" "github_app_<<GITHUB_APP>>" {
  name          = "alias/<<KMS_ALIAS>>"
  target_key_id = aws_kms_external_key.github_app_<<GITHUB_APP>>.key_id
}
```

> [!WARNING]
> Do not use `key_material_base64` on `aws_kms_external_key`.
> It stores the private key in the Terraform state in plaintext, which defeats the entire purpose of this procedure.
> The key material is loaded with the AWS CLI in step 3.

Leaving `valid_to` unset makes the key material non-expiring (this matches `KEY_MATERIAL_DOES_NOT_EXPIRE` in step 3).

### With the AWS CLI

```sh
# Create an empty container for the key. With `--origin EXTERNAL`, KMS generates no key
# and `KeyState` stays `PendingImport`. Your own key is loaded into it later.
KMS_KEY_ID=$(aws kms create-key \
  --key-spec RSA_2048 \
  --key-usage SIGN_VERIFY \
  --origin EXTERNAL \
  --output json \
  --description "GitHub App JWT signing key" | jq -r ".KeyMetadata.KeyId")

# Not required, but an alias is convenient.
aws kms create-alias \
    --alias-name "alias/<<KMS_ALIAS>>" \
    --target-key-id "$KMS_KEY_ID"
```

## 2. Set up the IAM role

- Grant the IAM role permission to sign with the KMS key
- Allow GitHub Actions to assume the IAM role via OIDC

There are two policy documents. Don't mix them up.

- `sign_github_app_<<GITHUB_APP>>`: permission to sign with the KMS key. Passed to `aws_iam_role_policy`
- `sign_github_app_<<GITHUB_APP>>_assume_role`: who may assume this role. Passed to `assume_role_policy`

Passing the permission document to `assume_role_policy` fails to apply because it has no principal.

```tf
resource "aws_iam_role" "sign_github_app_<<GITHUB_APP>>" {
  name               = "sign_github_app_<<GITHUB_APP>>"
  description        = "Sign GitHub App JWTs with AWS KMS"
  assume_role_policy = data.aws_iam_policy_document.sign_github_app_<<GITHUB_APP>>_assume_role.json
}

data "aws_iam_policy_document" "sign_github_app_<<GITHUB_APP>>" {
  statement {
    effect    = "Allow"
    actions   = ["kms:Sign"]
    resources = [aws_kms_external_key.github_app_<<GITHUB_APP>>.arn]

    condition {
      test     = "StringEquals"
      variable = "kms:SigningAlgorithm"
      values   = ["RSASSA_PKCS1_V1_5_SHA_256"]
    }
  }
}

resource "aws_iam_role_policy" "sign_github_app_<<GITHUB_APP>>" {
  name   = "sign_github_app_<<GITHUB_APP>>"
  role   = aws_iam_role.sign_github_app_<<GITHUB_APP>>.id
  policy = data.aws_iam_policy_document.sign_github_app_<<GITHUB_APP>>.json
}

data "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"
}

data "aws_iam_policy_document" "sign_github_app_<<GITHUB_APP>>_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      # List the repositories and refs holding the workflows that generate tokens
      values = [
        "repo:<<OWNER>>/<<REPO>>:ref:refs/heads/main",
      ]
    }
  }
}
```

> [!WARNING]
> Do not use an organization-wide wildcard such as `repo:<<OWNER>>/*:*` for `sub`.
> Anyone who can push a workflow to any repository in that organization would be able to sign,
> which undermines the point of moving the private key into KMS.
> Restrict it to the repository name, and to the ref or environment where possible.

When a workflow in a new repository starts generating tokens, that repository has to be added to this `sub` list.

## 3. Import the private key into KMS

The private key is encrypted before being sent to AWS so that it cannot leak in transit.
`aws kms get-parameters-for-import` returns a temporary (24h) public key and an import token for this purpose.
The GitHub App private key is too large to be encrypted with that public key directly.
So a temporary AES key (symmetric) is generated to encrypt the private key, the AES key is encrypted with the public key, and the two are concatenated and sent to AWS.

First check that the AWS CLI can reach the KMS key.
Set AWS_PROFILE and AWS_REGION as needed.

```sh
# When step 1 was done with Terraform, set the KMS key ID / ARN / alias here
KMS_KEY_ID=alias/<<KMS_ALIAS>>

aws kms describe-key \
  --key-id "$KMS_KEY_ID" \
  --query 'KeyMetadata.{Arn:Arn,Enabled:Enabled,KeyState:KeyState,Origin:Origin}'
```

Confirm that `Origin` is `EXTERNAL` and `KeyState` is `PendingImport`.

Download the private key from GitHub and run [scripts/import.sh](../scripts/import.sh) from the skill directory.
The script writes the converted plaintext private key to a temporary directory, but deletes it on exit whether or not it succeeds.

```sh
# PRIVATE_KEY: path to the downloaded private key file
PRIVATE_KEY=~/Downloads/<<GITHUB_APP>>.private-key.pem

bash scripts/import.sh "$KMS_KEY_ID" "$PRIVATE_KEY"
```

The import succeeded if the `KeyState` printed at the end is `Enabled`.
When managing this with Terraform, change `enabled` to `true` and apply again.

> [!WARNING]
> Deleting the imported key material or the KMS key makes re-importing impossible, because step 5 deletes the private key.
> Recovering means issuing a new GitHub App private key and starting over.
> Do not remove `prevent_destroy`.

## 4. Register the GitHub Variables

Register the values the workflow references as GitHub Variables (not Secrets).
None of them are sensitive.
Confirm the variable names with the user and adjust them as needed.

- `ROLE_TO_ASSUME`: ARN of the IAM role created in step 2 for signing with the KMS key
- `APP_ID`: the GitHub App's App ID. Note that this is **not the Client ID**
- `KMS_KEY_ID`: ID / ARN / alias of the KMS key created in step 1

When workflows in several repositories use this, organization variables avoid having to register them per repository.

## 5. Delete the local copy of the private key

Leaving the private key on a local machine is a leak risk, so delete it.
Check for copies and the trash, not just the downloaded file itself.

> [!NOTE]
> Revoking the old private key registered on the GitHub App, and deleting the secrets that are no longer needed (such as `secrets.APP_PRIVATE_KEY`), are out of scope for this skill.
> When the same private key is used by other workflows or systems, the migration takes time to complete.
> Just be aware that the old private key can still generate tokens until it is revoked.

That completes the setup.
See [SKILL.md](../SKILL.md) for the workflow changes.
