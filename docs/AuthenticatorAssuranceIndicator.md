# Authenticator Assurance Indicator (AAI)

The Authenticator Assurance Indicator (AAI) is a list of indicators that the session has been authenticated with known,
validated technical proofs the user has been authenticated securely.

Sets of indicators are grouped into Authenticator Assurance Levels which are mapped after 
[Mozilla's Standard Levels](https://infosec.mozilla.org/guidelines/risk/standard_levels)

The levels allow for the consumers of the claim or assertion to quickly determine how much assurance - or trust,
confidence, the authenticator has declared to have for this user.

A mapping is available in the [CIS Well-Known endpoint](Well-Known Endpoint.md).

## Example

User A utilizes 2FA to authenticate and their web browser has a known unique identifier set in a cookie (which allows
the authenticator to known that the same browser is returning).

*Authenticator Assurance Indicator for user A*

`user[A].aai = ["2FA", "HAS_KNOWN_BROWSER_KEY"]`

*Authenticator Assurance Level for user A*
`user[A].aal = "MEDIUM"`

A relying party which requires AAL MEDIUM will let this user login. If it requires HIGH, for example, it would deny User
A access. Alternatively, it may require the user to login again using all credentials in it's possession (such as
password, 2FA OTP, Phone OTP and security question - where all 4 would be required to login)

**NOTE**: Certain relying parties (RP) may also accept AAL LOW for example, but perform it's own additional checks based
on the user's AAI or AAL values. The RP may want to require specifically `AAL=MEDIUM` and AAI to contain 2FA for admin
users for example,. but `AAL=LOW` may be acceptable for regular users.

# Standard Levels summary

These levels are further detailed on [Mozilla's Standard
Levels](https://infosec.mozilla.org/guidelines/risk/standard_levels)

Each level inherit from the previous.

- UNKNOWN: The system was unable to determine the level and this should otherwise be considered LOW.
- LOW: Often first-time-seen users, without any particular assurance.
- MEDIUM: Default, a balance of confidence that the account is trusted. Generally requires 2FA.
- HIGH: Generally requires strong proof the user authenticated correctly using similar patterns to past authentications.
- MAXIMUM: Maximum level of assurance, requires the current cutting edge authenticators such as webauthn + strong proof
  the user possess the webauthn token.

# Known Authenticator Assurance Indicators

This is a list of known Assurance indicators. They may or may not all be in use by CIS.

- NO_RECENT_AUTH_FAIL: No user authentication failure in the past 30 days.
- AUTH_RATE_NORMAL: No recent (7 days) burst of user authentication requests such as 10 requests within 1 second.
- 2FA: User authenticated using 2 factors, such as password + OTP device.
- HAS_KNOWN_BROWSER_KEY: The user's web browser has a unique key known by the authenticator, which indicates that the
  same browser has returned to the authentication screen ("same device").
- HIGH_ASSURANCE_IDP: An IDP (Identity Provider) which has been considered to have significant controls but cannot be
  technically asserted because it does not indicate exactly which controls were used (e.g.: Google IDP).
- GEOLOC_NEAR: User's last authentication request was within realistic geographical range of the previous request. For
  example, if the user logged in 5min ago from Moscow, RU and is now logging in from Brisbane, AU - this is considered
physically impossible and GEOLOC_NEAR will not be set. (Fraud detection systems may also alert the user independently)
- SAME_IP_RANGE: User's last authentication request is within the same range according to WHOIS data, i.e. same ISP
  block.
- KEY_AUTH: User's authentication token uses asymmetric public key cryptography.
