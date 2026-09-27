#!/bin/sh
set -eu

usage() {
  echo "usage: $0 <source-checkout> <candidate-dir> <signed-dir> <signer.age> <age-identity>" >&2
  echo "       $0 --verify-bundle <source-checkout> <signer.age> <age-identity>" >&2
  exit 2
}

MODE=release
if test "${1:-}" = "--verify-bundle"; then
  test "$#" -eq 4 || usage
  MODE=verify
  SOURCE=$(realpath "$2")
  CANDIDATE=
  SIGNED=
  BUNDLE=$(realpath "$3")
  IDENTITY=$(realpath "$4")
else
  test "$#" -eq 5 || usage
  SOURCE=$(realpath "$1")
  CANDIDATE=$(realpath -m "$2")
  SIGNED=$(realpath -m "$3")
  BUNDLE=$(realpath "$4")
  IDENTITY=$(realpath "$5")
fi

case "$SOURCE" in
  /mnt/cache/little-orbit-deploy/repo) ;;
  /mnt/cache/little-orbit-deploy/android-signing-drills/little-orbit-*)
    test "$(dirname "$SOURCE")" = "/mnt/cache/little-orbit-deploy/android-signing-drills" \
      || { echo "unsafe disposable source path" >&2; exit 2; }
    ;;
  *) echo "unsafe source path" >&2; exit 2 ;;
esac
if test "$MODE" = "release"; then
  case "$CANDIDATE" in /mnt/cache/little-orbit-live/release-work/*) ;; *) echo "unsafe candidate path" >&2; exit 2 ;; esac
  case "$SIGNED" in /mnt/cache/little-orbit-live/release-work/*) ;; *) echo "unsafe signed path" >&2; exit 2 ;; esac
fi
case "$BUNDLE" in /mnt/cache/vault/little-orbit/android-signing/*) ;; *) echo "unsafe signer bundle path" >&2; exit 2 ;; esac
git -C "$SOURCE" diff --quiet --ignore-submodules --
git -C "$SOURCE" diff --cached --quiet --ignore-submodules --
test -z "$(git -C "$SOURCE" ls-files --others --exclude-standard)"
for protected in "$BUNDLE" "$IDENTITY"; do
  test "$(stat -c %u "$protected")" -eq 0
  case "$(stat -c %a "$protected")" in 400|600) ;; *) echo "protected input must be root-only" >&2; exit 2 ;; esac
done

AGE_BIN=${ANDROID_RELEASE_AGE_BIN:-/mnt/cache/little-orbit-tools/bin/age}
case "$AGE_BIN" in /*) ;; *) echo "ANDROID_RELEASE_AGE_BIN must be absolute" >&2; exit 2 ;; esac
test -x "$AGE_BIN" || { echo "the pinned age binary is unavailable" >&2; exit 2; }

SECRET_BASE=/dev/shm/little-orbit-signing
SOURCE_BASE=/dev/shm/little-orbit-source
for base in "$SECRET_BASE" "$SOURCE_BASE"; do
  test ! -L "$base"
  mkdir -p "$base"
  test "$(stat -c %u "$base")" -eq 0
  chmod 0700 "$base"
done
SECRET_ROOT=$(mktemp -d "$SECRET_BASE/little-orbit.XXXXXX")
BUILD_SOURCE=
cleanup() {
  case "$SECRET_ROOT" in "$SECRET_BASE"/little-orbit.*) find "$SECRET_ROOT" -depth -delete ;; esac
  case "${BUILD_SOURCE:-}" in "$SOURCE_BASE"/little-orbit.*) find "$BUILD_SOURCE" -depth -delete ;; esac
}
trap cleanup EXIT HUP INT TERM
umask 077

build_image() {
  target="$1"
  tag="$2"
  iid_file="$SECRET_ROOT/${target}.iid"
  docker build --target "$target" --tag "$tag" --iidfile "$iid_file" \
    "$SOURCE/android-release" >&2
  image_id=$(tr -d '\r\n' <"$iid_file")
  rm -f -- "$iid_file"
  printf '%s\n' "$image_id" | grep -Eq '^sha256:[0-9a-f]{64}$' \
    || { echo "Docker did not return an immutable image ID" >&2; exit 2; }
  test "$(docker image inspect --format '{{.Id}}' "$image_id")" = "$image_id"
  printf '%s\n' "$image_id"
}

SIGNER_IMAGE=$(build_image signer little-orbit-android-signer:1)
if test "$MODE" = "release"; then
  BUILD_SOURCE=$(mktemp -d "$SOURCE_BASE/little-orbit.XXXXXX")
  mkdir -p "$CANDIDATE" "$SIGNED"
  test -z "$(find "$CANDIDATE" -mindepth 1 -maxdepth 1 -print -quit)"
  test -z "$(find "$SIGNED" -mindepth 1 -maxdepth 1 -print -quit)"
  git -C "$SOURCE" archive --format=tar HEAD | tar -x -C "$BUILD_SOURCE"
  BUILDER_IMAGE=$(build_image builder little-orbit-android-builder:1)
  docker run --rm \
    --mount "type=bind,src=$BUILD_SOURCE,dst=/src,readonly" \
    --mount "type=bind,src=$CANDIDATE,dst=/out" \
    --tmpfs /work:exec,size=8g \
    "$BUILDER_IMAGE"
fi

SECRET_ARCHIVE="$SECRET_ROOT/signer.tar"
"$AGE_BIN" --decrypt --identity "$IDENTITY" "$BUNDLE" >"$SECRET_ARCHIVE"
test "$(tar -tf "$SECRET_ARCHIVE" | LC_ALL=C sort)" = "$(printf '%s\n' \
  key-alias key-password release.p12 store-password | LC_ALL=C sort)"
tar --extract --file "$SECRET_ARCHIVE" --directory "$SECRET_ROOT" \
  --no-same-owner --no-same-permissions -- \
  release.p12 store-password key-alias key-password
rm -f -- "$SECRET_ARCHIVE"
test -z "$(find "$SECRET_ROOT" -type l -print -quit)"
test "$(find "$SECRET_ROOT" -type f | wc -l)" -eq 4
chmod 0700 "$SECRET_ROOT"
find "$SECRET_ROOT" -type f -exec chmod 0600 {} +

if test "$MODE" = "verify"; then
  docker run --rm --network none --read-only --cap-drop ALL \
    --security-opt no-new-privileges \
    --entrypoint /opt/release/container-verify-signer.sh \
    --mount "type=bind,src=$SECRET_ROOT,dst=/secrets,readonly" \
    --tmpfs /tmp:exec,size=64m \
    "$SIGNER_IMAGE"
  exit 0
fi

docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges \
  --mount "type=bind,src=$CANDIDATE,dst=/candidate,readonly" \
  --mount "type=bind,src=$SIGNED,dst=/out" \
  --mount "type=bind,src=$SECRET_ROOT,dst=/secrets,readonly" \
  --tmpfs /work:exec,size=1g \
  --tmpfs /tmp:exec,size=64m \
  "$SIGNER_IMAGE"
