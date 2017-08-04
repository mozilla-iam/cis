import logging
import os

from pluginbase import PluginBase


logger = logging.getLogger(__name__)


class Schema(object):
    def __init__(self, publisher, profile_data, user=None):
        """Validates a user profile against the JSON schema using a predefined set of plugins."""
        # List of plugins to load, in order
        self.plugin_load = ['json_schema_plugin', 'mozilliansorg_publisher_plugin']
        self.plugin_source = self._initialize_plugin_source()
        self.profile_data = profile_data
        self.publisher = publisher
        self.user = user

    def validate(self):
        with self.plugin_source:
            for plugin in self.plugin_load:
                cur_plugin = self.plugin_source.load_plugin(plugin)
                try:
                    if cur_plugin.run(self.publisher, self.user, self.profile_data) is False:
                        return False
                    else:
                        pass
                except Exception as e:
                    logger.exception(
                        'Validation plugin {name} failed : {error}'.format(
                            name=cur_plugin.__name__,
                            error=e
                        )
                    )
                    return False
        return True

    def _initialize_plugin_source(self):
        plugin_base = PluginBase(package='cis.plugins.validation')
        plugin_source = plugin_base.make_plugin_source(
            searchpath=[
                os.path.join(
                    os.path.abspath(
                        os.path.dirname(__file__)
                    ),
                    '../plugins/validation/'
                )
            ]
        )

        return plugin_source


class Operation(object):
    """Guaranteed object for performing validation steps."""
    def __init__(self, publisher, profile_data, user=None):
        self.publisher = publisher
        self.profile_data = profile_data
        self.user = user

    def is_valid(self):
        """Source of truth for all validation options."""
        s = Schema(self.publisher, self.profile_data, self.user)

        if s.validate() is True:
            return True
        else:
            return False
