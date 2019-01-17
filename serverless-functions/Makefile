ROOT_DIR		:= $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
LAMBDA_PACKAGE_CMD	:= docker run --rm -v $(ROOT_DIR)/../:/var/task lambci/lambda:build-python3.6
VENV_COMMAND		:= virtualenv venv -p python3
VENV_ACTIVATE		:= source venv/bin/activate
CIS_MODULE_PATH		:= python-modules
PY_DIR			:= build/python/lib/python3.6/site-packages
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

.PHONY:package-layer
package-layer:
	mkdir -p $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) $(CIS_MODULE_PATH)/cis_aws/ -t $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) $(CIS_MODULE_PATH)/cis_change_service/ -t $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) $(CIS_MODULE_PATH)/cis_crypto/ -t $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) $(CIS_MODULE_PATH)/cis_fake_well_known/ -t $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) $(CIS_MODULE_PATH)/cis_identity_vault/ -t $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) $(CIS_MODULE_PATH)/cis_processor/ -t $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) $(CIS_MODULE_PATH)/cis_profile/ -t $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) $(CIS_MODULE_PATH)/cis_profile_retrieval_service/ -t $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) $(CIS_MODULE_PATH)/cis_publisher/ -t $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) serverless_wsgi -t $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) flask -t $(PY_DIR)
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) iam-profile-faker -t $(PY_DIR)

.PHONY:package-single-layer
package-single-layer:
	$(LAMBDA_PACKAGE_CMD) $(PIP_CMD) -v $(CIS_MODULE_PATH)/${MODULE}/ -t $(PY_DIR) --upgrade

.PHONY:zip-layer
zip-layer:
	cd build/ && zip -r $(ROOT_DIR)/cis.zip .

.PHONY:upload-layer
upload-layer:
	aws lambda publish-layer-version \
	--layer-name $(LAYER_NAME)_$(STAGE) --compatible-runtimes python3.6 \
	--zip-file fileb://$(ROOT_DIR)/cis.zip | \
	jq .LayerVersionArn | xargs -n 1 aws ssm put-parameter \
	--name /iam/cis/$(STAGE)/lambda_layer_arn \
	--overwrite --type String --value

.PHONY:deploy-change-service
deploy-change-service:
	cd change && \
	npm install serverless-domain-manager --save-dev && \
	sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY:test-change-service
test-change-service:
	python e2e/test_change_endpoint.py

.PHONY:deploy-ldap-publisher
deploy-ldap-publisher:
	cd ldap-publisher && sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY:deploy-stream-processor
deploy-stream-processor:
	cd stream-processor && sls deploy --region $(AWS_REGION) --stage $(STAGE)

.PHONY:deploy-person-api
deploy-person-api:
	cd profile_retrieval && \
	npm install serverless-domain-manager --save-dev && \
	sls deploy --region $(AWS_REGION) --stage $(STAGE)
