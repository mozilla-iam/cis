import boto3
import cis_profile
import datetime
import json
import logging
import requests
import sys
from os import getenv
from requests.auth import HTTPBasicAuth


class hris_processor(object):
    def __init__(self):
        self.logger = self.setup_logging()

    def setup_logging(self, stream=sys.stderr, level=logging.INFO):
        formatstr = "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s"
        logging.basicConfig(format=formatstr, datefmt="%H:%M:%S", stream=stream)
        logger = logging.getLogger(__name__)
        logger.setLevel(level)
        return logger

    def get_secure_parameter(self, parameter_name):
        client = boto3.client('ssm')
        response = client.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']

    def get_file_from_hris(self, username, password, url, path):
        params = dict(format='json')
        route = 'https://{}{}'.format(url, path)
        res = requests.get(
            route,
            auth=HTTPBasicAuth(username, password),
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

    def store_in_s3(self, s3_bucket_name, data):
        if getenv('HRIS_ASSUME_ROLE_ARN', None) is None:
            s3 = boto3.resource('s3')
        else:
            credentials = assume_role()
            boto_session = boto3.session.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
            )
            s3 = boto_session.resource('s3')
        bucket = s3.Bucket(s3_bucket_name)
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
            tzmap = {
                    "GMT United Kingdom Time (London)": "UTC+0000 Europe/London",
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
                    "GMT-08:00 Pacific Time": "UTC-0800 US/Pacific",
                    }
            return tzmap[hris_tz]

        def cost_center_convert(cc):
            return str(int(cc.split(' ')[0]))

        user_array = []
        for hruser in hris_data.get('Report_Entry'):
            p = cis_profile.User()
            # Note: Never use non-preferred names here
            p.primary_email.value = hruser.get('PrimaryWorkEmail')
            p.last_name.value = hruser.get('Preferred_Name_-_Last_Name')
            p.first_name.value = hruser.get('PreferredFirstName')
            p.timezone.value = tz_convert(hruser.get('Time_Zone'))
            p.staff_information.manager.value = bool(hruser.get('IsManager'))
            p.staff_information.director.value = bool(hruser.get('isDirectorOrAbove'))
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
            user_array.append(p)

        return user_array


def handle(event=None, context={}):
    cis_environment = getenv('CIS_ENVIRONMENT', 'development')
    hris_url = get_secure_parameter('/iam/hris-publisher/{}/hris_url'.format(cis_environment))
    hris_path = get_secure_parameter('/iam/hris-publisher/{}/hris_path'.format(cis_environment))
    username = get_secure_parameter('/iam/hris-publisher/{}/hris_user'.format(cis_environment))
    password = get_secure_parameter('/iam/hris-publisher/{}/hris_password'.format(cis_environment))
    s3_bucket = get_secure_parameter('/iam/hris-publisher/{}/hris_bucket'.format(cis_environment))

    hris = hris_processor()
    hris_data = hris.get_file_from_hris(username, password, hris_url, hris_path)
    hris_as_cis_profiles = hris.convert_hris_to_cis_profiles(hris_data)

    #store_in_s3(s3_bucket, bytes(json.dumps(hris_data).encode('utf-8')))
    return 200
