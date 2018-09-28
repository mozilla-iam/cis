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


def load_file(file_path):
    with open(file_path) as fh:
        return fh.read()


def write_file(file_content, file_name):
    with open(file_name, 'w') as fh:
        fh.write(file_content)
        fh.close()
