# -*- coding: utf-8 -*-

"""Top-level package for cis_crypto."""

__author__ = """Andrew Krug"""
__email__ = 'akrug@mozilla.com'
__version__ = '0.0.1'

import os

from everett.manager import ConfigManager
from everett.manager import ConfigIniEnv
from everett.manager import ConfigOSEnv


def get_config():
    return ConfigManager(
        [
            ConfigIniEnv([
                os.environ.get('CIS_CONFIG_INI'),
                '~/.mozilla-cis.ini',
                '/etc/mozilla-cis.ini'
            ]),
            ConfigOSEnv()
        ]
    )


def open_file(file_path):
    pass


def write_file(contents, file_path):
    pass
