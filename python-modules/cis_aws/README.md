# cis_aws python module

## Purpose

Interop layer for abstracting AWS assume role vs local developer uses.

## Usage

The module: cis_aws requires the following configuration options in either environment variables or a pyconfig.
In order to use pyconfig copy the `mozilla-cis.ini.dist` to `~/.mozilla-cis.ini` or `/etc/mozilla-cis.ini`.  This is overridable by setting an evironment variable `'CIS_CONFIG_INI'` to any other system path.

*Order of configuration resolution*

1. ini file.
2. environment variables in the CIS namespace.


### First Class Object Usage

```python

from cis_aws import connect

# New up a connection object.
aws = connect.AWS()

# Get a boto_session object for your desired region.  Local returns a stub.

aws.session(region_name='us-west-2')

# Assume a role using the assumeRole configured.  AssumeRole is required ( this is an opinionated decision )

aws.assume_role()

```

> The above block of code initializes the correct role on the AWS() object.

### Discovering CIS resources.

CIS version 1 included a lot of hard coded ARNs.  The library exposes a discovery function in two methods that will return a boto3 connection object and the ARN of the resource using tag based discovery.  In a local environment this will fall back to dynalite and kinesalite.

> Note that each assumeRole is only good for 3600 seconds.  So if you are persisting a boto3 client for dynamoDb or kinesis for longer than 1 hour you will need to handle the accessToken expired exception of ask for a new discovery.  Simply calling assume_role() on the object as well will opportunistically renew the token if it needs to be renewed.

```python

# Discover Kinesis

aws.input_stream_client()

# Discover DynamoDb

aws.identity_vault_client()

```
