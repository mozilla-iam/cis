# -*- coding: utf-8 -*-

import os

from base64 import b64encode
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


def load_key_file(key_name, key_type, binary=False):
    """Takes key_name and key_type."""
    config = get_config()
    key_dir = config('jwks_key_path', namespace='cis', default=('{}/keys'.format(os.path.dirname(__file__))))
    file_name = '{}.{}.pem'.format(key_name, key_type)
    if binary is False:
        fh = open((os.path.join(key_dir, file_name)), 'r')
    else:
        fh = open((os.path.join(key_dir, file_name)), 'rb')
    return fh.read()


def encode_key(key_contents):
    try:
        encoded_key = b64encode(key_contents)
    except TypeError:
        encoded_key = b64encode(key_contents.encode())
    return encoded_key
