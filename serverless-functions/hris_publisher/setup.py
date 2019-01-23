#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = ["requests", "boto3", "everett", "cis_profile", "authzerolib"]
test_requirements = ["pytest", "pytest-watch", "pytest-cov"]
setup_requirements = ["pytest-runner", "setuptools>=40.5.0"]

extras = {"test": test_requirements}

setup(
    name="serverless_hris_loader",
    version="0.0.1",
    author="Guillaume Destuynder",
    author_email="kang@mozilla.com",
    description="Mozilla IAM HRIS data loader.",
    long_description=long_description,
    url="https://github.com/mozilla-iam/cis",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Operating System :: OS Independent",
    ],
    install_requires=requirements,
    license="Mozilla Public License 2.0",
    packages=find_packages(),
    setup_requires=setup_requirements,
    tests_require=test_requirements,
    extras_require=extras,
    test_suite="tests",
    zip_safe=True,
)
