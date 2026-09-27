#!/bin/sh
set -eu

test -f /opt/little-orbit-android-builder
test -f /src/gradlew
test -d /out
test -z "$(find /out -mindepth 1 -maxdepth 1 -print -quit)"

cp -a /src/. /work/repo
cd /work/repo
./gradlew --no-daemon \
  :apps:android:domain:test \
  :apps:android:data:testDebugUnitTest \
  :apps:android:mobile:testDebugUnitTest \
  :apps:android:wear:testDebugUnitTest \
  :apps:android:mobile:lintRelease \
  :apps:android:wear:lintRelease \
  :apps:android:mobile:assembleRelease \
  :apps:android:wear:assembleRelease
python3 /opt/release/release_tool.py prepare \
  --policy /opt/release/policy.json \
  --source /work/repo \
  --output /out
