#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = [
    "python-jose[cryptography]",
    "cryptography",
    "everett",
    "everett[ini]",
    "configobj",
    "boto3",
    "boto",
    "botocore",
    "requests",
    "pyaml",
]

setup_requirements = ["pytest-runner", "setuptools>=40.5.0"]

test_requirements = ["pytest", "pytest-watch", "pytest-cov", "pytest-mock", "moto[ssm]<2", "mock<=4.0.2", "flake8",
                     "cis_profile", "botocore<1.23.24", "responses<0.12.1"]

extras = {"test": test_requirements}

setup(
    name="cis_crypto",
    version="0.0.1",
    author="Andrew Krug",
    author_email="akrug@mozilla.com",
    description="Per attribute signature system for jwks sign-verify in mozilla-iam.",
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
    packages=find_packages(include=["cis_crypto", "bin"]),
    scripts=["bin/cis_crypto"],
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require=extras,
    zip_safe=False,
)
