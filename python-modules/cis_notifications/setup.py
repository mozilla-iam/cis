#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = ["everett", "boto3", "configobj"]

setup_requirements = ["pytest-runner", "setuptools>=40.5.0"]

test_requirements = ["pytest", "pytest-watch", "pytest-cov", "patch", "mock", "flake8", "moto", "PyYAML"]

extras = {"test": test_requirements}

setup(
    name="cis_notifications",
    version="0.0.1",
    author="Andrew Krug",
    author_email="akrug@mozilla.com",
    description="Notifies relying parties if there has been an" "update to a user so they may see what has changed.",
    long_description=long_description,
    url="https://github.com/mozilla-iam/cis",
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Mozilla Public License",
        "Operating System :: OS Independent",
    ),
    install_requires=requirements,
    license="Mozilla Public License 2.0",
    include_package_data=True,
    packages=find_packages(include=["cis_notifications"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require=extras,
    zip_safe=False,
)
