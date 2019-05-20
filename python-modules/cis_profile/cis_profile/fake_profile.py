#!/usr/bin/env python

import base64
import cis_profile.profile
import faker
import faker.providers
import logging
import itertools

from cis_profile.fake_display import DisplayFaker, DisplayFakerPolicy

logger = logging.getLogger(__name__)
fake = faker.Faker()


def create_random_hierarchy_iter(random):
    """Generate hierarchy iterator with a random pattern"""

    def gen():
        for i in itertools.count():
            yield (i + 1, random.randint(0, i))

    return gen()


def non_hierarchy_iter():
    def gen():
        while True:
            yield (None, None)

    return gen()


class FakeProfileConfig(object):
    def __init__(self):
        self._create = False
        self._cis = False
        self._mozillians = False
        self._hris = False
        self._ldap = False
        self._auth0 = False
        self._uuid_username = False
        self._minimal = False
        self._active_percent = 100

    def default(self):
        return self.mozillians().hris().ldap().auth0().uuid_username()

    def create(self, b=True):
        self._create = b
        return self

    def cis(self, b=True):
        self._cis = b
        return self

    def minimal(self, b=True):
        self._minimal = b
        return self

    def mozillians(self, b=True):
        self._mozillians = b
        return self

    def hris(self, b=True):
        self._hris = b
        return self

    def ldap(self, b=True):
        self._ldap = b
        return self

    def auth0(self, b=True):
        self._auth0 = b
        return self

    def uuid_username(self, b=True):
        self._uuid_username = b
        return self


class FakeCISProfileProvider(faker.providers.BaseProvider):
    """
    A provider for cis_profiles fake data
    """

    def ldap_identity(self):
        """
        Fake ldap identity generator
        """
        user_name = self.generator.user_name()
        email = "{}@{}".format(user_name, self.generator.domain_name())
        return (
            {"mozilla_posix_id": user_name, "mozilla_ldap_id": email, "mozilla_ldap_primary_email": email},
            "ad|Mozilla-LDAP|{}".format(user_name),
            email,
        )

    def mozillians_identities(self, user_idp=None, additional=None):
        """
        Fake additional identities generator
        """

        def custom1():
            email = self.generator.email()
            return ({"custom_1_primary_email": email}, "email|{}".format(self.generator.md5()), email)

        def custom2():
            email = self.generator.email()
            return ({"custom_2_primary_email": email}, "email|{}".format(self.generator.md5()), email)

        def custom3():
            email = self.generator.email()
            return ({"custom_3_primary_email": email}, "email|{}".format(self.generator.md5()), email)

        def github():
            id = self.generator.pyint()
            email = self.generator.email()
            return (
                {
                    "github_id_v3": str(id),
                    "github_id_v4": base64.urlsafe_b64encode(str.encode("04:User{}".format(id))).decode("utf-8"),
                    "github_primary_email": email,
                },
                "github|{}".format(id),
                email,
            )

        def google():
            id = self.generator.pyint()
            email = self.generator.email()
            return ({"google_oauth2_id": str(id), "google_primary_email": email}, "google-oauth2|{}".format(id), email)

        def fxa():
            id = self.generator.pystr(min_chars=20, max_chars=20)
            email = self.generator.email()
            return (
                {"firefox_accounts_id": id, "firefox_accounts_primary_email": email},
                "oauth2|firefoxaccounts|{}".format(id),
                email,
            )

        idps = {
            "github": github,
            "google": google,
            "firefox_accounts": fxa,
            "custom_1_primary_email": custom1,
            "custom_2_primary_email": custom2,
            "custom_3_primary_email": custom3,
        }

        identities = {}

        if not user_idp or user_idp not in idps.keys():
            user_idp = self.generator.random.choice(list(idps.keys()))

        idp, user_id, email = idps[user_idp]()

        identities.update(idp)

        if additional:
            pool = idps.keys() - set(user_idp)
            k = self.generator.random.randint(len(pool))
            for idp_name in self.generator.random.sample(pool, k):
                idp, _, _ = idps[idp_name]
                identities.update(idp)

        return (identities, user_id, email)

    def login_method(self):
        p = ["Mozilla-LDAP", "google-oauth2", "github", "firefoxaccounts", "email"]
        return self.generator.random.choice(p)

    def primary_username_random(self):
        return "r--{}".format(base64.urlsafe_b64encode(fake.uuid4(cast_to=lambda x: x.bytes)).decode("utf-8"))

    def primary_username(self):
        return self.generator.user_name()

    def usernames(self):
        u = {}
        for _ in range(self.generator.random.randrange(0, 10)):
            u[self.generator.words(nb=1)[0]] = self.generator.user_name()
        return u

    def ssh_keys(self):
        keys = {}
        for _ in range(self.generator.random.randrange(0, 3)):
            keys[self.generator.words(nb=1)[0]] = self.generator.sha1(raw_output=False)
        return keys

    def pgp_keys(self):
        keys = {}
        for _ in range(self.generator.random.randrange(0, 3)):
            keys[self.generator.words(nb=1)[0]] = self.generator.sha1(raw_output=False)
        return keys

    def phone(self):
        u = {}
        for _ in range(self.generator.random.randrange(0, 3)):
            u[self.generator.words(nb=1)[0]] = self.generator.phone_number()
        return u

    def websites(self):
        u = {}
        for _ in range(self.generator.random.randrange(0, 5)):
            u[self.generator.words(nb=1)[0]] = self.generator.url()
        return u

    def languages(self):
        pool = ["German", "English", "French", "Spanish"]
        n = self.generator.random.randint(0, len(pool))
        langs = {}
        for lang in self.generator.random.sample(pool, n):
            langs[lang] = None
        return langs

    def tags(self):
        t = {}
        for _ in range(self.generator.random.randrange(0, 10)):
            t[self.generator.words(nb=1)[0]] = None
        return t

    def ai(self):
        """
        Fake groups generator
        """
        u = {}
        for _ in range(0, self.generator.random.randrange(0, 10)):
            u[self.generator.words(nb=1)[0]] = None
        return u

    def worker_type(self):
        p = ["Employee", "Contractor", "Intern"]
        return self.generator.random.choice(p)

    def display(self, filterout=[]):
        p = [None, "public", "authenticated", "vouched", "ndaed", "staff", "private"]
        r = set(p) - set(filterout)
        return self.generator.random.choice(list(r))

    def custom_tz(self):
        return "UTC{:0=+3}00 {}".format(self.generator.random.randint(-12, 12), self.generator.timezone())

    def hris(self, employee_id=None, manager_id=None):
        h = {}

        h["employee_id"] = employee_id if employee_id is not None else self.generator.random.randint(0, 100000)
        h["worker_type"] = self.generator.random.choice(["Employee", "Contractor"])
        h["managers_employee_id"] = manager_id if manager_id is not None else self.generator.random.randint(0, 100000)
        h["egencia_pos_country"] = self.generator.country_code(representation="alpha-2")

        return h

    def staff_information(self):
        s = {}
        s["manager"] = self.generator.boolean()
        s["director"] = self.generator.boolean()
        s["staff"] = True
        s["title"] = self.generator.job()
        s["team"] = self.generator.sentence(nb_words=2)
        s["cost_center"] = "{} - {}".format(
            self.generator.random.randint(1000, 9999), self.generator.sentence(nb_words=2)
        )
        s["office_location"] = self.generator.random.choice(
            ["{} Office".format(self.generator.city()), "{} Remote".format(self.generator.country())]
        )
        s["wpr_desk_number"] = str(self.generator.random.randint(10000, 99999))

        return s


