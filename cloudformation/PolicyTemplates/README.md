## CIS Developer Policy Templates

This method of AWS IAM policy is called ResourceTag Policy.  Effectively this
grants a developer admin level access of resources with specific tags.

In our case the tag granted access is "Application:Cis".  Any resource that is
type lambda, kinesis, or dynamo tagged in this manner will allow explicit access.

Recommended that you use this with aws-mfa python module for compatibility with Apex framework.

To use aws-mfa start by:

    pip install -r requirements.txt
    Edit your ~/.aws/credentials file and create a profile that looks like this with static access keys that give you the ability to assume_role.

[defult-long-term]
aws_access_key_id = YOUR_LONGTERM_KEY_ID
aws_secret_access_key = YOUR_LONGTERM_ACCESS_KEY

I set up a bash alias for convenience after this that looks like:

alias cisaws="/Users/akrug/Library/Python/2.7/bin/aws-mfa --device {YOUR_MFA_ARN} --assume-role arn:aws:iam::656532927350:role/CISDeveloper --role-session-name "cis-developer-session""

My creds generated in this manner are good for 60-minutes. I could set up additional aliases for additional profiles if necessary.
