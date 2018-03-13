# Changelog

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No changes yet_

## [0.1.2.1] - 2017-03-13

### Fixed

- Don't traceback if watchtower is not present.  Closes #103
- Only get a new auth0 bearer token every fifteen minutes or when not present. Closes #104

## [0.1.2] - 2017-03-07

The first release to include a changelog.

### Added

#### Watchtower Support
- Support Consolidated Logging to Single CloudWatch group.
- Fallback to stream logger if cloudwatch params not specified.
- Add requirements to setup.py
- Update requirements.txt

#### Removed

- Abandoned imports
- Pep8 errors
