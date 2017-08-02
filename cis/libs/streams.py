from cis.settings import get_config


class Operation(object):
    def __init__(self, boto_session, publisher, signature, encrypted_profile_data):
        self.boto_session = boto_session
        self.config = get_config()
        self.encrypted_profile_data = encrypted_profile_data
        self.publisher = publisher
        self.signature = signature
        self.kinesis_client = None

    def to_kinesis(self):
        """
        Publish data to CIS kinesis stream given a partition key.
    
        :data: Data to be published to kinesis (dict)
        :partition_key: Kinesis partition key used to publish data to
        """

        if self.kinesis_client is not None:
            kinesis = self.boto_session.client('kinesis')

        event = {
            'publisher': self.publisher,
            'profile': self.encrypted_profile_data,
            'signature': self.signature
        }

        stream_arn = self.config('kinesis_stream_arn', namespace='cis')
        stream_name = stream_arn.split('/')[1]

        response = kinesis.put_record(
            StreamName=stream_name,
            Data=event,
            PartitionKey=self.publisher.get('id', None)
        )

        return response



