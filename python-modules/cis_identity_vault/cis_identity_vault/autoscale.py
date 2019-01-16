import boto3
from cis_identity_vault.common import get_config


class ScalableTable(object):
    def __init__(self, table_name):
        self.config = get_config()
        self._boto_session = None
        self._autoscaling_client = None
        self.index_names = ['primary_email', 'sequence_number']
        self.max_read_capacity = 100
        self.max_write_capacity = 100
        self.min_read_capactity = 5
        self.min_write_capactity = 5
        self.percent_of_use_to_aim_for = 50.0
        self.scale_out_cooldown_in_seconds = 60
        self.scale_in_cooldown_in_seconds = 60
        self.table_name = table_name

    def connect(self):
        if self._boto_session is None:
            self._session()

        if self._autoscaling_client is None:
            self._autoscaling_client = self._boto_session.client('application-autoscaling')

        return self._autoscaling_client

    def _session(self):
        if self._boto_session is None:
            region = self.config('region_name', namespace='cis', default='us-west-2')
            self._boto_session = boto3.session.Session(region_name=region)
            return self._boto_session

    def enable_autoscaler(self):
        self._register_scalable_target_read_table()
        self._register_scalable_target_write_table()
        self._register_scalable_target_read_indicies()
        self._register_scalable_target_write_indicies()
        self._put_scaling_policy_table()
        self._put_scaling_policy_indexes()
        return True

    def _register_scalable_target_read_table(self):
        self._autoscaling_client.register_scalable_target(
            ServiceNamespace='dynamodb',
            ResourceId='table/{}'.format(self.table_name),
            ScalableDimension='dynamodb:table:ReadCapacityUnits',
            MinCapacity=self.min_read_capactity,
            MaxCapacity=self.max_read_capacity
        )

    def _register_scalable_target_write_table(self):
        self._autoscaling_client.register_scalable_target(
            ServiceNamespace='dynamodb',
            ResourceId='table/{}'.format(self.table_name),
            ScalableDimension='dynamodb:table:WriteCapacityUnits',
            MinCapacity=self.min_write_capactity,
            MaxCapacity=self.max_write_capacity
        )

    def _register_scalable_target_read_indicies(self):
        for indexName in self.index_names:
            self._autoscaling_client.register_scalable_target(
                ServiceNamespace='dynamodb',
                ResourceId='table/{}/index/{}-{}'.format(
                    self.table_name, self.table_name, indexName
                ),
                ScalableDimension='dynamodb:index:ReadCapacityUnits',
                MinCapacity=self.min_read_capactity,
                MaxCapacity=self.max_read_capacity
            )

    def _register_scalable_target_write_indicies(self):
        for indexName in self.index_names:
            self._autoscaling_client.register_scalable_target(
                ServiceNamespace='dynamodb',
                ResourceId='table/{}/index/{}-{}'.format(
                    self.table_name, self.table_name, indexName
                ),
                ScalableDimension='dynamodb:index:WriteCapacityUnits',
                MinCapacity=self.min_write_capactity,
                MaxCapacity=self.max_write_capacity
            )

    def _put_scaling_policy_table(self):
        self._autoscaling_client.put_scaling_policy(
            ServiceNamespace='dynamodb',
            ResourceId='table/{}'.format(self.table_name),
            PolicyType='TargetTrackingScaling',
            PolicyName='ScaleDynamoDBReadCapacityUtilization',
            ScalableDimension='dynamodb:table:ReadCapacityUnits',
            TargetTrackingScalingPolicyConfiguration={
                'TargetValue': self.percent_of_use_to_aim_for,
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'DynamoDBReadCapacityUtilization'
                },
                'ScaleOutCooldown': self.scale_out_cooldown_in_seconds,
                'ScaleInCooldown': self.scale_in_cooldown_in_seconds
            }
        )

        self._autoscaling_client.put_scaling_policy(
            ServiceNamespace='dynamodb',
            ResourceId='table/{}'.format(self.table_name),
            PolicyType='TargetTrackingScaling',
            PolicyName='ScaleDynamoDBWriteCapacityUtilization',
            ScalableDimension='dynamodb:table:WriteCapacityUnits',
            TargetTrackingScalingPolicyConfiguration={
                'TargetValue': self.percent_of_use_to_aim_for,
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'DynamoDBWriteCapacityUtilization'
                },
                'ScaleOutCooldown': self.scale_out_cooldown_in_seconds,
                'ScaleInCooldown': self.scale_in_cooldown_in_seconds
            }
        )

    def _put_scaling_policy_indexes(self):
        for indexName in self.index_names:
            self._autoscaling_client.put_scaling_policy(
                ServiceNamespace='dynamodb',
                ResourceId='table/{}/index/{}-{}'.format(
                    self.table_name,
                    self.table_name,
                    indexName
                ),
                PolicyType='TargetTrackingScaling',
                PolicyName='ScaleDynamoDBWriteCapacityUtilization',
                ScalableDimension='dynamodb:index:WriteCapacityUnits',
                TargetTrackingScalingPolicyConfiguration={
                    'TargetValue': self.percent_of_use_to_aim_for,
                    'PredefinedMetricSpecification': {
                        'PredefinedMetricType': 'DynamoDBWriteCapacityUtilization'
                    },
                    'ScaleOutCooldown': self.scale_out_cooldown_in_seconds,
                    'ScaleInCooldown': self.scale_in_cooldown_in_seconds
                }
            )

            self._autoscaling_client.put_scaling_policy(
                ServiceNamespace='dynamodb',
                ResourceId='table/{}/index/{}-{}'.format(
                    self.table_name,
                    self.table_name,
                    indexName
                ),
                PolicyType='TargetTrackingScaling',
                PolicyName='ScaleDynamoDBReadCapacityUtilization',
                ScalableDimension='dynamodb:index:ReadCapacityUnits',
                TargetTrackingScalingPolicyConfiguration={
                    'TargetValue': self.percent_of_use_to_aim_for,
                    'PredefinedMetricSpecification': {
                        'PredefinedMetricType': 'DynamoDBReadCapacityUtilization'
                    },
                    'ScaleOutCooldown': self.scale_out_cooldown_in_seconds,
                    'ScaleInCooldown': self.scale_in_cooldown_in_seconds
                }
            )
