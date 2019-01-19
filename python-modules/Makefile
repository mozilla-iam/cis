MODULES	:= cis_aws cis_change_service cis_crypto cis_identity_vault \
cis_processor cis_profile cis_profile_retrieval_service cis_publisher

all:
	@echo 'Available make targets:'
	@grep '^[^#[:space:]].*:' Makefile

install: $(MODULES)

build: $(MODULES)

test: tests
tests: $(MODULES)

test-tox: $(MODULES)

clean: $(MODULES)

$(MODULES):
	$(MAKE) $(MAKECMDGOALS) -C $@

.PHONY: test tests clean all install $(MODULES)
