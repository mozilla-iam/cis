ROOT_DIR	:= $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

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

compose-up:
	docker-compose up -f docker/docker-compose/devpreview.yml