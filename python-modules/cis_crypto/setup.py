#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = ['python-jose-cryptodome', 'python-jose', 'everett', 'boto3==1.7.67', 'boto==2.49.0',
                'botocore==1.10.67', 'requests', 'pyaml']

setup_requirements = ['pytest-runner']

test_requirements = ['pytest', 'pytest-watch', 'pytest-cov', 'pytest-mock', 'moto', 'mock', 'cis_fake_well_known',
                     'flake8']

extras = {'test': test_requirements}

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
    packages=find_packages(include=['cis_crypto', 'bin']),
    scripts=['bin/cis_crypto'],
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    extras_require=extras,
    zip_safe=False
)
