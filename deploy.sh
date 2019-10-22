#!/bin/bash

echo "Begin deploy of the Mozilla Change Integration Service version 2."
echo "$CODEBUILD_WEBHOOK_TRIGGER"
make login-to-ecr

mkdir -p ~/.aws/
echo '[default]' >> ~/.aws/credentials
echo aws_access_key_id = $AWS_ACCESS_KEY_ID >> ~/.aws/credentials
echo aws_secret_access_key = $AWS_SECRET_ACCESS_KEY >> ~/.aws/credentials
echo aws_session_token = $AWS_SESSION_TOKEN >> ~/.aws/credentials

echo '[default]' >> ~/.aws/config
echo 'region = us-west-2' >> ~/.aws/config
echo 'output = json' >> ~/.aws/config

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
