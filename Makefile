ROOT_DIR	:= $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
STAGE			:= ${STAGE}
STAGE			:= $(if $(STAGE),$(STAGE),testing)

all:
	@echo 'Available make targets:'
	@grep '^[^#[:space:]].*:' Makefile

docker-build:
	docker build -t mozillaiam/cis-dev-preview:latest .

docker-run:
	@echo "Starting Docker..."
	@echo "/!\ Creating a fake database of users WILL TAKE SOME TIME."
	@echo "/!\ Wait a bit before querying the service!"
	docker run -p 80:80 \
	  -e AWS_ACCESS_KEY_ID="fake" \
	  -e AWS_SECRET_ACCESS_KEY="fake" \
	  -e AWS_DEFAULT_REGION="us-west-2" \
	  -ti mozillaiam/cis-dev-preview:latest supervisord -c /opt/cis/conf/supervisor.conf

preview-shell:
	docker run -ti mozillaiam/cis-dev-preview:latest /bin/bash

setup-codebuild:
	sudo apt-get update
	curl -sL https://deb.nodesource.com/setup_11.x | sudo -E bash -
	sudo npm install -g serverless
	sudo npm install -g serverless-domain-manager
	sudo pip install boto3
	sudo pip install awscli

.PHONY: build
build:
	$(MAKE) -C serverless-functions package-layer STAGE=$(STAGE)
	$(MAKE) -C serverless-functions zip-layer STAGE=$(STAGE)

.PHONY: release
release:
	$(MAKE) -C serverless-functions upload-layer STAGE=$(STAGE)
	$(MAKE) -C serverless-functions deploy-change-service STAGE=$(STAGE)
	$(MAKE) -C serverless-functions deploy-person-api STAGE=$(STAGE)
