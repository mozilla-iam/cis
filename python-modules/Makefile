MODULES	:= $(wildcard cis_*)

all:
	@echo 'Available make targets:'
	@grep '^[^#[:space:]].*:' Makefile

install: $(MODULES)

build: $(MODULES)

test: tests
tests: $(MODULES)

clean: $(MODULES)
	
$(MODULES):
	$(MAKE) $(MAKECMDGOALS) -C $@

.PHONY: test tests clean all install $(MODULES)
