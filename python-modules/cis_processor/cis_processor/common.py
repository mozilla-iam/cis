# -*- coding: utf-8 -*-

import os

from everett.ext.inifile import ConfigIniEnv
from everett.manager import ConfigManager
from everett.manager import ConfigOSEnv


def get_config():
    return ConfigManager(
        [ConfigIniEnv([os.environ.get("CIS_CONFIG_INI"), "~/.mozilla-cis.ini", "/etc/mozilla-cis.ini"]), ConfigOSEnv()]
    )
