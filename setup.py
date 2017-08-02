from distutils.command.build import build
from setuptools import setup
from setuptools.command.install import install as _install

import unittest

def test_suite():
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests', pattern='test_*.py')
    return test_suite

class install(_install):
    def run(self):
        self.run_command('build')
        _install.run(self)

setup(
    name='mozilla-iam-cis',
    version='0.1dev',
    packages=['cis', 'cis/plugins', 'cis/plugins/validation'],
    license='MPL 2.0',
    long_description='Mozilla IAM change integration service',
    include_package_data=True,
    test_suite=('setup.test_suite')
)
