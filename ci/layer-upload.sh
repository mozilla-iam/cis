#!/usr/bin/env bash
# Uploads the zip generated from `ci/layer-build.sh`.

set -euo pipefail
. ci/layer.inc.sh

# shellcheck disable=SC2059
printf "$(< ci/layer-upload-header.msg)\n\n" \
    "$HOST_AWS_EFFECTIVE_ROLE" \
    "$TARGET_OUTPUT.zip" \
    "$TARGET_STAGE" \
    "$TARGET_NAME" \
    "$TARGET_SSM_PARAMETER"

AWS_LAMBDA_LAYER_ARN=$(aws lambda publish-layer-version \
    --layer-name "$TARGET_NAME" \
    --compatible-runtimes "python${TARGET_PYTHON_VERSION_SHORT}" \
    --compatible-architectures "$TARGET_ARCH" \
    --description "See https://github.com/mozilla-iam/cis" \
    --zip-file "fileb://$TARGET_OUTPUT.zip" \
    --output json | jq -r .LayerVersionArn)

echo "AWS Lambda Layer ARN: $AWS_LAMBDA_LAYER_ARN"

aws ssm put-parameter \
    --name "$TARGET_SSM_PARAMETER" \
    --type String \
    --overwrite \
    --value "$AWS_LAMBDA_LAYER_ARN"
