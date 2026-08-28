#!/usr/bin/env bash
# Import a GitHub App private key into an AWS KMS key.
#
# Usage:
#   bash import.sh <KMS_KEY_ID> <PRIVATE_KEY_FILE>
#
#   KMS_KEY_ID:       ID / ARN / alias of the KMS key to import into
#   PRIVATE_KEY_FILE: path to the private key (PEM) downloaded from GitHub

set -euo pipefail
umask 077

kms_key_id="$1"
private_key="$2"

# Temporary directory holding intermediate files, including the plaintext private key.
# Always removed, whether or not this script succeeds.
kms_import_dir="$(mktemp -d)"
trap 'rm -rf "$kms_import_dir"' EXIT

private_key_der="${kms_import_dir}/private-key.der" # GitHub App private key converted to the format KMS expects

# Convert the private key downloaded from GitHub to the format AWS KMS expects.
# PKCS#1 => PKCS#8 DER (raw binary)
# -topk8                   PKCS#1 -> PKCS#8
# -inform PEM -outform DER Base64 text -> raw binary
# -nocrypt                 output without a passphrase. Required
openssl pkcs8 -topk8 -inform PEM -outform DER \
  -in "$private_key" -out "$private_key_der" -nocrypt

test -f "$private_key_der"

# Get the public key and import token needed to import the key material.
# They are valid for 24 hours.
aws kms get-parameters-for-import \
  --key-id "$kms_key_id" \
  --wrapping-algorithm RSA_AES_KEY_WRAP_SHA_256 \
  --wrapping-key-spec RSA_4096 \
  > "$kms_import_dir/parameters.json"

jq -r '.PublicKey' "$kms_import_dir/parameters.json" \
  | base64 -d > "$kms_import_dir/wrapping-key.der"

jq -r '.ImportToken' "$kms_import_dir/parameters.json" \
  | base64 -d > "$kms_import_dir/import-token.bin"

# Generate a single-use 256-bit AES key.
# The GitHub App private key is too large to be encrypted with the KMS public key directly.
openssl rand -out "$kms_import_dir/aes-key.bin" 32

# Encrypt the single-use AES key with the KMS public key using RSA-OAEP-SHA256.
# -inkey: the KMS public key
# -in:    the single-use AES key
openssl pkeyutl -encrypt \
  -pubin \
  -keyform DER \
  -inkey "$kms_import_dir/wrapping-key.der" \
  -in "$kms_import_dir/aes-key.bin" \
  -out "$kms_import_dir/wrapped-aes-key.bin" \
  -pkeyopt rsa_padding_mode:oaep \
  -pkeyopt rsa_oaep_md:sha256 \
  -pkeyopt rsa_mgf1_md:sha256

# Convert the single-use AES key to hex.
aes_key_hex="$(xxd -p -c 256 "$kms_import_dir/aes-key.bin")"

# Encrypt the GitHub App private key with the single-use AES key.
# -K:  the single-use AES key (hex). Visible in ps, which is acceptable because the key
#      is used only by this process and is not needed after the import
# -iv: the fixed AIV defined by RFC 5649 (AES Key Wrap with Padding). Do not change it
# -in: the GitHub App private key converted to the format KMS expects
openssl enc -id-aes256-wrap-pad \
  -K "$aes_key_hex" \
  -iv A65959A6 \
  -in "$private_key_der" \
  -out "$kms_import_dir/wrapped-private-key.bin"

unset aes_key_hex

# Concatenate, in this order, the AES key encrypted with the KMS public key
# and the GitHub App private key encrypted with the AES key.
cat "$kms_import_dir/wrapped-aes-key.bin" "$kms_import_dir/wrapped-private-key.bin" \
  > "$kms_import_dir/encrypted-key-material.bin"

# Import the private key into KMS.
aws kms import-key-material \
  --key-id "$kms_key_id" \
  --import-token "fileb://$kms_import_dir/import-token.bin" \
  --encrypted-key-material "fileb://$kms_import_dir/encrypted-key-material.bin" \
  --expiration-model KEY_MATERIAL_DOES_NOT_EXPIRE

# Check the key state after the import. KeyState should be Enabled.
aws kms describe-key \
  --key-id "$kms_key_id" \
  --query 'KeyMetadata.{Arn:Arn,Enabled:Enabled,KeyState:KeyState,Origin:Origin}'
