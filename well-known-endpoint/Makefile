# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Copyright (c) 2014 Mozilla Corporation
#

ROOT_DIR        := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

AWS_REGION	:= us-west-2
S3_BUCKET_NAME	:= cis-well-known-endpoint
S3_BUCKET_URI   := s3://$(S3_BUCKET_NAME)/

.PHONY:all
all:
	@echo 'Available make targets:'
	@grep '^[^#[:space:]^\.PHONY.*].*:' Makefile

.PHONY: create-s3-bucket
create-s3-bucket:
	@export AWS_REGION=$(AWS_REGION)
	aws s3api create-bucket --bucket $(S3_BUCKET_NAME) --acl public-read --create-bucket-configuration LocationConstraint=$(AWS_REGION)

upload-s3-bucket:
	@export AWS_REGION=$(AWS_REGION)
	aws s3 sync s3/ $(S3_BUCKET_URI) --acl public-read

cloudformation: cloudformation.yml
