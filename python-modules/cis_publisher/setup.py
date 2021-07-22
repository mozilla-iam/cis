#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = ["boto3", "botocore", "everett", "everett[ini]", "auth0-python"]

setup_requirements = ["pytest-runner"]

test_requirements = ["pytest", "pytest-watch", "pytest-cov", "moto", "flake8", "mock"]

extras = {"test": test_requirements}

setup(
    name="cis_publisher",
    version="0.0.1",
    author="The Mozilla IAM Team",
    author_email="gdestuynder@mozilla.com",
    description="Publisher module for the CIS API.",
    long_description=long_description,
    url="https://github.com/mozilla-iam/cis",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Mozilla Public License",
        "Operating System :: OS Independent",
    ],
    install_requires=requirements,
    license="Mozilla Public License 2.0",
    include_package_data=True,
    packages=find_packages(include=["cis_publisher"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require=extras,
    zip_safe=False,
)
