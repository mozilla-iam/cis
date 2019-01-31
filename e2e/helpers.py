import boto3
import os


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
