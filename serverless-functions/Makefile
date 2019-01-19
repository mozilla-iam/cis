ROOT_DIR		:= $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
LAMBDA_PACKAGE_CMD	:= docker run --rm \
	-e AWS_DEFAULT_REGION=us-west-2 \
	-v ${HOME}/.aws:/root/.aws \
	-v $(ROOT_DIR)/..:/var/task 320464205386.dkr.ecr.us-west-2.amazonaws.com/custom-codebuild-cis-ci:latest

VENV_COMMAND		:= virtualenv venv -p python3
VENV_ACTIVATE		:= source venv/bin/activate
CIS_MODULE_PATH		:= python-modules
PY_DIR			:= /python/lib/site-packages
PIP_CMD			:= pip install --upgrade
LAYER_NAME		:= cis
STAGE			:= ${STAGE}
STAGE			:= $(if $(STAGE),$(STAGE),testing)
AWS_REGION		:= us-west-2

.PHONY:all
all:
	@echo 'Available make targets:'
	@grep '^[^#[:space:]^\.PHONY.*].*:' Makefile
	@echo $(STAGE)

.PHONY:clean-layer
clean-layer:
	rm -rf $(ROOT_DIR)/layer/*
	rm -rf $(ROOT_DIR)/build/*
	rm $(ROOT_DIR)/cis.zip

.PHONY:layer
layer:
	$(LAMBDA_PACKAGE_CMD) \
	/bin/bash -c "$(PIP_CMD) $(CIS_MODULE_PATH)/cis_aws/ \
	$(CIS_MODULE_PATH)/cis_change_service/ \
	$(CIS_MODULE_PATH)/cis_crypto/ \
	$(CIS_MODULE_PATH)/cis_fake_well_known/ \
	$(CIS_MODULE_PATH)/cis_identity_vault/ \
	$(CIS_MODULE_PATH)/cis_processor/ \
	$(CIS_MODULE_PATH)/cis_profile/ \
	$(CIS_MODULE_PATH)/cis_profile_retrieval_service/ \
	$(CIS_MODULE_PATH)/cis_publisher/ \
	serverless_wsgi \
	flask \
	iam-profile-faker -t /var/task/serverless-functions/$(PY_DIR) && \
	ls /var/task/serverless-functions/build/ && \
	zip -r /var/task/serverless-functions/cis.zip /var/task/serverless-functions/build/ && \
	aws lambda publish-layer-version \
	--layer-name $(LAYER_NAME)_$(STAGE) --compatible-runtimes python3.6 \
	--zip-file fileb:///var/task/serverless-functions/cis.zip | \
	jq .LayerVersionArn | xargs -n 1 aws ssm put-parameter \
	--name /iam/cis/$(STAGE)/lambda_layer_arn \
	--overwrite --type String --value "

.PHONY: layer-codebuild
layer-codebuild:
	mkdir -p /tmp/build/$(PYDIR)
	$(PIP_CMD) ../$(CIS_MODULE_PATH)/cis_aws/ \
	../$(CIS_MODULE_PATH)/cis_change_service/ \
	../$(CIS_MODULE_PATH)/cis_crypto/ \
	../$(CIS_MODULE_PATH)/cis_fake_well_known/ \
	../$(CIS_MODULE_PATH)/cis_identity_vault/ \
	../$(CIS_MODULE_PATH)/cis_processor/ \
	../$(CIS_MODULE_PATH)/cis_profile/ \
	../$(CIS_MODULE_PATH)/cis_profile_retrieval_service/ \
	../$(CIS_MODULE_PATH)/cis_publisher/ \
	serverless_wsgi \
	flask \
	iam-profile-faker -t /tmp/build/$(PY_DIR) && \
	cd /tmp/build && zip -r /tmp/cis.zip . && \
	aws lambda publish-layer-version \
	--layer-name $(LAYER_NAME)_$(STAGE) --compatible-runtimes python3.6 \
	--zip-file fileb:///tmp/cis.zip | \
	jq .LayerVersionArn | xargs -n 1 aws ssm put-parameter \
	--name /iam/cis/$(STAGE)/lambda_layer_arn \
	--overwrite --type String --value

.PHONY:package-single-layer
package-single-layer:
	$(LAMBDA_PACKAGE_CMD) \
	$(PIP_CMD) -v $(CIS_MODULE_PATH)/${MODULE}/ -t serverless-functions/$(PY_DIR) --upgrade && \
	zip -r /var/task/serverless-functions/ /var/task/serverless-functions/build/ && \
	aws lambda publish-layer-version \
	--layer-name $(LAYER_NAME)_$(STAGE) --compatible-runtimes python3.6 \
	--zip-file fileb:///var/task/serverless-functions/cis.zip | \
	jq .LayerVersionArn | xargs -n 1 aws ssm put-parameter \
	--name /iam/cis/$(STAGE)/lambda_layer_arn \
	--overwrite --type String --value

.PHONY:deploy-change-service
deploy-change-service:
	cd $(ROOT_DIR)/change && \
	npm install serverless-domain-manager --save-dev && \
	sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY:test-change-service
test-change-service:
	python e2e/test_change_endpoint.py

.PHONY:deploy-ldap-publisher
deploy-ldap-publisher:
	cd $(ROOT_DIR)/ldap-publisher && sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY:deploy-stream-processor
deploy-stream-processor:
	cd $(ROOT_DIR)/stream-processor && sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY:deploy-person-api
deploy-person-api:
	cd $(ROOT_DIR)/profile_retrieval && \
	npm install serverless-domain-manager --save-dev && \
	sls deploy --region $(AWS_REGION) --stage $(STAGE)
