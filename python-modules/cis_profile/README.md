# moz_iam_profile

This library is a dynamic class-constructor for the Mozilla IAM profiles (v2).
It takes the Mozilla IAM default profile and schema, and creates a Python class from it dynamically.

This means that the default profile (JSON file: user_profile_null.json) and schema can be changed without
affecting the class code (to some degree).

## Example usage

### Using profiles

```
from cis_profile import User
skel_user = User(user_id="bobsmith")
skel_user.user_id.value = "notbobsmith"
if skel_user.validate():
  profile = skel_user.as_json()

user = { exiting...user..json }
skel_user2 = User(profile_structure_json=user)
skel_user2.fun_title.value = 'New title!'
skel_user2.sign_attribute('fun_title', 'ldap')
```

### Faking profiles

```
from cis_profile import FakeUser
user = FakeUser()
print(user.first_name.value)
# Jim
```

## About tests

`cis_crypto` must be setup and function for tests to run, see the `cis_crypto` module if is it not setup (in particular
keys must be created)
