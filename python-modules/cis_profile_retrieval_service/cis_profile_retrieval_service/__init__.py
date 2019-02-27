# -*- coding: utf-8 -*-
"""API package for api.sso.mozilla.com."""

__version__ = "0.0.1"

from cis_profile_retrieval_service import common
from cis_profile_retrieval_service import exceptions
from cis_profile_retrieval_service import idp
from cis_profile_retrieval_service import schema
from cis_profile_retrieval_service import v2_api


__all__ = [common, exceptions, idp, schema, v2_api, __version__]
