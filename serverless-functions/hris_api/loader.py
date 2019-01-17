import boto3
import cis_profile
import json
import logging
import requests
import sys
from authzero import AuthZero
from os import getenv


class cisAPI(object):
    """
    This class requires cis_profile and authzero
    """
    def __init__(self,
                 client_id,
                 client_secret,
                 authorizer_url,
                 api_type="change",
                 well_known="https://auth.allizom.org/.well-known/mozilla-iam"):
        self.logger = self.setup_logging()
        config = {'client_id': client_id, 'client_secret': client_secret, 'uri': authorizer_url}
        self.az = AuthZero(config)
        self.well_known = cis_profile.WellKnown()
        wk = self.well_known.get_well_known()
        self.api_url = wk.api.endpoints[api_type]
        self.api_audience = wk.api.audience

    def setup_logging(self, stream=sys.stderr, level=logging.INFO):
        formatstr = "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s"
        logging.basicConfig(format=formatstr, datefmt="%H:%M:%S", stream=stream)
        logger = logging.getLogger(__name__)
        logger.setLevel(level)
        return logger

    def _check_http_response(self, response):
        """Check that we got a 2XX response from the server, else bail out"""
        if (response.status >= 300) or (response.status < 200):
            self.logger.debug("_check_http_response() HTTP communication failed: {} {}"
                              .format(response.status, response.reason, response.read().decode('utf-8')))
            raise Exception('HTTPCommunicationFailed', (response.status, response.reason))

    def post_profiles(self, profiles):
        """
        @profiles [] list of profiles as cis_profile.User objects
        Return server response as {} dict
        raises HTTPCommunicationFailed on any error
        """
        # Unroll profiles so that we have a list of json documents instead of objects
        json_profiles = []
        for _ in profiles:
            json_profiles = _.as_json()

        # This always gets a fresh or cached valid token (we use authzero lib)
        token_info = self.az.get_access_token()
        headers = {'authorization': "Bearer {}".format(token_info.access_token),
                   'Content-type': 'application/json'}
        print("WOULD POST")
        #res = requests.post("{}/v2/users", self.api_curl, headers=headers, data=json.dumps(json_profiles))
        self._check_http_response(res)
        ret = json.loads(res.read().decode('utf-8'))
        return ret


