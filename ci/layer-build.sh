#!/usr/bin/env bash
# Builds something similar to what we used to, preferring statically linked
# dependencies where possible (specifically psycopg2 and cffi).
#
# This decision vastly simplifies our life, since we no longer need to be
# copying a whole set of `.so`s anywhere, and only care about the one
# directory. At least for now, until I encounter a runtime error.

set -euo pipefail
. ci/layer.inc.sh

case $TARGET_ARCH in
    arm64|x86_64)
        ;;
    *)
        echo Unsupported "$TARGET_ARCH" architecture. Pick either arm64 or x86_64.
        exit 1
        ;;
esac

# shellcheck disable=SC2059
printf "$(< ci/layer-build-header.msg)\n\n" \
    "$HOST_ARCH" \
    "$HOST_DOCKER_SERVER_VERSION" \
    "$TARGET_ARCH" \
    "$TARGET_PYTHON_VERSION" \
    "$TARGET_PYTHON_PIP_VERSION" \
    "$TARGET_OUTPUT"

mkdir -p "$TARGET_OUTPUT"/python/lib

# Clear the previous build, if it exists.
# re: shellcheck: Set above with prefix.
# shellcheck disable=SC2115
rm -fr "$TARGET_OUTPUT"/python/lib/*
rm -f "$TARGET_OUTPUT.zip"

docker buildx build \
    -f ci/Dockerfile.layer \
    --build-arg PYTHON_VERSION="$TARGET_PYTHON_VERSION" \
    --build-arg PYTHON_PIP_VERSION="$TARGET_PYTHON_PIP_VERSION" \
    --platform "linux/$TARGET_ARCH" \
    --iidfile "$TARGET_OUTPUT.image-id" \
    --progress plain \
    .

# DEBT(bhee): maybe someone could write to this file ahead of time? Not sure
# how much effort we want to put into this.
IMAGE_ID="$(< "$TARGET_OUTPUT.image-id")"
CONTAINER_ID="$(docker create --platform "linux/$TARGET_ARCH" "$IMAGE_ID")"

# The container has Python stuff in: /home/build/.local/lib/pythonN.N
docker cp "$CONTAINER_ID:/home/build/.local/lib/python${TARGET_PYTHON_VERSION_SHORT}" "$TARGET_OUTPUT/python/lib"
docker rm -f "$CONTAINER_ID"

cd "$TARGET_OUTPUT" && zip -qr "../$TARGET_NAME.zip" . && cd -
