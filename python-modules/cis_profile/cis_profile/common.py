import json
import os
import requests
import requests.exceptions
import requests_cache
import logging

logger = logging.getLogger(__name__)


class DotDict(dict):
    """
    Convert a dict to a fake class/object with attributes, such as:
    test = dict({"test": {"value": 1}})
    test.test.value = 2
    """
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        try:
            # Python2
            for k, v in self.iteritems():
                self.__setitem__(k, v)
        except AttributeError:
            # Python3
            for k, v in self.items():
                self.__setitem__(k, v)

    def __getattr__(self, k):
        try:
            return dict.__getitem__(self, k)
        except KeyError:
            raise AttributeError("'DotDict' object has no attribute '" + str(k) + "'")

    def __setitem__(self, k, v):
        dict.__setitem__(self, k, DotDict.__convert(v))

    __setattr__ = __setitem__

    def __delattr__(self, k):
        try:
            dict.__delitem__(self, k)
        except KeyError:
            raise AttributeError("'DotDict'  object has no attribute '" + str(k) + "'")

    @staticmethod
    def __convert(o):
        """
        Recursively convert `dict` objects in `dict`, `list`, `set`, and
        `tuple` objects to `DotDict` objects.
        """
        if isinstance(o, dict):
            o = DotDict(o)
        elif isinstance(o, list):
            o = list(DotDict.__convert(v) for v in o)
        elif isinstance(o, set):
            o = set(DotDict.__convert(v) for v in o)
        elif isinstance(o, tuple):
            o = tuple(DotDict.__convert(v) for v in o)
        return o


class MozillaDataClassification(DotDict):
    """
    See https://wiki.mozilla.org/Security/Data_Classification
    Just a simple object-enum - it returns all valid labels per level
    as a list/array.
    """
    UNKNOWN = ['UNKNOWN']
    PUBLIC = ['PUBLIC']
    MOZILLA_CONFIDENTIAL = ['MOZILLA CONFIDENTIAL', 'Mozilla Confidential - Staff and NDA\'d Mozillians Only']
    WORKGROUP_CONFIDENTIAL = ['WORKGROUP CONFIDENTIAL', 'Mozilla Confidential - Specific Work Groups Only']
    INDIVIDUAL_CONFIDENTIAL = ['INDIVIDUAL CONFIDENTIAL', 'Mozilla Confidential - Specific Individuals Only']
    # Well-known Workgroups:
    WELL_KNOWN_WORKGROUPS = ['STAFF_ONLY']
    STAFF_ONLY = ['WORKGROUP CONFIDENTIAL: STAFF ONLY']


class WellKnown(object):
    """
    CIS JSON WellKnown and Schema loader with memory and disk cache and builtin fallback support.
    This object cannot fail to return the schema, but the schema is not garanteed to be up to date in case of network
    issues.

    Tries to get the well-known URL and schema from local cache if the cache has not expired.
    Else, tries to get the schema from well-known URL and cache it.
    Else, uses a library-builtin copy of schema.

    Return: dict Schema dictionary (can be converted to JSON)

    Ex:
    import cis_profile.common.WellKnown
    wk = WellKnown
    print(wk.get_schema())
    <Dict: schema>
    """

    def __init__(self, discovery_url='https://auth.mozilla.com/.well-known/mozilla-iam'):
        self._request_cache = '/var/tmp/cis_request_cache'  # XXX use `get_config` to configure that
        self._request_cache_ttl = 3600
        # Memory cached copies
        self._well_known_json = None
        self._schema_json = None
        self.discovery_url = discovery_url

        logger.debug('Initializing requests_cache TTL={} at {}'.format(self._request_cache_ttl, self._request_cache))
        requests_cache.install_cache(self._request_cache, expire_after=self._request_cache_ttl, backend='sqlite')

    def get_publisher_rules(self):
        """
        Public wrapper for _load_rules
        """
        self._well_known_json = self._load_well_known()
        rules_url = self._well_known_json.get('publishers_rules_uri')
        return self._load_publisher_rules(rules_url)

    def get_schema(self):
        """
        Public wrapper for _load_well_known()
        """
        self._well_known_json = self._load_well_known()
        schema_url = self._well_known_json.get('api').get('data/profile_schema')
        return self._load_schema(schema_url, stype='data/profile.schema')

    def get_core_schema(self):
        """ Deprecated """
        return self.get_schema()

    def get_extended_schema(self):
        """ Deprecated """
        return self.get_schema()

    def get_well_known(self):
        """
        Public wrapper for _load_well_known
        """
        return self._load_well_known()

    def _load_publisher_rules(self, rules_url):
        """
        Get the CIS integration rules
        """
        rules = None
        if rules_url is not None:
            try:
                r = requests.get(rules_url)
                rules = r.json()
                if r.from_cache:
                    logger.debug('Loaded rules data from requests cache')
            except (json.JSONDecodeError, requests.exceptions.ConnectionError) as e:
                logger.debug('Failed to load rules data from rules_url {} ({})'.format(rules_url, e))

        # Fall-back to built-in copy
        if rules is None:
            rules_file = 'data/well-known/mozilla-iam-publisher-rules'
            if not os.path.isfile(rules_file):
                dirname = os.path.dirname(os.path.realpath(__file__))
                path = dirname + '/' + rules_file
            else:
                path = rules_file

            rules = json.load(open(path))
        return rules

    def _load_well_known(self):
        """
        Gets the discovery url's data ("well-known")
        Return dict,None the well-known JSON data copy
        """
        # Memory cache
        if self._well_known_json is not None:
            return self._well_known_json

        try:
            r = requests.get(self.discovery_url)
            self._well_known_json = r.json()
            if r.from_cache:
                logger.debug('Loaded well-known url from requests cache')
        except (json.JSONDecodeError, requests.exceptions.ConnectionError) as e:
            logger.debug('Failed to fetch schema url from discovery {} ({})'.format(self.discovery_url, e))
            logger.debug('Using builtin copy')
            well_known_file = 'data/well-known/mozilla-iam'  # Local fall-back
            if not os.path.isfile(well_known_file):
                dirname = os.path.dirname(os.path.realpath(__file__))
                path = dirname + '/' + well_known_file
            else:
                path = well_known_file
            self._well_known_json = json.load(open(path))

        return self._well_known_json

    def _load_schema(self, schema_url, stype='data/profile.schema'):
        """
        Loads JSON Schema from an URL
        @schema_url: str,None the schema URL
        @stype: str, type of schema to load. This is also the name of the library builtin, local copy.
        Return dict JSON object which is the CIS Profile Schema
        """
        schema = None
        if schema_url is not None:
            try:
                r = requests.get(schema_url)
                schema = r.json()
                if r.from_cache:
                    logger.debug('Loaded schema data from requests cache')
            except (json.JSONDecodeError, requests.exceptions.ConnectionError) as e:
                logger.debug('Failed to load schema from schema_url {} ({})'.format(schema_url, e))

        # That did not work, fall-back to local, built-in copy
        if schema is None:
            # Builtin, hardcoded schema from library
            schema_file = stype
            if not os.path.isfile(schema_file):
                dirname = os.path.dirname(os.path.realpath(__file__))
                path = dirname + '/' + schema_file
            else:
                path = schema_file

            schema = json.load(open(path))
        return schema
