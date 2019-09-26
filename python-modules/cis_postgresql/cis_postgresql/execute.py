"""Allows the execution of complex queries against postgres."""
import operator
import sqlalchemy
import unicodedata
from cis_identity_vault.models import rds
from sqlalchemy.dialects.postgresql import JSON, TEXT

def attr_single_or_multi(attr):
    """[return value or values for an attribute for use in queries]
    
    Arguments:
        attr {string} -- [name of the attribute]
    """

    values = [
        'usernames', 'ssh_public_keys', 
        'pgp_public_keys', 'access_information', 
        'access_information.ldap', 'access_information.mozilliansorg',
        'access_information.hris', 'access_information.access_provider',
        'languages', 'tags', 'uris', 'phone_numbers', 'usernames',
    ]

    if attr in values:
        return 'values'
    else:
        return 'value'
    pass

def raw_query(conn, sql_statement):
    """[Execute a raw sql query against the database.]
    
    Arguments:
        conn {object} -- [A sqlalchemy connection object]
        sql_statement {[string]} -- [The sql query to execute.]
    """
    result = None
    result = conn.execute(sql_statement)
    return result.fetchall()

def sql_alchemy_select(
    engine, attr, comparator, stringified_operator, start=None, end=None, full_profiles=False
):
    """[Execute a sqlalchemy style filter by against the database.]
    
    Arguments:
        conn {object} -- [A sqlalchemy connection object.]
        attr {string} -- [attribute that we are querying against.]
        comparator {string} -- [thing that we must equal.]
        stringified_operator {string} -- [what kind of operation are we performing.]
        start {int} -- [used in paginator slices.]
        stop {int} -- [used in paginator slices.]
        full_profiles {bool} -- [should we return full profiles or usernames only.]
    """
    comparator_key = attr_single_or_multi(attr)
    result = None
    Session = sqlalchemy.orm.sessionmaker(bind=engine)
    session = Session()

    allowed_operators = ['not', 'empty', 'contains']

    max_records_to_return = 50 # for a paginated query

    if stringified_operator not in allowed_operators:
        raise ValueError(f'Operator {stringified_operator} not allowed for query.')

    if attr == 'active':
        if stringified_operator == 'contains':
            result = session.query(
                rds.People
            ).filter(
                rds.People.profile[('active', 'value')].astext.cast(sqlalchemy.types.BOOLEAN) == bool(comparator)
            )
        elif stringified_operator == 'not':
            result = session.query(
                rds.People
            ).filter(
                rds.People.profile[('active', 'value')].astext.cast(sqlalchemy.types.BOOLEAN) != bool(comparator)
            )
        elif stringified_operator == 'empty':
            result = session.query(
                rds.People
            ).filter(
                rds.People.profile[('active', 'value')].astext == None or \
                    rds.People.profile[('active', 'value')].astext == ''
            )
        else:
            result = []
    elif attr.startswith('access_information.'):
        access_provider = attr.split('.')[1]
        if access_provider == 'ldap':
            if stringified_operator == 'contains':
                result = session.query(
                    rds.People
                ).filter(
                    rds.People.profile[('access_information', 'ldap', 'values')].astext.contains(comparator)
                )
            elif stringified_operator == 'not':
                # Future feature
                pass
            elif stringified_operator == 'empty':
                # Future feature
                pass
            else:
                result = []
        elif access_provider == 'mozilliansorg':
            if stringified_operator == 'contains':
                result = session.query(
                    rds.People
                ).filter(
                    rds.People.profile[
                        ('access_information', 'mozilliansorg', 'values')
                    ].astext.contains(comparator)
                )
            elif stringified_operator == 'not':
                # Future feature
                pass
            elif stringified_operator == 'empty':
                # Future feature
                pass
            else:
                result = []
        elif access_provider == 'access_provider':
            # Currently unused.  Reserve for future use.
            pass
        elif access_provider == 'hris':
            # Currently unused. Reserve for future use.
            pass
        else:
            raise ValueError('Access provider not supported.')
    elif attr.startswith == 'staff_information.':
        if stringified_operator == 'contains':
            result = session.query(
                rds.People
            ).filter(
                rds.People.profile[('staff_information', 'values')].astext.contains(comparator)
            )
        elif stringified_operator == 'not':
            # Future feature
            pass
        elif stringified_operator == 'empty':
            # Future feature
            pass
        else:
            result = []
    else:
        raise ValueError(f'Attribute {attr} is not supported.')

    results = []
    if result.count() > 0:
        if full_profiles == True:
            for _ in result:
                results.append(_.profile)
        elif full_profiles == False:
            for _ in result:
                results.append(_.user_id)
        else:
            pass
    return results
