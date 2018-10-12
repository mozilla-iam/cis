ROOT_DIR	:= $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

all:
	@echo 'Available make targets:'
	@grep '^[^#[:space:]].*:' Makefile

docker-build:
	docker build -t mozillaiam/cis-dev-preview:latest .

preview-shell:
	docker run -ti mozillaiam/cis-dev-preview:latest /bin/bash

compose-up:
	docker-compose up -f docker/docker-compose/devpreview.yml
