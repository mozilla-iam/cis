import os
from decouple import config


ARN_MASTER_KEY = config(
    'CIS_ARN_MASTER_KEY', default=os.getenv('CIS_ARN_MASTER_KEY')
)
DYNAMODB_TABLE = config(
    'CIS_DYNAMODB_TABLE',
    default=os.getenv('CIS_DYNAMODB_TABLE')
)
