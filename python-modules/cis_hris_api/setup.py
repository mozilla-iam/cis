#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = [
    'python-jose==3.0.1',
    'cryptography==2.3.1',
    'boto>=2.36.0',
    'boto3>=1.6.16',
    'botocore>=1.12.13',
    'everett==0.9',
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
    'moto>=1.3.7',
    'mock',
    'flake8'
]

extras = {'test': test_requirements}

setup(
    name="cis_profile_retrieval_service",
    version="0.0.1",
    author="Andrew Krug",
    author_email="akrug@mozilla.com",
    description="Flask bindings for providing hris-api.sso.mozilla.com",
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
    packages=find_packages(include=['cis_hris_api']),
    scripts=['bin/cis_hris_api'],
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    extras_require=extras,
    zip_safe=False
)
