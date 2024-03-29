#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = ["everett", "boto", "boto3", "botocore"]

setup_requirements = ["pytest-runner", "setuptools>=40.5.0"]

test_requirements = [
    "pytest",
    "pytest-watch",
    "pytest-cov",
    "patch",
    "mock",
    "flake8",
    "moto",
    "docker",
    "psycopg2",
    "psycopg2-binary",
]

extras = {"test": test_requirements}

setup(
    name="cis_postgresql",
    version="0.0.1",
    author="Andrew Krug",
    author_email="akrug@mozilla.com",
    description="Takes a user profile from the stream and sends to postgresql for storage.",
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
    packages=find_packages(include=["cis_postgresql"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require=extras,
    zip_safe=False,
)
