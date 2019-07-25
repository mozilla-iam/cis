#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = ["everett", "everett[ini]", "configobj", "boto", "boto3", "botocore", "sqlalchemy", "psycopg2"]

setup_requirements = ["pytest-runner", "setuptools>=40.5.0"]

test_requirements = ["pytest", "pytest-watch", "pytest-cov", "patch", "mock", "moto>=1.3.7", "flake8"]

extras = {"test": test_requirements}

setup(
    name="cis_identity_vault",
    version="0.0.1",
    author="Andrew Krug",
    author_email="akrug@mozilla.com",
    description="Creates a dynamodb table for the environment for CIS.",
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
    packages=find_packages(include=["cis_identity_vault", "cis_identity_vault.models"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require=extras,
    zip_safe=False,
)
