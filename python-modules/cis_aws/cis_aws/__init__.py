# -*- coding: utf-8 -*-

"""Top-level package for iam-profile-faker."""

__author__ = """Andrew Krug"""
__email__ = 'akrug@mozilla.com'
__version__ = '0.0.1'

from everett.manager import ConfigManager
from everett.manager import ConfigOSEnv


def get_config():
    return ConfigManager(
        [
            ConfigOSEnv()
        ]
)
