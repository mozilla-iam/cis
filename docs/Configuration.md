# Referencing Configuration Values

The [`/python-modules/cis_notifications/cis_notifications/event.py`](https://github.com/mozilla-iam/cis/blob/874556b48d782236deaad1c1f909879b7943dd74/python-modules/cis_notifications/cis_notifications/event.py#L96-L98) file references config values like this

```
rp_urls = self.config(
    "rp_urls", 
    namespace="cis", 
    default="https://dinopark.k8s.dev.sso.allizom.org/events/update"
)
```

`self.config` is a configuration data structure which comes from the [`get_config()` method in the `common` module in `cis_notifications`](https://github.com/mozilla-iam/cis/blob/874556b48d782236deaad1c1f909879b7943dd74/python-modules/cis_notifications/cis_notifications/event.py#L22) which in turn uses the Everett [ConfigManager](https://everett.readthedocs.io/en/latest/configuration.html#create-a-configmanager-and-specify-sources) to resolve the value.


# Resolving Configuration Values

For a config value, [Everett](https://github.com/willkg/everett), the config library that CIS uses, will follow the order asserted when it's initialized.

The [`get_config()` method in `/python-modules/cis_notifications/cis_notifications/common.py`](https://github.com/mozilla-iam/cis/blob/874556b48d782236deaad1c1f909879b7943dd74/python-modules/cis_notifications/cis_notifications/common.py#L10) looks like this


```
    return ConfigManager(
        [
            ConfigIniEnv(
                    [os.environ.get("CIS_CONFIG_INI"), 
                    "~/.mozilla-cis.ini", 
                    "/etc/mozilla-cis.ini"]
            ), 
            ConfigOSEnv()
        ]
    )
```

This tells Everett to look in the following locations to produce a configuration data structure, using whatever config value it encounters first. 

* A `.ini` file with a filename defined in the `CIS_CONFIG_INI` environment variable
* A `.ini` file called `~/.mozilla-cis.ini`
* A `.ini` file called `/etc/mozilla-cis.ini`
* The environment variables present

## `.ini` Files

The `.ini` files are only used during testing. The environment variables are used in production.

The `.ini` files look like [this](https://github.com/mozilla-iam/cis/blob/master/python-modules/cis_publisher/tests/fixture/mozilla-cis.ini) and set config variables within a namespace. In this example file, the config `.ini` file defines a set of config variables under the `CIS` namespace.

## Environment Variables

In production environment variables are used to assert config values.

So a call for a config value like this

```
self.config(
    "rp_urls",
    namespace="cis",
    default="https://dinopark.k8s.dev.sso.allizom.org/events/update"
)
```

would cause Everett to first look for various `.ini` files, find they didn't exist and fall back to environment variables. Everett determines the name of the environment variable to look for by combining the `namespace` with the name of the variable (in our example `rp_urls`). Everett combines the two values with an underscore (`_`) and sets all the characters to uppercase. So for this example the environment variable name would be

```
CIS_RP_URLS
```

# Where Are The Environment Variables Set?

The environment variables, like the example above of `CIS_RP_URLS`, are set in the [`aws` `provider` in the `environment` section of the `serverless.yml`](https://github.com/mozilla-iam/cis/blob/4465e56e85ca82408b3fd35ac3a717de23890d7b/serverless-functions/webhook_notifier/serverless.yml#L53). This section looks like this

```
provider:
  name: aws
  runtime: python3.8
  stage: ${opt:stage, 'dev'}
  tracing: true # enable tracing
  environment:
    CIS_RP_URLS: ${self:custom.webhookEnvironment.CIS_RP_URLS.${self:custom.webhookStage}}
```

The value of this environment variable is set to a value like

```
${self:custom.webhookEnvironment.CIS_RP_URLS.${self:custom.webhookStage}}
```

## Where is the "stage" set?

To resolve the `${self:custom.webhookEnvironment.CIS_RP_URLS.${self:custom.webhookStage}}` templated value, first the `${self:custom.webhookStage}` needs to be resolved.

`${self:custom.webhookStage}` refers to [this custom dictionary value](https://github.com/mozilla-iam/cis/blob/4465e56e85ca82408b3fd35ac3a717de23890d7b/serverless-functions/webhook_notifier/serverless.yml#L5) which sets the `webhookStage` value.

```
  webhookStage: ${opt:stage, self:provider.stage}
```

This `stage` value is set from the [`--stage` setting passed to `sls` in the `Makefile`](https://github.com/mozilla-iam/cis/blob/4465e56e85ca82408b3fd35ac3a717de23890d7b/serverless-functions/Makefile#L141)

The `Makefile` gets the `$(STAGE)` value from [the environment variable passed when `make` is called](https://github.com/mozilla-iam/cis/blob/4465e56e85ca82408b3fd35ac3a717de23890d7b/serverless-functions/Makefile#L14)

That environment variable is set in the [AWS CodeBuild `buildspec.yml` file](https://github.com/mozilla-iam/cis/blob/4465e56e85ca82408b3fd35ac3a717de23890d7b/deploy.sh#L24-L26
)

So in production [the variable `${self:custom.webhookStage}` resolves to `production`](https://github.com/mozilla-iam/cis/blob/4465e56e85ca82408b3fd35ac3a717de23890d7b/deploy.sh#L24-L26)

## Knowing the "stage", what is the resulting environment variable?

After resolving the "stage" to `production` in our example, we know that the value `${self:custom.webhookEnvironment.CIS_RP_URLS.${self:custom.webhookStage}}` equals `${self:custom.webhookEnvironment.CIS_RP_URLS.production}`

To find the value of `${self:custom.webhookEnvironment.CIS_RP_URLS.production}` we have to look up a value in the [`webhookEnvironment` custom severless dictionary](https://github.com/mozilla-iam/cis/blob/4465e56e85ca82408b3fd35ac3a717de23890d7b/serverless-functions/webhook_notifier/serverless.yml#L6-L42).

Specifically [the "production" key in the `CIS_RP_URLS` section](https://github.com/mozilla-iam/cis/blob/4465e56e85ca82408b3fd35ac3a717de23890d7b/serverless-functions/webhook_notifier/serverless.yml#L40)

```
  webhookEnvironment:
    CIS_RP_URLS:
      production: https://people.mozilla.org/events/update,https://discourse-staging.itsre-apps.mozit.cloud/mozilla_iam/notification,https://discourse.mozilla.org/mozilla_iam/notification
      development: https://dinopark.k8s.dev.sso.allizom.org/events/update
      testing: https://dinopark.k8s.test.sso.allizom.org/events/update
```

Finally we can see that the config setting of `self.config("rp_urls", namespace="cis", default="https://dinopark.k8s.dev.sso.allizom.org/events/update")`

equals 

`https://people.mozilla.org/events/update,https://discourse-staging.itsre-apps.mozit.cloud/mozilla_iam/notification,https://discourse.mozilla.org/mozilla_iam/notification`
