MODULE_NAME	:= $(abspath $(ROOT_DIR))

all:
	@echo 'Available make targets:'
	@grep '^[^#[:space:]].*:' Makefile

install:
	# Installs as egg
	python setup.py install
	# Installs via pip
	pip install .

build:
	python setup.py build

python-venv: venv
venv:
	$(shell [ -d venv ] || python3 -m venv venv)
	echo "# Run this in your shell to activate:"
	echo "source venv/bin/activate"

test: tests
tests:
	python setup.py test
	pip install flake8
	flake8 setup.py
	flake8 tests/*.py
	flake8 $(MODULE_NAME)/*.py

clean:
	rm -rf venv
	rm -rf __pycache__
	rm -rf *.egg-info
	rm -rf .eggs
	rm -rf build
	rm -rf dist

.PHONY: test tests clean all install
