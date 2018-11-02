#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = [
    'python-jose[cryptography]==3.0.1',
    'cryptography==2.3.1',
    'everett',
    'boto3==1.7.67', 'boto==2.49.0', 'jsonschema', 'flask',
    'faker'
]

setup_requirements = [
    'pytest-runner',
    'setuptools>=40.5.0'
]

test_requirements = ['pytest', 'pytest-watch', 'pytest-cov', 'pytest-flask', 'flake8']

extras = {'test': test_requirements}

setup(
    name="cis_fake_well_known",
    version="0.0.1",
    author="Andrew Krug",
    author_email="akrug@mozilla.com",
    description="Provides a mock IDP .well-known configuration for testing modules like cryptography.",
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
    packages=find_packages(include=['cis_fake_well_known', 'cis_fake_well_known/keys', 'bin']),
    package_data={'cis_fake_well_known': ['keys/*.pem', 'json/*.json']},
    scripts=['bin/cis_fake_well_known'],
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    extras_require=extras,
    zip_safe=False
)
