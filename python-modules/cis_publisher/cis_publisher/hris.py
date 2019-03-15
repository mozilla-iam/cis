import cis_profile
import cis_publisher
import logging
import requests
from traceback import format_exc

logger = logging.getLogger(__name__)


class HRISPublisher:
    def __init__(self):
        self.secret_manager = cis_publisher.secret.Manager()

    def publish(self, user_ids=None):
        """
        Glue to create or fetch cis_profile.User profiles for this publisher
        Then pass everything over to the Publisher class
        None, ALL profiles are sent.
        @user_ids: list of str - user ids to publish. If None, all users are published.
        """
        logger.info("Starting HRIS Publisher")
        report_profiles = self.fetch_report()
        profiles = self.convert_hris_to_cis_profiles(report_profiles, user_ids)
        del report_profiles

        logger.info("Processing {} profiles".format(len(profiles)))

        publisher = cis_publisher.Publish(profiles, publisher_name="hris", login_method="ad")

        failures = []
        try:
            publisher.filter_known_cis_users()
            failures = publisher.post_all(user_ids=user_ids)
        except Exception as e:
            logger.error("Failed to post_all() HRIS profiles. Trace: {}".format(format_exc()))
            raise e

        if len(failures) > 0:
            logger.error("Failed to post {} profiles: {}".format(len(failures), failures))

    def fetch_report(self):
        """
        Fetches the Workday report data
        Strip out unused data
        Returns the JSON document with only used data
        """

        hris_url = self.secret_manager.secret("hris_url")
        hris_username = self.secret_manager.secret("hris_user")
        hris_password = self.secret_manager.secret("hris_password")

        logger.info("Fetching HRIS report from {}".format(hris_url))
        params = dict(format="json")

        res = requests.get(hris_url, auth=requests.auth.HTTPBasicAuth(hris_username, hris_password), params=params)

        del hris_password
        del hris_username

        if not res.ok:
            logger.error(
                "Error fetching the HRIS report, status_code: {}, reason: {}, text: {}".format(
                    res.status_code, res.reason, res.text
                )
            )
            raise ValueError("Could not fetch HRIS report")
        return res.json()

    def convert_hris_to_cis_profiles(self, hris_data, user_ids=None):
        """
        @hris_data list dict of HRIS data
        @user_ids list of user ids to convert

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
                "GMT+05:00 Pakistan Standard Time (Karachi)": "UTC+05:00 Pakistan/Karachi",
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
            try:
                tzmap[hris_tz]
            except KeyError:
                logger.warning(
                    "Unknown timezone in workday, defaulting to UTC. Timezone from HRIS was" " {}.".format(hris_tz)
                )
                return "UTC+0000 Europe/London"
            return tzmap[hris_tz]

        def cost_center_convert(cc):
            """
            Cost centers can have decimal points
            So it's a float
            """
            return str(float(cc.split(" ")[0]))

        def strbool_convert(v):
            return v.lower() in ("yes", "true", "t", "1")

        user_array = []
        for hruser in hris_data.get("Report_Entry"):
            # Attempt a rough guess at the user-id. this may not match all user ids correctly
            # We assume this is ok as user_ids are only passed for testing purposes or fixing purposes
            if user_ids is not None:
                if "ad|Mozilla-LDAP|" + hruser.get("PrimaryWorkEmail").split("@")[0] not in user_ids:
                    if "ad|Mozilla-LDAP-Dev|" + hruser.get("PrimaryWorkEmail").split("@")[0] not in user_ids:
                        # Skip user
                        continue
            p = cis_profile.User()
            # Note: Never use non-preferred names here
            p.primary_email.value = hruser.get("PrimaryWorkEmail")
            p.primary_email.signature.publisher.name = "hris"
            p.last_name.value = hruser.get("Preferred_Name_-_Last_Name")
            p.last_name.signature.publisher.name = "hris"
            p.first_name.value = hruser.get("PreferredFirstName")
            p.first_name.signature.publisher.name = "hris"
            p.timezone.value = tz_convert(hruser.get("Time_Zone"))
            p.timezone.signature.publisher.name = "hris"
            p.staff_information.manager.value = strbool_convert(hruser.get("IsManager"))
            p.staff_information.manager.signature.publisher.name = "hris"
            p.staff_information.director.value = strbool_convert(hruser.get("isDirectorOrAbove"))
            p.staff_information.director.signature.publisher.name = "hris"
            if len(hruser.get("EmployeeID")) > 0:
                p.staff_information.staff.value = True
            else:
                p.staff_information.staff.value = False
            p.staff_information.staff.signature.publisher.name = "hris"
            p.staff_information.title.value = hruser.get("businessTitle")
            p.staff_information.title.signature.publisher.name = "hris"
            p.staff_information.team.value = hruser.get("Team")
            p.staff_information.team.signature.publisher.name = "hris"
            p.staff_information.cost_center.value = cost_center_convert(hruser.get("Cost_Center"))
            p.staff_information.cost_center.signature.publisher.name = "hris"
            p.staff_information.worker_type.value = hruser.get("WorkerType")
            p.staff_information.worker_type.signature.publisher.name = "hris"
            p.staff_information.wpr_desk_number.value = hruser.get("WPRDeskNumber")
            p.staff_information.wpr_desk_number.signature.publisher.name = "hris"
            p.staff_information.office_location.value = hruser.get("LocationDescription")
            p.staff_information.office_location.signature.publisher.name = "hris"

            p.access_information.hris["values"] = {}
            p.access_information.hris.signature.publisher.name = "hris"
            p.access_information.hris["values"]["employee_id"] = hruser.get("EmployeeID")
            p.access_information.hris["values"]["worker_type"] = hruser.get("WorkerType")
            p.access_information.hris["values"]["manager_employee_id"] = hruser.get("WorkersManagersEmployeeID")
            p.access_information.hris["values"]["egencia_pos_country"] = hruser.get("EgenciaPOSCountry")

            try:
                p.sign_all(publisher_name="hris")
            except Exception as e:
                logger.critical(
                    "Profile data signing failed for user {} - skipped signing, verification "
                    "WILL FAIL ({})".format(p.primary_email.value, e)
                )
                logger.debug("Profile data {}".format(p.as_dict()))
            try:
                p.validate()
            except Exception as e:
                logger.critical(
                    "Profile schema validation failed for user {} - skipped validation, verification "
                    "WILL FAIL({})".format(p.primary_email.value, e)
                )
                logger.debug("Profile data {}".format(p.as_dict()))

            try:
                p.verify_all_publishers(cis_profile.User())
            except Exception as e:
                logger.critical(
                    "Profile publisher verification failed for user {} - skipped signing, verification "
                    "WILL FAIL ({})".format(p.primary_email.value, e)
                )
                logger.debug("Profile data {}".format(p.as_dict()))
            # XXX Change this whenever hris becomes the publisher for users
            # When that happens, code to disable the user will also be necessary!
            # p.active.value = True
            user_array.append(p)

        return user_array
