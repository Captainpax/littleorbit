#!/bin/sh
set -eu

for file in release.p12 store-password key-alias key-password; do
  test -f "/secrets/$file"
done

actual=$(java -cp /opt/release SignerCertificateVerifier /secrets)
expected=$(python3 -c \
  'import json; print(json.load(open("/opt/release/policy.json", encoding="utf-8"))["certificate_sha256"].lower())')
test "$actual" = "$expected" || {
  echo "signer certificate does not match the pinned Little Orbit identity" >&2
  exit 2
}
printf 'Little Orbit signer bundle verified: %s\n' "$actual"
