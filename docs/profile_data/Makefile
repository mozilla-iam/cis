all:
	@echo 'Available make targets:'
	@grep '^[^#[:space:]].*:' Makefile

validate-schema-are-json: $(wildcard *.schema)
	for schema in $^; do \
	  echo "Validating " $$schema ; \
	  python -m json.tool $$schema > /dev/null; \
	done

validate-profiles-are-json: $(wildcard *.json)
	for profile in $^; do \
	  echo "Validating " $$profile ; \
	  python -m json.tool $$profile > /dev/null; \
	done

validate-core-test-profile: user_profile_core.json profile_core.schema
	jsonschema -i user_profile_core.json profile_core.schema

validate-core-plus-extended-test-profile: profile.schema user_profile_core_plus_extended.json
	jsonschema -i user_profile_core_plus_extended.json profile.schema

validate-core-plus-extended-null-test-profile: profile.schema user_profile_core_plus_extended_null.json
	jsonschema -i user_profile_core_plus_extended_null.json profile.schema

test-convert-yml-to-json: user_profile_core_plus_extended.yml
	python -c 'import yaml, json; print(json.dumps(yaml.load(open("user_profile_core_plus_extended.yml")), indent=4))'

test-convert-json-to-yml: user_profile_core_plus_extended.json
	python -c 'import sys,yaml,json; print(yaml.dump(json.load(open("user_profile_core_plus_extended.json")), sys.stdout))'

.PHONY: all test-convert-yml-to-json test-convert-json-to-yml