class FakeUser(cis_profile.profile.User):
    """
    A fake user factory for cis_profile
    @generator int a static seed to always get the same fake profile back
    """

    def __init__(self, seed=None, fake=fake, hierarchy=non_hierarchy_iter(), config=FakeProfileConfig().default()):
        user_structure_json_file = (
            "data/user_profile_null_create.json" if config._create else "data/user_profile_null.json"
        )
        super().__init__(user_structure_json_file=user_structure_json_file)
        if seed is not None:
            fake.seed_instance(seed)

        fake.add_provider(faker.providers.person)
        fake.add_provider(faker.providers.date_time)
        fake.add_provider(faker.providers.internet)
        fake.add_provider(faker.providers.misc)
        fake.add_provider(faker.providers.lorem)
        fake.add_provider(faker.providers.address)
        fake.add_provider(faker.providers.job)
        fake.add_provider(FakeCISProfileProvider)

        self._init_dicts()
        self.generate_minimal(fake, config)
        self.generate_uuid_and_primary_username(fake, config)
        self.generate_ldap(fake, config)
        self.generate_hris(fake, config, hierarchy)
        self.generate_mozillians(fake, config)

        display_faker = DisplayFaker()
        display_faker.populate(self.__dict__, policy=DisplayFakerPolicy.rand_display(fake.random))

        super().initialize_timestamps()

    def _init_dicts(self):
        """
        Init null profile dicts with empty dicts so that we can update them
        """
        for _ in self.__dict__["access_information"]:
            self.__dict__["access_information"][_]["values"] = {}

    def _d(self, path, value):
        v = self.__dict__
        path = path.split(".")
        last = path.pop()
        for a in path:
            v = v[a]
        v[last] = value

    def generate_uuid_and_primary_username(self, fake, config):
        """
        Generate uuid (added by change API)
        """
        if not config._uuid_username:
            return

        self._d("uuid.value", str(fake.uuid4()))
        self._d("primary_username.value", fake.primary_username_random())

    def generate_minimal(self, fake, config):
        if not config._minimal:
            return
        identities, user_id, email = fake.mozillians_identities()

        self._d("user_id.value", user_id)
        self._d("login_method.value", fake.login_method())
        self._d("active.value", fake.boolean(chance_of_getting_true=config._active_percent))
        self._d("primary_email.value", email)

    def generate_ldap(self, fake, config):
        """
        Generate fields created by ldap
        """
        if not config._ldap:
            return

        identities, user_id, email = fake.ldap_identity()

        self._d("user_id.value", user_id)
        self._d("login_method.value", "Mozilla-LDAP")
        self._d("active.value", fake.boolean(chance_of_getting_true=config._active_percent))
        self._d("created.value", fake.iso8601())
        self._d("primary_email.value", email)

        if config._minimal:
            return

        for k, v in identities.items():
            self.__dict__["identities"][k]["value"] = v

        self._d("first_name.value", fake.first_name())
        self._d("last_name.value", fake.last_name())
        self._d("ssh_public_keys.values", fake.ssh_keys())
        self._d("pgp_public_keys.values", fake.pgp_keys())
        self._d("access_information.ldap.values", fake.ai())
        self._d("fun_title.value", fake.job())
        self._d("description.value", fake.text(max_nb_chars=200))
        self._d("location.value", fake.country())
        self._d("timezone.value", fake.custom_tz())
        self._d("picture.value", fake.image_url())
        self._d("phone_numbers.values", fake.phone())

    def generate_hris(self, fake, config, hierarchy):
        """
        Generate fields created by ldap
        """
        if not config._hris:
            return

        staff_information = fake.staff_information()
        eid, mid = next(hierarchy)
        hris = fake.hris(eid, mid)
        self._d("first_name.value", fake.first_name())
        self._d("last_name.value", fake.last_name())
        self._d("timezone.value", fake.custom_tz())
        self._d("created.value", fake.iso8601())
        self._d("active.value", fake.boolean(chance_of_getting_true=config._active_percent))
        self.__dict__["access_information"]["hris"]["values"].update(hris)

        for k, v in staff_information.items():
            self.__dict__["staff_information"][k]["value"] = v

    def generate_mozillians(self, fake, config):
        """
        Generate fields created by mozillians
        """
        if not config._mozillians:
            return

        identities, user_id, email = fake.mozillians_identities(additional=not config._mozillians)

        self._d("user_id.value", user_id)
        self._d("login_method.value", fake.login_method())
        self._d("active.value", fake.boolean(chance_of_getting_true=config._active_percent))
        self._d("last_modified.value", fake.iso8601())
        self._d("created.value", fake.iso8601())
        self._d("first_name.value", fake.first_name())
        self._d("primary_email.value", email)

        for k, v in identities.items():
            self.__dict__["identities"][k]["value"] = v

        if not config._create:
            self._d("primary_username.value", fake.primary_username())

        if config._minimal:
            return

        self._d("usernames.values", fake.usernames())
        self._d("last_name.value", fake.last_name())
        self._d("ssh_public_keys.values", fake.ssh_keys())
        self._d("pgp_public_keys.values", fake.pgp_keys())
        self._d("access_information.mozilliansorg.values", fake.ai())
        self._d("fun_title.value", fake.job())
        self._d("description.value", fake.text(max_nb_chars=200))
        self._d("location.value", fake.country())
        self._d("timezone.value", fake.custom_tz())
        self._d("languages.values", fake.languages())
        self._d("tags.values", fake.tags())
        self._d("pronouns.value", None)
        self._d("picture.value", fake.image_url())
        self._d("uris.values", fake.websites())
        self._d("alternative_name.value", fake.name())

    def generate_auth0(self, fake, config):
        """
        Generate fields created by auth0
        """
        if not config._auth0:
            return

        self._d("access_information.access_provider.values", fake.ai())


def batch_create_fake_profiles(seed, number):
    fake = faker.Faker()
    fake.seed(seed)
    hierarchy = create_random_hierarchy_iter(fake.random)
    profiles = map(lambda x: x.as_dict(), [FakeUser(fake=fake, hierarchy=hierarchy) for _ in range(number)])

    return list(profiles)
