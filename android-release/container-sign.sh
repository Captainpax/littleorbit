#!/bin/sh
set -eu

for file in release.p12 store-password key-alias key-password; do
  test -f "/secrets/$file"
done

exec python3 /opt/release/release_tool.py sign \
  --policy /opt/release/policy.json \
  --candidate /candidate \
  --output /out \
  --work /work \
  --keystore /secrets/release.p12 \
  --store-password /secrets/store-password \
  --key-alias /secrets/key-alias \
  --key-password /secrets/key-password
