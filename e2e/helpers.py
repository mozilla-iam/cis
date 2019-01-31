import boto3
import os
import random
import cis_crypto
from cis_profile import common
from cis_profile import profile


def get_cis_environment():
    return os.getenv("CIS_ENVIRONMENT", "development")

def get_client_id_path():
    return "/iam/cis/{}/change_client_id".format(get_cis_environment())

def get_client_secret_path():
    return "/iam/cis/{}/change_service_client_secret".format(get_cis_environment())

def get_url_dict():
    cis_environment = get_cis_environment()

    if cis_environment == 'development':
        change_url = "change.api.dev.sso.allizom.org"
        person_url = "person.api.dev.sso.allizom.org"
        audience = "api.dev.sso.allizom.org"

    if cis_environment == 'testing':
        change_url = "change.api.test.sso.allizom.org"
        person_url = "person.api.test.sso.allizom.org"
        audience = "api.test.sso.allizom.org"

    if cis_environment == 'production':
        change_url = "change.api.sso.allizom.org"
        person_url = "person.api.sso.allizom.org"
        audience = "api.sso.allizom.org"

    return dict(
        change=change_url,
        person=person_url,
        audience=audience
    )

def get_secure_parameter(parameter_name):
    client = boto3.client("ssm")
    response = client.get_parameter(Name=parameter_name, WithDecryption=True)
    return response["Parameter"]["Value"]

def get_client_secret():
    return get_secure_parameter(get_client_secret_path())

def get_client_id():
    return get_secure_parameter(get_client_id_path())

def get_complex_structures():
    return [
        'staff_information',
        'access_information',
        'identities',
        'schema'
    ]

def ensure_appropriate_publishers_and_sign(fake_profile, condition):
    os.environ['CIS_SECRET_MANAGER'] = 'aws-ssm'
    os.environ['CIS_SECRET_MANAGER_SSM_PATH'] = '/iam/cis/{}'.format(os.getenv('CIS_ENVIRONMENT', 'development'))

    publisher_rules = common.WellKnown().get_publisher_rules()
    complex_structures = get_complex_structures()

    temp_profile = fake_profile.as_dict()
    for attr in publisher_rules[condition]:
        if attr not in complex_structures:
            successful_random_publisher = random.choice(publisher_rules[condition][attr])
            temp_profile[attr]['signature']['publisher']['name'] = successful_random_publisher
            os.environ['CIS_SIGNING_KEY_NAME'] = 'mozilliansorg_signing_key'
            u = profile.User(user_structure_json=temp_profile)
            if successful_random_publisher == 'mozilliansorg':
                os.environ['CIS_SIGNING_KEY_NAME'] == 'mozilliansorg_signing_key'
            if successful_random_publisher == 'hris':
                os.environ['CIS_SIGNING_KEY_NAME'] = 'hris_signing_key'
            if successful_random_publisher == 'ldap':
                os.environ['CIS_SIGNING_KEY_NAME'] = 'ldap_signing_key'
            if successful_random_publisher == 'cis':
                os.environ['CIS_SIGNING_KEY_NAME'] = 'change_service_signing_key'
            if successful_random_publisher  == 'access_provider':
                os.environ['CIS_SIGNING_KEY_NAME'] = 'auth0_signing_key'
            u.sign_attribute(attr, successful_random_publisher)
            temp_profile = u.as_dict()
        else:
            if attr != 'schema' and attr in complex_structures:
                for k in temp_profile[attr]:
                    if attr == 'access_information':
                        successful_random_publisher = random.choice(publisher_rules[condition][attr][k])

                    if attr == 'staff_information' or attr == 'identities':
                        successful_random_publisher = random.choice(publisher_rules[condition][attr])

                    if successful_random_publisher == 'mozilliansorg':
                        os.environ['CIS_SIGNING_KEY_NAME'] == 'mozilliansorg_signing_key'
                    if successful_random_publisher == 'hris':
                        os.environ['CIS_SIGNING_KEY_NAME'] = 'hris_signing_key'
                    if successful_random_publisher == 'ldap':
                        os.environ['CIS_SIGNING_KEY_NAME'] = 'ldap_signing_key'
                    if successful_random_publisher == 'cis':
                        os.environ['CIS_SIGNING_KEY_NAME'] = 'change_service_signing_key'
                    if successful_random_publisher  == 'access_provider':
                        os.environ['CIS_SIGNING_KEY_NAME'] = 'auth0_signing_key'

                    temp_profile[attr][k]['signature']['publisher']['name'] = successful_random_publisher
                    u = profile.User(user_structure_json=temp_profile)

                    attribute = '{}.{}'.format(attr, k)
                    u.sign_attribute(attribute, successful_random_publisher)

                    from pprint import pprint
                    print(pprint(u.as_dict()))
                    temp_profile = u.as_dict()

    return profile.User(user_structure_json=temp_profile)
