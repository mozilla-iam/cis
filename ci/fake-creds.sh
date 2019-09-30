#!/bin/bash

# Create fake AWS profiles as part of the test pipeline when needed.
if [ ! -d /root/.aws ]; then
    mkdir ~/.aws
    touch ~/.aws/credentials
    echo '[default]' >> ~/.aws/credentials
    echo 'aws_access_key_id=ABCDEFG'  >> ~/.aws/credentials
    echo 'aws_secret_access_key=ABCDEFG'  >> ~/.aws/credentials
    touch ~/.aws/config
    echo '[default]' >> ~/.aws/config
    echo 'output=json'  >> ~/.aws/config
    echo 'region=us-west-2'  >> ~/.aws/config
fi
