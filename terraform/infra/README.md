infra
=====

Generally for dealing with DAX.

To allow the Person API Lambdas to talk with DAX, you'll need to
get the following out of `terraform output`:

* `lambda_security_group`: a security group, allowing the lambdas to talk to DAX (and DAX to accept traffic from this SG).
* `private_subnets`: the subnets where we create the Person API lambdas.

We generally prefer to use private subnets because it's easier to
reason about what kinds of traffic we're going to expect: None.
The Lambdas are all called via the AWS API Gateway, using AWS's
APIs, and not via regular channels.