class hris_processor(object):
    def __init__(self, environment):
        self.cis_environment = environment
        self.logger = self.setup_logging()

    def setup_logging(self, stream=sys.stderr, level=logging.INFO):
        formatstr = "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s"
        logging.basicConfig(format=formatstr, datefmt="%H:%M:%S", stream=stream)
        logger = logging.getLogger(__name__)
        logger.setLevel(level)
        return logger

    def get_parameters(self):
        self.hris_url = self.get_secure_parameter('/iam/hris-publisher/{}/hris_url'.format(self.cis_environment))
        self.hris_path = self.get_secure_parameter('/iam/hris-publisher/{}/hris_path'.format(self.cis_environment))
        self.hris_username = self.get_secure_parameter('/iam/hris-publisher/{}/hris_user'.format(self.cis_environment))
        self.hris_password = self.get_secure_parameter('/iam/hris-publisher/{}/hris_password'
                                                       .format(self.cis_environment))
        self.s3_bucket = self.get_secure_parameter('/iam/hris-publisher/{}/hris_bucket'.format(self.cis_environment))
        self.az_client_id = self.get_secure_parameter('/iam/hris-publisher/{}/client_id'.format(self.cis_environment))
        self.az_client_secret = self.get_secure_parameter('/iam/hris-publisher/{}/client_secret'
                                                          .format(self.cis_environment))
        self.az_url = self.get_secure_parameter('/iam/hris-publisher/{}/authzero_url'.format(self.cis_environment))

    def get_secure_parameter(self, parameter_name):
        self.logger.debug("Getting parameter: ".format(parameter_name))
        client = boto3.client('ssm')
        response = client.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']

    def get_file_from_hris(self):
        params = dict(format='json')
        route = 'https://{}{}'.format(self.hris_url, self.hris_path)
        res = requests.get(
            route,
            auth=requests.auth.HTTPBasicAuth(self.hris_username, self.hris_password),
            params=params
        )
        return res.json()

    def assume_role(self):
        role_arn = getenv('HRIS_ASSUME_ROLE_ARN', None)
        sts = boto3.client('sts')
        credentials = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='cis-hris-loader',
            DurationSeconds=900
        )

        return credentials['Credentials']

    def store_in_s3(self, data):
        if getenv('HRIS_ASSUME_ROLE_ARN', None) is None:
            s3 = boto3.resource('s3')
        else:
            credentials = self.assume_role()
            boto_session = boto3.session.Session(aws_access_key_id=credentials['AccessKeyId'],
                                                 aws_secret_access_key=credentials['SecretAccessKey'],
                                                 aws_session_token=credentials['SessionToken'])
            s3 = boto_session.resource('s3')
        bucket = s3.Bucket(self.s3_bucket_name)
        object = bucket.put_object(
            Body=data,
            Key='workday.json'
        )
        return object

    def convert_hris_to_cis_profiles(self, hris_data):
        """
        @hris_data list dict of HRIS data

        returns: cis_profile.Profile
        """

        def tz_convert(hris_tz):
            tzmap = {"GMT United Kingdom Time (London)": "UTC+0000 Europe/London",
                     "GMT Western European Time (Casablanca)": "UTC+0100 Africa/Casablanca",
                     "GMT+01:00 Central European Time (Amsterdam)": "UTC+0200 Europe/Amsterdam",
                     "GMT+01:00 Central European Time (Berlin)": "UTC+01:00 Europe/Berlin",
                     "GMT+01:00 Central European Time (Oslo)": "UTC+01:00 Europe/Oslo",
                     "GMT+01:00 Central European Time (Paris)": "UTC+01:00 Europe/Paris",
                     "GMT+01:00 Central European Time (Prague)": "UTC+01:00 Europe/Prague",
                     "GMT+01:00 Central European Time (Stockholm)": "UTC+01:00 Europe/Stockholm",
                     "GMT+02:00 Eastern European Time (Athens)": "UTC+02:00 Europe/Athens",
                     "GMT+02:00 Eastern European Time (Bucharest)": "UTC+02:00 Europe/Bucharest",
                     "GMT+02:00 Eastern European Time (Helsinki)": "UTC+02:00 Europe/Helsinki",
                     "GMT+02:00 South Africa Standard Time (Johannesburg)": "UTC+02:00 Africa/Johannesburg",
                     "GMT+03:00 East Africa Time (Nairobi)": "UTC+03:00 Africa/Nairobi",
                     "GMT+03:00 Moscow Standard Time (Moscow)": "UTC+03:00 Europe/Moscow",
                     "GMT+05:30 India Standard Time (Kolkata)": "UTC+05:30 Asia/Kolkata",
                     "GMT+07:00 Western Indonesia Time (Jakarta)": "UTC+07:00 Asia/Jakarta",
                     "GMT+08:00 Australian Western Standard Time (Perth)": "UTC+08:00 Australia/Perth",
                     "GMT+08:00 China Standard Time (Shanghai)": "UTC+08:00 Asia/Shanghai",
                     "GMT+08:00 Taipei Standard Time (Taipei)": "UTC+08:00 Asia/Taipei",
                     "GMT+09:00 Japan Standard Time (Tokyo)": "UTC+09:00 Asia/Tokyo",
                     "GMT+10:00 Australian Eastern Standard Time (Brisbane)": "UTC+10:00 Australia/Brisbane",
                     "GMT+12:00 New Zealand Time (Auckland)": "UTC+12:00 Pacific/Auckland",
                     "GMT-03:00 Argentina Standard Time (Buenos Aires)": "UTC-0300 America/Buenos_Aires",
                     "GMT-03:00 Brasilia Standard Time (Recife)": "UTC-0300 America/Recife",
                     "GMT-04:00 Atlantic Time (Halifax)": "UTC-0400 America/Halifax",
                     "GMT-05:00 Eastern Time": "UTC-0500 US/Eastern",
                     "GMT-06:00 Central Standard Time (Regina)": "UTC-0600 America/Regina",
                     "GMT-06:00 Central Time (Chicago)": "UTC-0600 America/Chicago",
                     "GMT-06:00 Central Time": "UTC-0600 US/Central",
                     "GMT-07:00 Mountain Time": "UTC-0700 US/Mountain",
                     "GMT-08:00 Pacific Time (Los Angeles)": "UTC-0800 America/Los_Angeles",
                     "GMT-08:00 Pacific Time (Tijuana)": "UTC-0800 America/Tijuana",
                     "GMT-08:00 Pacific Time": "UTC-0800 US/Pacific"}
            return tzmap[hris_tz]

        def cost_center_convert(cc):
            """
            Cost centers can have decimal points
            So it's a float
            """
            return str(float(cc.split(' ')[0]))

        def strbool_convert(v):
            return v.lower() in ("yes", "true", "t", "1")

        user_array = []
        for hruser in hris_data.get('Report_Entry'):
            p = cis_profile.User()
            # Note: Never use non-preferred names here
            p.primary_email.value = hruser.get('PrimaryWorkEmail')
            p.last_name.value = hruser.get('Preferred_Name_-_Last_Name')
            p.first_name.value = hruser.get('PreferredFirstName')
            p.timezone.value = tz_convert(hruser.get('Time_Zone'))
            p.staff_information.manager.value = strbool_convert(hruser.get('IsManager'))
            p.staff_information.director.value = strbool_convert(hruser.get('isDirectorOrAbove'))
            if len(hruser.get('EmployeeID')) > 0:
                p.staff_information.staff.value = True
            else:
                p.staff_information.staff.value = False
            p.staff_information.title.value = hruser.get('businessTitle')
            p.staff_information.team.value = hruser.get('Team')
            p.staff_information.cost_center.value = cost_center_convert(hruser.get('Cost_Center'))
            p.staff_information.worker_type.value = hruser.get('WorkerType')
            p.staff_information.wpr_desk_number.value = hruser.get('WPRDeskNumber')
            p.staff_information.office_location.value = hruser.get('LocationDescription')

            p.access_information.hris['values']['employee_id'] = hruser.get('EmployeeID')
            p.access_information.hris['values']['worker_type'] = hruser.get('WorkerType')
            p.access_information.hris['values']['manager_employee_id'] = hruser.get('WorkersManagersEmployeeID')
            p.access_information.hris['values']['egencia_pos_country'] = hruser.get('EgenciaPOSCountry')

            # Typical required user values
            p.active.value = True
            p.initialize_timestamps()
            try:
                p.sign_all(publisher_name='hris')
            except Exception as e:
                self.logger.critical("Profile data signing failed for user {} - skipped signing, verification "
                                     "WILL FAIL ({})".format(p.primary_email.value, e))
            try:
                p.validate()
            except Exception as e:
                self.logger.critical("Profile schema validation failed for user {} - skipped validation, verification "
                                     "WILL FAIL({})".format(p.primary_email.value, e))

            try:
                p.verify_all_publishers(cis_profile.User())
            except Exception as e:
                self.logger.critical("Profile signing failed for user {} - skipped signing, verification "
                                     "WILL FAIL ({})".format(p.primary_email.value, e))
#            print(p.as_json())
            import sys
            sys.exit()
            user_array.append(p)

        return user_array


def handle(event=None, context={}):
    cis_environment = getenv('CIS_ENVIRONMENT', 'development')
    hris = hris_processor(cis_environment)
    hris.get_parameters()
    hris_data = hris.get_file_from_hris()
    hris_as_cis_profiles = hris.convert_hris_to_cis_profiles(hris_data)

    # Compat with person api v1, can be removed when v1 is no longer used XXX
    hris.store_in_s3(bytes(json.dumps(hris_data).encode('utf-8')))

    # How many profiles to send per batch. API Max is 10.
    per_batch = 5

    to_send = []
    p_index = 0
    cis = cisAPI(client_id=hris.az_client_id, client_secret=hris.az_client_secret, authorizer_url=hris.az_url)
    for p_nr in range(0, len(hris_as_cis_profiles)):
        to_send = []
        for _ in range(0, per_batch):
            p_index = p_index + _
            try:
                to_send.append(hris_as_cis_profiles[p_index])
            except IndexError:
                # No more profiles
                break
        cis.post_profiles(to_send)
    return 200

if __name__ == "__main__":
    handle()
