import base64
import json
import os
import unittest


class ValidationTest(unittest.TestCase):

    def setUp(self):
        fixtures = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data/fixtures.json')
        with open(fixtures) as artifacts:
            self.test_artifacts = json.load(artifacts)

        # Load a good and bad profile.
        profile_good_file = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'data/profile-good.json')
        profile_bad_file = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'data/profile-bad.json')

        with open(profile_good_file) as profile_good:
            self.test_profile_good = json.load(profile_good)
        with open(profile_bad_file) as profile_bad:
            self.test_profile_bad = json.load(profile_bad)

        os.environ['AWS_DEFAULT_REGION'] = self.test_artifacts['dummy_aws_region']
        # Set environment variables
        """
        * Environment variables used
          * CIS_ARN_MASTER_KEY
          * CIS_DYNAMODB_TABLE
          * CIS_KINESIS_STREAM_ARN
          * CIS_LAMBDA_VALIDATOR_ARN

        """
        os.environ["CIS_ARN_MASTER_KEY"] = self.test_artifacts['dummy_kms_arn']
        os.environ["CIS_DYNAMODB_TABLE"] = self.test_artifacts['dummy_dynamodb_table']
        os.environ["CIS_KINESIS_STREAM_ARN"] = self.test_artifacts['dummy_kinesis_arn']
        os.environ["CIS_LAMBDA_VALIDATOR_ARN"] = self.test_artifacts['dummy_lambda_validator_arn']

        self.publisher = str(base64.b64decode(self.test_artifacts['dummy_publisher']))

    def test_object_init(self):

        from cis.libs import validation

        o = validation.Operation(
            self.publisher,
            self.test_profile_good
        )

        assert o is not None

    def test_schema_validation(self):

        from cis.libs import validation

        o_1 = validation.Operation(
            'foo',
            self.test_profile_good
        )

        good_result = o_1.is_valid()

        o_2 = validation.Operation(
            self.publisher,
            self.test_profile_bad
        )

        print(good_result)

        bad_result = o_2.is_valid()
        assert good_result is True
        assert bad_result is False

    def test_mozillians_org_plugin(self):

        from cis.libs import validation

        o_1 = validation.Operation(
            'mozillians.org',
            self.test_profile_good
        )

        o_1.user = self.test_profile_good

        from cis.libs import validation

        o_1 = validation.Operation(
            'mozillians.org',
            self.test_profile_good
        )

        o_1.user = None

        bad_result = o_1.is_valid()

        assert bad_result is False
