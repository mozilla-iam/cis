#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = [
    'python-jose',
    'cryptography=',
    'boto',
    'boto3',
    'botocore',
    'everett',
    'everett[ini]',
    'configobj',
    'flask',
    'flask_cors',
    'six',
    'flask_restful',
    'flask-graphql',
    'graphene',
    'requests',
    'ipdb',
    'aniso8601'
]

setup_requirements = [
    'pytest-runner',
    'setuptools>=40.5.0'
]

test_requirements = [
    'pytest',
    'pytest-watch',
    'pytest-cov',
    'pytest-mock',
    'moto',
    'mock',
    'flake8',
    'iam-profile-faker'
]

extras = {'test': test_requirements}

setup(
    name="cis_profile_retrieval_service",
    version="0.0.1",
    author="Andrew Krug",
    author_email="akrug@mozilla.com",
    description="Flask bindings for providing api.sso.mozilla.com",
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
    packages=find_packages(include=['cis_profile_retrieval_service']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    extras_require=extras,
    zip_safe=False
)
