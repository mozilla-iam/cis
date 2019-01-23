#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = ["boto", "boto3", "botocore", "everett", "everett[ini]", "configobj"]

setup_requirements = ["pytest-runner", "setuptools>=40.5.0"]

test_requirements = ["jsonschema", "mock", "moto", "pytest", "pytest-watch", "pytest-cov", "flake8"]

extras = {"test": test_requirements}

setup(
    name="cis_aws",
    version="0.0.1",
    author="Andrew Krug",
    author_email="akrug@mozilla.com",
    description="Interop layer for mozilla-iam and AWS use of DynamoDb, Kinesis, and SSM Parameter Store.",
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
    packages=find_packages(include=["cis_aws"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require=extras,
    zip_safe=False,
)
