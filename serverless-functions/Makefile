ROOT_DIR		:= $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
LIB_DIR 		:= lib
LAMBDA_PACKAGE_CMD	:= docker run --rm \
	-e AWS_DEFAULT_REGION=us-west-2 \
	-v ${HOME}/.aws:/root/.aws \
	-v $(ROOT_DIR)/..:/var/task 320464205386.dkr.ecr.us-west-2.amazonaws.com/custom-codebuild-cis-ci:latest

VENV_COMMAND		:= virtualenv venv -p python3
VENV_ACTIVATE		:= source venv/bin/activate
CIS_MODULE_PATH		:= python-modules
PY_DIR			:= python/lib/python3.7/site-packages
PIP_CMD			:= pip install --upgrade
LAYER_NAME		:= cis
STAGE			:= ${STAGE}
STAGE			:= $(if $(STAGE),$(STAGE),testing)
AWS_REGION		:= us-west-2
SLS_PATH		:= /node_modules/.bin

.PHONY:all
all:
	@echo 'Available make targets:'
	@grep '^[^#[:space:]^\.PHONY.*].*:' Makefile
	@echo $(STAGE)

.PHONY:clean-layer
clean-layer:
	rm -rf /tmp/build/layer/*
	rm -rf /tmp/build/build/*
	rm -f /tmp/build/cis.zip

.PHONY:layer
layer:
	@echo "Looking for the layer MakeTarget?  It's no longer supported.  Only run inside of Docker."

.PHONY: layer-codebuild
layer-codebuild:
	mkdir -p /tmp/build/$(PYDIR)
	mkdir -p /tmp/build/$(LIB_DIR)
	cp -ar /postgresql-11.1/lib/* /tmp/build/$(LIB_DIR)
	$(PIP_CMD) ../$(CIS_MODULE_PATH)/cis_aws/ \
	../$(CIS_MODULE_PATH)/cis_change_service/ \
	../$(CIS_MODULE_PATH)/cis_crypto/ \
	../$(CIS_MODULE_PATH)/cis_identity_vault/ \
	../$(CIS_MODULE_PATH)/cis_processor/ \
	../$(CIS_MODULE_PATH)/cis_profile/ \
	../$(CIS_MODULE_PATH)/cis_profile_retrieval_service/ \
	../$(CIS_MODULE_PATH)/cis_publisher/ \
	../$(CIS_MODULE_PATH)/cis_logger/ \
	../$(CIS_MODULE_PATH)/cis_notifications/ \
	../$(CIS_MODULE_PATH)/cis_postgresql/ \
	serverless_wsgi \
	flask \
	iam-profile-faker -t /tmp/build/$(PY_DIR) && \
	cp -r /psycopg2-2.8.3/build/lib.linux-x86_64-3.7/psycopg2 /tmp/build/$(PY_DIR) && \
	cd /tmp/build && zip -r /tmp/cis.zip .

.PHONY: publish-layer
publish-layer:
	@echo "Attempting to publish the layer using the local non-docker aws cli"
	aws lambda publish-layer-version \
	--layer-name $(LAYER_NAME)_$(STAGE) --compatible-runtimes python3.6 python3.7 \
	--zip-file fileb:///$(ROOT_DIR)/build/cis.zip | \
	jq .LayerVersionArn | xargs -n 1 aws ssm put-parameter \
	--name /iam/cis/$(STAGE)/lambda_layer_arn \
	--overwrite --type String --value

.PHONY: build-without-publish
build-without-publish: layer-codebuild 
	mkdir -p /var/task/serverless-functions/build
	mv /tmp/cis.zip /var/task/serverless-functions/build
	@echo "The layer has been built and waits in serverless-functions/build/"

.PHONY: package-single-layer
package-single-layer:
	mkdir -p /tmp/build/$(LIB_DIR)
	cp -ar /postgresql-11.1/lib/* /tmp/build/$(LIB_DIR)
	$(LAMBDA_PACKAGE_CMD) \
	$(PIP_CMD) -v $(CIS_MODULE_PATH)/${MODULE}/ -t serverless-functions/$(PY_DIR) --upgrade && \
	zip -r /var/task/serverless-functions/ /var/task/serverless-functions/build/ && \
	aws lambda publish-layer-version \
	--layer-name $(LAYER_NAME)_$(STAGE) --compatible-runtimes python3.6 python3.7 \
	--zip-file fileb:///var/task/serverless-functions/cis.zip | \
	jq .LayerVersionArn | xargs -n 1 aws ssm put-parameter \
	--name /iam/cis/$(STAGE)/lambda_layer_arn \
	--overwrite --type String --value

.PHONY: deploy-change-service
deploy-change-service:
	cd $(ROOT_DIR)/change && \
	npm install serverless-domain-manager --save-dev serverless-plugin-tracing && \
	npm install serverless-domain-manager --save-dev && \
	$(SLS_PATH)/sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY: test-change-service
test-change-service:
	python e2e/test_change_endpoint.py

.PHONY: deploy-ldap-publisher
deploy-ldap-publisher:
	cd $(ROOT_DIR)/ldap_publisher && \
	npm install serverless-domain-manager --save-dev serverless-plugin-tracing && \
	npm install serverless-domain-manager --save-dev && \
	$(SLS_PATH)/sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY: deploy-hris-publisher
deploy-hris-publisher:
	cd $(ROOT_DIR)/hris_publisher && \
	npm install serverless-domain-manager --save-dev serverless-plugin-tracing && \
	npm install serverless-domain-manager --save-dev && \
	$(SLS_PATH)/sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY: deploy-mozilliansorg-groups-publisher
deploy-mozilliansorg-groups-publisher:
	cd $(ROOT_DIR)/mozilliansorg_groups_publisher && \
	npm install serverless-domain-manager --save-dev serverless-plugin-tracing && \
	npm install serverless-domain-manager --save-dev && \
	$(SLS_PATH)/sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY: deploy-auth0-publisher
deploy-auth0-publisher:
	cd $(ROOT_DIR)/auth0_publisher && \
	npm install serverless-domain-manager --save-dev serverless-plugin-tracing && \
	npm install serverless-domain-manager --save-dev && \
	$(SLS_PATH)/sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY: deploy-stream-processor
deploy-stream-processor:
	cd $(ROOT_DIR)/stream-processor && sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY: deploy-person-api
deploy-person-api:
	cd $(ROOT_DIR)/profile_retrieval && \
	npm install serverless-domain-manager --save-dev serverless-plugin-tracing && \
	npm install serverless-domain-manager --save-dev && \
	$(SLS_PATH)/sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY: deploy-notifications
deploy-notifications:
	cd $(ROOT_DIR)/webhook_notifier && \
	npm install serverless-domain-manager --save-dev serverless-plugin-tracing && \
	$(SLS_PATH)/sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY: deploy-curator
deploy-curator:
	cd $(ROOT_DIR)/identity_vault_curator && \
	npm install serverless-domain-manager --save-dev serverless-plugin-tracing && \
	$(SLS_PATH)/sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY: deploy-postgresql-replicator
deploy-postgresql-replicator:
	cd $(ROOT_DIR)/postgresql_replicator && \
	npm install serverless-domain-manager --save-dev serverless-plugin-tracing && \
	$(SLS_PATH)/sls deploy --region $(AWS_REGION) --stage $(STAGE)

