all:
	@echo 'Available make targets:'
	@grep '^[^#[:space:]].*:' Makefile

validate: user_profile_core.json user_profile_core_plus_extended.json profile.schema profile_extended.schema profile_core.schema
	@echo validating test profile with core schema...
	jsonschema -i user_profile_core.json profile_core.schema
	@echo validating test profile with core+extended schema...
	jsonschema -i user_profile_core_plus_extended.json profile.schema

test-convert-yml-to-json: user_profile_core_plus_extended.yml
	python -c 'import yaml, json; print(json.dumps(yaml.load(open("user_profile_core_plus_extended.yml")), indent=4))'

test-convert-json-to-yml: user_profile_core_plus_extended.json
	python -c 'import sys,yaml,json; print(yaml.dump(json.load(open("user_profile_core_plus_extended.json")), sys.stdout))'
