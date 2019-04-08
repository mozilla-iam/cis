# Guide to understanding the user profile rules

This is a reference document to understand how to read the profile rules.
This will tell you how to understand:

- which ranges of display (i.e. user intent to display the field) are allowed per field
- which data classification (RP field access) is allowed per field
- which defaults are used for display values when a range is allowed
- how to read the schema

## Understand the user profile defaults

Remember that these are *DEFAULTS* and that users can and will override them.

The profile defaults are sourced from the "null" profile (contains only `null` field attribute values). Find it here:
- Null Profile https://github.com/mozilla-iam/cis/blob/master/python-modules/cis_profile/cis_profile/data/user_profile_null.json
- Null Profile (parsed / easier to naviguate) https://codebeautify.org/jsonviewer/cb360eb5

### Special case for display defaults only

Publishers, such as the LDAP or HRIS publisher may override display defaults in code as they publish new users. Defaults are only overriden for attributes that were previously unset (i.e. `null` but not empty strings or lists, arrays). For example, the LDAP publisher will override `first_name.metadata.display` to `staff` as well as many other fields.

- For LDAP, see https://github.com/gdestuynder/auth0-scripts/blob/profilev2/LDAP/ldap2s3/ldap2s3.py#L187 for example
- For HRIS, see https://github.com/mozilla-iam/cis/blob/master/python-modules/cis_publisher/cis_publisher/hris.py#L210 for example

## Read the user profile display allowed values

Ranges of values are allowed for the `metadata.display` value, for each field. These are enforced by https://auth.mozilla.com/.well-known/profile.schema and cannot be bypassed.

Look for "DinoParkDisplay" for a list of acceptable values, which are currently:

-	"public"
- "authenticated"
-	"vouched"
-	"ndaed"
-	"staff"
-	"private"

Each field has a set of rules which will indicate the rule used for display. Currently the rules available per field are:

- DisplayAnyValue: Any of the values are allowed.
- DisplayNone: Only `null` is allowed, this mean the field is not meant for user display.
- DisplayPublicOnly: Only "public" is allowed. This field cannot be hidden from users.
- DisplayStaffOnly: Only "staff" is allowed. This field cannot be hidden from staff.
- DisplayStaffNDAOnly: Onll "staff" and "ndaed" are allowed. This field cannot be hidden from staff and NDAed.

# Understand the publishing rules

The rules are available at https://auth.mozilla.com/.well-known/mozilla-iam-publisher-rules

Anything under the `create` indicates which publisher is allowed to first create data for the field. For example, in `create.first_name` you find:
-	"ldap"
-	"hris"
-	"access_provider"
-	"mozilliansorg"

This means any of these publishers can create `first_name`. This only applies if `first_name` does not yet exist (i.e. is set to `null`). Once a field is created it cannot be deleted (only the whole profile can be deleted).

Under `update` you will find which publisher is allowed to change the field value. This what is used who can change the value after the field has been created and can only contain a single publisher. For example, in `update.first_name` you find `"mozilliansorg"` - this means only that publisher is allowed to change the value once created.

# Understand the user profile schema (advanced)

The schema is available at https://auth.mozilla.com/.well-known/profile.schema
I recommend that you collapse all fields for reading it as it's quite a big file of rules.

The `definitions.Profile.properties` section contains all the profile base fields (`user_id`, `uuid`, `first_name`, ...). Most of these fields contain signatures, metadata and their actual value(s).

Certain fields contain extended lists of values such as `identities`, `staff_information` and `access_information`. The specification of these fields is stored in `definition.StaffInformationValuesArray.properties` for `staff_information` for example, while `definitions.Profile.staff_information` only holds a reference to it.

There are several additional structures under `definitions.*` which indicate all available values for the various classifications, metadata, signature, display, etc. field specification. You only need to read these if you want to understand which kind of classifications, metadata, signature, etc. are allowed.

Here's an example field: `first_name`

Under `definitions.Profile.properties.first_name` you will find:
```	
allOf:
0	
 $ref	"#/definitions/DisplayAnyValue"
1	
 $ref	"#/definitions/StandardAttributeString"
2	
 $ref	"#/definitions/ClassificationPublic"
$comment	"Preferred first name for the user (not necessary a legal name)."
```

Translation:
- `first_name` allows `DisplayAnyValue` (Any display value may be set in `first_name.metadata.display`
- `first_name` requires `ClassificationPublic` (Mozilla Data Classification is Public) set in `first_name.metadata.classification`
- `first_name` is a `StandardAttributeString` (i.e. it's just a string and it's value will be set in `first_name.value`)

You can lookup `StandardAttributeString` if you're curious about the entiere structure rules. You'll see it contains a property for `value` (the actual first name in this case!) and a reference to `Signature` and `Metadata` properties. You can dig deeper and also lookup these properties to find how they're constructed.

# Appendix

## Easy to read list of rules per field:

This is generated and picks defaults from the null profile, and display rules, classification from the schemna.

- https://codebeautify.org/jsonviewer/cb0c1642 
