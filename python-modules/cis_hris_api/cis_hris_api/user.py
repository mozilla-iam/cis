from boto3.dynamodb.conditions import Key
from copy import deepcopy
from iam_profile_faker import factory


class Profile(object):
    def __init__(self, dynamodb_table_resource):
        """Take a dynamodb table resource to use for operations."""
        self.table = dynamodb_table_resource
        self.field_mapping = {
            'IsManager': 'is_manager',
            'LocationDescription': 'location_description',
            'PreferredFirstName': 'preferred_first_name',
            'Preferred_Name': 'preferred_name',
            'Preferred_Name_-_Last_Name': 'preferred_last_name',
            'Team': 'team',
            'WPRDeskNumber': 'wpr_desk_number',
            'WorkerType': 'worker_type',
            'Worker_s_Manager_s_Email_Address': 'manager_email',
            'WorkersManager': 'workers_manager',
            'businessTitle': 'business_title',
            'isDirectorOrAbove': 'is_director_or_above',
            'PrimaryWorkEmail': 'primary_email',
            'EmployeeID': 'employee_id'
        }

    def _clean(self, profile):
        """Remove any keys containing empty string."""
        profile_copy = deepcopy(profile)
        for k in profile:
            if k in self.field_mapping.keys():
                if profile[k] == '' or profile[k] == []:
                    del profile_copy[k]
                else:
                    profile_copy.pop(k)
                    profile_copy[self.field_mapping[k]] = profile[k]
            else:
                profile_copy.pop(k)
        return profile_copy

    def create(self, user_profile):
        return self.table.put_item(Item=self._clean(user_profile))

    def update(self, user_profile):
        return self.table.put_item(Item=user_profile)

    def delete(self, user_profile):
        return self.table.delete_item(Item=user_profile)

    def find_by_email(self, email):
        result = self.table.query(
            KeyConditionExpression=Key('primary_email').eq(email)
        )
        return result

    def seed(self, seed_data):
        for record in seed_data['Report_Entry']:
            self.create(record)

    @property
    def all(self):
        response = self.table.scan()
        users = response.get('Items')
        while 'LastEvaluatedKey' in response:
            response = self.table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            users.extend(response['Items'])
        return users

    def all_by_page(self, next_page=None, limit=25):
        if next_page is not None:
            response = self.table.scan(
                Limit=limit,
                ExclusiveStartKey=next_page
            )
        else:
            response = self.table.scan(
                Limit=limit
            )
        return response
