#!/usr/bin/env bash
set -euo pipefail

TARGET_ARCH="${TARGET_ARCH:-x86_64}"
TARGET_PYTHON_VERSION="${TARGET_PYTHON_VERSION:-3.9.23}"
TARGET_PYTHON_VERSION_SHORT="$(echo "$TARGET_PYTHON_VERSION" | cut -d. -f1,2)"
TARGET_PYTHON_VERSION_SHORT_CLEAN="${TARGET_PYTHON_VERSION_SHORT//./}"
TARGET_PYTHON_PIP_VERSION="${TARGET_PYTHON_PIP_VERSION:-25.1.1}"

TARGET_STAGE=development-dirty
if [ -v GITHUB_EVENT_NAME ] && [ -v GITHUB_EVENT ]; then
    case "$GITHUB_EVENT_NAME" in
        push)
            TARGET_STAGE=development
            ;;
        release)
            # DEBT(bhee): one more and we should do the ol' `jq -r to_entries`
            # trick.
            IS_PRERELEASE=$(echo "$GITHUB_EVENT" | jq -r .release.prerelease)
            IS_DRAFT=$(echo "$GITHUB_EVENT" | jq -r .release.draft)
            if [ "$IS_DRAFT" == "false" ] && [ "$IS_PRERELEASE" == "false" ]; then
                TARGET_STAGE=production
            fi
            if [ "$IS_DRAFT" == "false" ] && [ "$IS_PRERELEASE" == "true" ]; then
                TARGET_STAGE=testing
            fi
            ;;
    esac
fi


TARGET_NAME="cis-$TARGET_ARCH-py${TARGET_PYTHON_VERSION_SHORT_CLEAN}-$TARGET_STAGE"
TARGET_OUTPUT="./build/$TARGET_NAME"
TARGET_SSM_PARAMETER="/iam/cis/$TARGET_STAGE/build/lambda_layer_arn"

case "$(uname -m)" in
    # Linux
    aarch64)
        HOST_ARCH="arm64"
        ;;
    *)
        HOST_ARCH="$(uname -m)"
        ;;
esac

HOST_AWS_EFFECTIVE_ROLE="$(aws sts get-caller-identity --output json | jq -r .Arn)"
HOST_DOCKER_SERVER_VERSION="$(docker version -f "{{.Server.Version}}")"

export TARGET_ARCH
export TARGET_PYTHON_VERSION
export TARGET_PYTHON_VERSION_SHORT
export TARGET_PYTHON_PIP_VERSION
export TARGET_STAGE
export TARGET_NAME
export TARGET_OUTPUT
export TARGET_SSM_PARAMETER

export HOST_ARCH
export HOST_AWS_EFFECTIVE_ROLE
export HOST_DOCKER_SERVER_VERSION
