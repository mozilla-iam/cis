#!/usr/bin/env python

import cis_profile.profile
import faker
import faker.providers
import logging
import random

logger = logging.getLogger(__name__)
fake = faker.Faker()


class FakeCISProfileProvider(faker.providers.BaseProvider):
    """
    A provider for cis_profiles fake data
    """

    def user_id(self):
        p = ['ad|Mozilla-LDAP|McDummy',
             'github|23494952',
             'google-oauth2|49459459039398484',
             'oauth2|firefoxaccounts|d0cee943848ef02293dfa',
             'email|5be93248483ee93d']
        return random.choice(p)

    def login_method(self):
        p = ['Mozilla-LDAP',
             'google-oauth2',
             'github',
             'firefoxaccounts',
             'email'
             ]
        return random.choice(p)

    def usernames(self):
        u = {}
        for i in range(0, random.randrange(0, 10)):
            u[fake.words(nb=1)[0]] = fake.user_name()
        return u

    def pub_key(self):
        u = {}
        for i in range(0, random.randrange(0, 3)):
            u[fake.words(nb=1)[0]] = fake.ipv6()
        return u

    def phone(self):
        u = {}
        for i in range(0, random.randrange(0, 3)):
            u[fake.words(nb=1)[0]] = fake.phone_number()
        return u

    def websites(self, s):
        u = {}
        for i in range(0, len(s)):
            u[fake.words(nb=1)[0]] = s[i]
        return u

    def ai(self):
        """
        Fake groups generator
        """
        u = {}
        for i in range(0, random.randrange(0, 10)):
            u[fake.words(nb=1)[0]] = None
        return u

    def worker_type(self):
        p = ['Employee', 'Contractor', 'Intern']
        return random.choice(p)

    def display(self, filterout=[]):
        p = [None, 'public', 'authenticated', 'vouched', 'ndaed', 'staff', 'private']
        r = set(p) - set(filterout)
        return random.choice(list(r))


class FakeUser(cis_profile.profile.User):
    """
    A fake user factory for cis_profile
    @generator int a static seed to always get the same fake profile back
    """

    def __init__(self, generator=None):
        super().__init__()
        if generator is not None:
            fake.seed(generator)

        self.generate(fake)
        super().initialize_timestamps()

    def generate(self, fake):
        """
        See also `data/user_profile_null.json`
        """

        fake.add_provider(faker.providers.person)
        fake.add_provider(faker.providers.date_time)
        fake.add_provider(faker.providers.internet)
        fake.add_provider(faker.providers.profile)
        fake.add_provider(faker.providers.lorem)
        fake.add_provider(faker.providers.address)
        fake.add_provider(FakeCISProfileProvider)

        fprofile = fake.profile()

        self.__dict__['user_id']['value'] = fake.user_id()
        self.__dict__['login_method']['value'] = fake.login_method()
        self.__dict__['active']['value'] = fake.boolean()
        self.__dict__['last_modified']['value'] = fake.iso8601()
        self.__dict__['created']['value'] = fake.iso8601()

        self.__dict__['usernames']['values'] = fake.usernames()
        self.__dict__['usernames']['metadata']['display'] = fake.display(filterout=["staff", "ndaed", "authenticated",
            "private", "vouched", None])

        self.__dict__['first_name']['value'] = fake.first_name()
        self.__dict__['first_name']['metadata']['display'] = fake.display()

        self.__dict__['last_name']['value'] = fake.last_name()
        self.__dict__['last_name']['metadata']['display'] = fake.display()

        self.__dict__['primary_email']['value'] = fprofile['mail']
        if self.login_method.value == 'Mozilla-LDAP':
            self.__dict__['identities']['mozilla_ldap_id']['value'] = fprofile['mail']
        self.__dict__['identities']['dinopark_id']['value'] = fake.user_name()
        self.__dict__['ssh_public_keys']['values'] = fake.pub_key()
        self.__dict__['pgp_public_keys']['values'] = fake.pub_key()
        if self.login_method.value == 'Mozilla-LDAP':
            self.__dict__['access_information']['ldap']['values'] = fake.ai()
            self.__dict__['access_information']['hris']['values'] = fake.ai()
        self.__dict__['access_information']['mozilliansorg']['values'] = fake.ai()
        self.__dict__['access_information']['access_provider']['values'] = fake.ai()

        self.__dict__['fun_title']['value'] = fprofile['job']
        self.__dict__['fun_title']['metadata']['display'] = fake.display()

        self.__dict__['description']['value'] = fake.text(max_nb_chars=200)
        self.__dict__['location']['value'] = fake.country()
        self.__dict__['timezone']['value'] = fake.timezone()
        self.__dict__['languages']['values'] = {'1': 'English'}
        self.__dict__['tags']['values'] = {'1': 'Test'}
        self.__dict__['pronouns']['value'] = None
        self.__dict__['picture']['value'] = fake.image_url()
        self.__dict__['uris']['values'] = fake.websites(fprofile['website'])
        self.__dict__['phone_numbers']['values'] = fake.phone()
        self.__dict__['alternative_name']['value'] = fprofile['name']
        if self.login_method.value == 'Mozilla-LDAP':
            self.__dict__['staff_information']['manager']['value'] = fake.boolean()
            self.__dict__['staff_information']['manager']['metadata']['display'] = \
                fake.display(filterout=['public', 'authenticated', 'vouched', None])

            self.__dict__['staff_information']['director']['value'] = fake.boolean()
            self.__dict__['staff_information']['director']['metadata']['display'] = \
                fake.display(filterout=['public', 'authenticated', 'vouched', None])

            self.__dict__['staff_information']['staff']['value'] = True
            self.__dict__['staff_information']['staff']['metadata']['display'] = \
                fake.display(filterout=['public', 'authenticated', 'vouched', None])

            self.__dict__['staff_information']['title']['value'] = fprofile['job']
            self.__dict__['staff_information']['title']['metadata']['display'] = fake.display()

            self.__dict__['staff_information']['team']['value'] = fake.sentence(nb_words=2)
            self.__dict__['staff_information']['team']['metadata']['display'] = \
                fake.display(filterout=['public', 'authenticated', 'vouched', 'private', None])

            self.__dict__['staff_information']['cost_center']['value'] = str(random.randint(1000, 9000))
            self.__dict__['staff_information']['cost_center']['metadata']['display'] = \
                fake.display(filterout=['public', 'authenticated', 'vouched', 'ndaed', 'private', None])

            self.__dict__['staff_information']['worker_type']['value'] = fake.worker_type()
            self.__dict__['staff_information']['worker_type']['metadata']['display'] = \
                fake.display(filterout=['public', 'authenticated', 'vouched', 'ndaed', 'private', None])

            self.__dict__['staff_information']['wpr_desk_number']['value'] = str(random.randint(100, 900))
            self.__dict__['staff_information']['wpr_desk_number']['metadata']['display'] = \
                fake.display(filterout=['public', 'authenticated', 'vouched', 'private', None])

            self.__dict__['staff_information']['office_location']['value'] = fake.city()
            self.__dict__['staff_information']['office_location']['metadata']['display'] = \
                fake.display(filterout=['public', 'authenticated', 'vouched', 'private', None])
