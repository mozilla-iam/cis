#!/bin/bash

echo "Begin deploy of the Mozilla Change Integration Service version 2."
echo "$CODEBUILD_WEBHOOK_TRIGGER"
make login-to-ecr


if [[ "branch/master" == "$CODEBUILD_WEBHOOK_TRIGGER" ]]
	then
		echo "Deploying the development environment."
		make build STAGE=development
		make publish STAGE=development
		make release STAGE=development
elif [[ "$CODEBUILD_WEBHOOK_TRIGGER" =~ ^tag\/[0-9]\.[0-9]\.[0-9](\-(pre|testing))?$ ]]
	then
		echo "Deploying the testing environment."
		make build STAGE=testing
		make publish STAGE=testing
		make release STAGE=testing
elif [[ "$CODEBUILD_WEBHOOK_TRIGGER" =~ ^tag\/[0-9]\.[0-9]\.[0-9](\-(prod))?$ ]]
	then
		echo "Deploying the production environment."
		make build STAGE=production
		make publish STAGE=production
		make release STAGE=production
fi

make build-ci-container
make push-ci-container
echo "$CODEBUILD_WEBHOOK_TRIGGER"
echo "End deploy of the Mozilla Change Integration Service version 2."
