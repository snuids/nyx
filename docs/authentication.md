[Back](README.md)

# Signing in: the ways in, and how to configure each one

An account can be opened in four different ways, and each one is switched on or off by configuration
alone — no code change, no rebuild. This page says what each way needs, what it accepts, and what it
refuses. The API contract of the routes is in [REST API](api.md); the behaviour of the code is in
`nyx_rest/sources/routes/auth.py` and `nyx_rest/sources/lib/*_oauth.py`, and when this page and the
code disagree, the code wins and this page is a bug.

The rule that holds for all of them:

> **The provider says who you are. `nyx_user` says what you may open.**

No way in creates privileges. A provider that answers with an identity nobody has filed gets
`Bad Credentials` — like a wrong password — or, if the instance is configured for it, a **disabled**
account an administrator still has to activate and grant. Nothing about signing in with Microsoft or
GitHub makes somebody an administrator.

## The ways in at a glance

| Way in | Route | Switched on by | Console button | May create an account |
| --- | --- | --- | --- | --- |
| Password | `POST /cred/login` | always | the form | no (accounts are created from the console) |
| Password + SMS code | same, `doublecode` | `doublePhase: true` on the account | the form | — |
| Active Directory / LDAP | same | `AD_SERVER`, `AD_DOMAIN`, `AD_BASE_DN` | the form | yes, from the directory groups |
| GitHub | `GET /cred/oauth/state` + `POST /cred/login_sso` | `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI` | *Sign in with GitHub* | only with `GITHUB_UNKNOWN_ACCOUNTS=inactive`, disabled |
| Microsoft Entra ID | same | `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, `ENTRA_REDIRECT_URI` | *Sign in with Microsoft* | only with `ENTRA_UNKNOWN_ACCOUNTS=inactive`, disabled |
| Google (legacy) | `POST /cred/login_google` | `CLIENT_SECRET_FILE` | none in this release | no |
| Impersonation | `POST /cred/login` with `admin>user` | an `admin` account | the login field | — |

The console shows a button only when `/api/v1/config` says the API can run that exchange, so a
half-configured provider cannot produce a sign-in that fails after the redirect:

```json
{"error": "", "version": "3.22.38",
 "login": {"github": true, "entra": false},
 "...": "…"}
```

## The account document

One Elasticsearch document per person, in `nyx_user`.

| Field | Meaning |
| --- | --- |
| `_id` | the address (`amarchand@icloud.com`) or a short name (`amarchand`) — **not necessarily what the person types** |
| `login` | the short name shown in the console and stamped on records as the author |
| `privileges` | what the account may open (`admin`, `user`, or the application privileges) |
| `filters` | default filters of the screens it opens |
| `language`, `theme` | preferences, written by the console |
| `inactive` | **absent means active.** `true` refuses the sign-in (`ACCOUNT_INACTIVE`) and cuts a live session |
| `mustResetPassword` | a provisional password: the token opens the password change and nothing else |
| `doublePhase`, `phone` | the SMS second factor, and where to send it |
| `source`, `created` | set by a provider-filed account: `github` / `entra`, and when |

Eight production accounts are indexed under their address while `login` holds a short name. Every
sign-in therefore tries **both**: the document id first, then `login.keyword` — that pair of lookups
lives in `find_account()` and is the same one the password form uses.

An account filed by a sign-in carries **no `password` field at all**. It can only come in through its
provider; a password attempt on it is refused like any other wrong credential. To give it a password
as well, an administrator resets one — which sets `mustResetPassword` and forces a new one at the
first password login.

## What every sign-in has in common

Whatever the way in, the route ends on `finalize_login()`, which mints the session token (a UUID;
**5 minutes** in worker memory, **24 hours** in Redis), loads the menus, sets the per-tool cookies
read by nginx (24 h), and refuses an `inactive` account — the single place that rule is written, so
the fourth provider added no second copy of it.

```
browser                      API                                   provider
   |                          |                                       |
   |-- GET /cred/oauth/state ->|  one-time state in Redis (10 min)     |
   |                          |  + HttpOnly cookie, SameSite=Lax      |
   |<-- {url, provider} ------|                                       |
   |-- redirect ---------------------------------------------------->|
   |                          |                       consent, MFA   |
   |<-- https://HOST/oauth?code=…&state=… ---------------------------|
   |                          |                                       |
   |-- POST /cred/login_sso ->|  state == cookie? (one use)           |
   |   {code, state}          |  provider from the state record       |
   |                          |-- exchange (TLS, server-side) ------->|
   |                          |<-- identity (aud, tid, iss, nonce) ---|
   |                          |  find_account -> nyx_user             |
   |                          |  finalize_login -> our own token      |
   |<-- {cred, menus, ...} ---|                                       |
```

Three properties of that shape matter when something goes wrong:

- **the `state` is single-use and bound to the browser** (Redis + a `nyx_oauth_state` cookie). A code
  and a state prepared elsewhere cannot sign anybody in: that is the login-CSRF guard.
- **the provider's token is used and dropped.** It never becomes the session token and is never
  stored: it would be a second secret, with a lifetime we cannot revoke.
- **the console has one return page** (`/oauth`). It posts the code and the state and nothing else;
  the API reads the provider from the state record, so the page cannot choose the exchange.

## Password

The form, and the reference for the rest of this page.

- **Policy**: 12 characters minimum, and not the login. Composition rules (upper, digit, symbol) are
  deliberately not imposed — they produce predictable passwords.
- **Provisional passwords**: an account created without one gets a random password nobody knows plus
  `mustResetPassword`. While the flag is set the token opens `/cred/changepassword`, `/cred/logout`,
  `/healthz` and `/metrics` — nothing else. The change is a condition of access, not a courtesy of
  the interface.
- **Brute force**: five free attempts per account and per IP inside a 5-minute window, then a 429 with
  `Retry-After`; ten failures add five minutes, twenty add an hour. Never a permanent block, which
  would turn an attack into a denial of service against its own user. Nothing is spent on the hash
  while the account is throttled.
- **Second factor**: `doublePhase: true` sends a five-digit code by SMS (`/topic/AUTH_SMS`) to the
  account's `phone`; it lives 120 s in Redis and is consumed by the first use. The answer is
  `{"error": "DoublePhase"}`, then the same call with `doublecode`.
- **Impersonation**: `admin>user` typed in the login field signs an administrator in *as* another
  account. The target must be given **as its document id** — a short login answers `Unknown User`.

## Microsoft Entra ID

The corporate directory, over OIDC. Four settings; until all four are present the button is hidden and
`/cred/oauth/state?provider=entra` answers `entra login not configured`.

```shell
ENTRA_TENANT_ID=00000000-0000-0000-0000-000000000000   # Directory (tenant) ID — a GUID
ENTRA_CLIENT_ID=...        # Application (client) ID
ENTRA_CLIENT_SECRET=...    # its secret — never reaches the browser
ENTRA_REDIRECT_URI=https://HOST/oauth   # the console's return page, absolute
ENTRA_UNKNOWN_ACCOUNTS=inactive         # refuse (default) or inactive — see below
```

`ENTRA_TENANT_ID` must be the **directory id**, not the domain name: every claim is compared against
it, and a name is read as "not configured" — the button stays hidden instead of leading to a sign-in
that fails afterwards, which looks like a wrong password.

### The application registration

| On the registration | Value | Why |
| --- | --- | --- |
| Supported account types | *Accounts in this organizational directory only* | one directory is the security boundary |
| Redirect URI platform | **Web** | the code is exchanged server-side with the secret; a *Single page application* registration has no secret |
| Redirect URI | `https://HOST/oauth` | the console's return page, the same value GitHub uses |
| API permissions (delegated) | `openid`, `profile`, `email` | the identity is read from the ID token; no Graph call is made, so `User.Read` is not asked for |
| Certificates & secrets | a client secret | **it expires** (24 months at most) |

The secret is an operational object: when it expires, every Entra sign-in answers `invalid_client`
and the fix is a new secret and a restart — put the rotation on a calendar.

### What the API checks, and why

The identity token must be issued **for this application** (`aud`), **by this directory** (`tid`, with
an `iss` that repeats it), inside its validity window (`exp`/`nbf`, 300 s of tolerance), and answer the
**`nonce`** this browser was given. Without the `tid` check, any Entra tenant could present a user
holding one of our addresses.

Its **signature is not verified**, and does not need to be: the token is read from the token endpoint's
own answer, over the TLS connection this confidential client opened, which is the server validation
OpenID Connect Core accepts in place of a signature check for that case (§3.1.3.7). Nothing is ever
read from an `id_token` a browser sends.

### Which account it lands on

The address the directory vouches for: the `email` claim, or `preferred_username` (the sign-in name)
when the directory sets none. No short name is derived and tried — a local part would match an account
whose address the identity does not hold. A filed account takes the address as its `_id` and the local
part of the sign-in name as its `login`.

Microsoft validates the password, the MFA and the conditional access: NYX never sees a Microsoft
credential, and the `doublePhase` SMS of the password route does not apply.

## GitHub

The same story on GitHub's side, with three settings:

```shell
GITHUB_CLIENT_ID=...        # the OAuth app's client id
GITHUB_CLIENT_SECRET=...    # its secret — never reaches the browser
GITHUB_REDIRECT_URI=https://HOST/oauth
GITHUB_UNKNOWN_ACCOUNTS=inactive   # refuse (default) or inactive
```

On GitHub: *Settings → Developer settings → OAuth Apps → New OAuth App*, homepage `https://HOST`, and
the **Authorization callback URL** `https://HOST/oauth`. No scopes to request beyond the default; the
sign-in asks `read:user user:email`.

What the identity carries, and what it cannot:

| Field | Source |
| --- | --- |
| `login` | the GitHub login, always present |
| `firstname` / `lastname` | the profile's `name`, split on the last space; empty when the profile has none, and `firstname` then falls back on the login |
| `email` | only a **verified** address from `/user/emails`. An address typed but never confirmed is logged and **not** stored: it is not a key anyone should trust |
| `phone` | nothing — GitHub has no phone field, on the profile or in the API |

The account is matched on that verified address first, then on `login.keyword` (the short-name case).

## Google (legacy)

`POST /cred/login_google {auth_code}` still works, but it is the oldest path of the three and differs
in two ways worth knowing before relying on it: it takes a **Google client-secrets file** rather than
individual settings (`CLIENT_SECRET_FILE`), and the token it returns is stored for **one hour**, where
the other sign-ins keep theirs for 24. There is no button for it in this console; a client that calls
the route directly is the only user.

## Active Directory / LDAP

Not a button: a fallback. When the stored password does not verify — including when there is no
`nyx_user` document at all — the login is tried against the directory.

```shell
AD_SERVER=ldap://dc1.example.com:389,ldap://dc2.example.com:389   # comma separated
AD_DOMAIN=EXAMPLE
AD_BASE_DN=DC=example,DC=com
GROUP_ROLE_MAP={"NYX-Users": "user", "NYX-Admins": "admin"}
```

- The bind is NTLM as `<DOMAIN>\<login>`; an address (`user@domain`) is reduced to its local part
  for both the bind and the `sAMAccountName` search. A successful bind **is** the acceptance: the
  directory entry is only read to take the name and the groups, and a bind that finds no entry still
  signs the person in.
- `GROUP_ROLE_MAP` translates the directory's group CNs (from `memberOf`) into NYX privileges. No
  mapping means `["user"]` — a level to be aware of: anybody the directory accepts can open the
  console with the base privilege. A group granting `admin` is a decision, and it is this line.
- The session is minted from the directory answer, **without** a `nyx_user` document: the person has
  no preferences and no per-account disable until someone files them. If accounts must be
  administratively controlled, do not configure AD and use Entra ID instead — there, an identity with
  no document is refused.

## Identities nobody has filed

Each provider decides, on its own, what happens to an identity with no account:

| `*_UNKNOWN_ACCOUNTS` | Behaviour |
| --- | --- |
| `refuse` (default) | `Bad Credentials`, the same answer as a wrong password. Nothing is written. |
| `inactive` | a `nyx_user` document is created **disabled and without privileges**, and the sign-in answers `ACCOUNT_INACTIVE` — the console shows the page that says so. |

Anything else is read as `refuse`: a misspelt value must not open a door. Filing an account grants
nothing — an administrator clears `inactive`, grants the privileges, and the person then signs in
through the provider without ever holding a password here. The accounts waiting there are visible in
the users list with the *inactive* filter.

## Auditing and troubleshooting

Every refusal is written to `nyx_authfail-YYYY.MM.DD` (kept seven days by the curator), with the
login, the IP and the User-Agent: the login route is the only one reachable without a token, so
without that line an attack would leave no trace.

| `reason` | Meaning |
| --- | --- |
| `BAD_CREDENTIALS` | wrong password, unknown account, or a directory that refused |
| `LOCKED` | refused before any verification: the brute-force ladder |
| `DOUBLE_PHASE` | wrong SMS code |
| `OAUTH_STATE` | unknown, already used, or issued to another browser |
| `OAUTH_PROVIDER` | a state issued for one provider posted to the other's callback |
| `GITHUB_EXCHANGE`, `ENTRA_EXCHANGE` | the provider refused the code, or answered something unusable |
| `NO_ACCOUNT_GITHUB`, `NO_ACCOUNT_ENTRA` | a correct identity, no account, policy `refuse` |

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| no provider button on the sign-in screen | `/api/v1/config` answers `login.x: false` | one setting is empty — and for Entra, check that the tenant is a GUID |
| `github login not configured` / `entra login not configured` | same, from `/cred/oauth/state` | same |
| `AADSTS700038` at the redirect | the client id does not exist in that directory | tenant id and client id are from two different directories |
| `AADSTS50011` at the redirect | the redirect URI is not registered, or differs by a slash | register `https://HOST/oauth` exactly |
| `AADSTS9002327` | the registration is a *Single page application* | recreate the platform as **Web** and use the client secret |
| `invalid_client` in the API log | the Entra secret expired | new secret, restart `nyx_restapi` |
| `Bad Credentials` from `/cred/login_sso`, while the provider login works elsewhere | no `nyx_user` whose `_id` or `login` matches the address | create the account, or set `*_UNKNOWN_ACCOUNTS=inactive` and activate it |
| `ACCOUNT_INACTIVE` | the account is disabled | clear `inactive` in the users list |
| `429 TOO_MANY_ATTEMPTS` | the ladder | wait `retry_after`, or clear `loginfail:*` in Redis |
| a disabled person keeps working for a moment | tokens live 5 min in worker memory / 24 h in Redis, and the disabled check is cached one minute | it clears within a minute; there is no need to restart anything |

## Adding a fifth way in

The three OAuth providers share everything after the exchange, so a new one is a module and a handful
of lines:

1. `nyx_rest/sources/lib/<provider>_oauth.py` — the authorize URL, the code exchange, and the claims
   checks. It must return the same profile shape every other provider returns (`login`, `email`,
   `name`, `firstname`, `lastname`) and must never return a provider token to its caller.
2. `sources/routes/auth.py` — add the name to `PROVIDERS`, a `*_configured()` test, a branch in
   `fetch_oauth_profile()` and in `oauth_candidates()`, and a thin route (`/cred/login_<provider>`)
   that calls `complete_oauth_sign_in("<provider>")`. `/cred/login_sso` already handles it.
3. `sources/routes/misc.py` — `login.<provider>` in `/config`, from the same test as the route.
4. `nyx_ui` — a button in `Login.vue` gated on that flag, its label in the four language files, and a
   key in the `sso.*` block if the return page must say something new.
5. Tests: a module test file (hand-built tokens, each refusal) and route cases in
   `tests/test_routes_auth.py` — the wrong-provider callback and the two policies are the ones that
   bite.

## What must not change

- The provider's token is **never** stored, and never becomes the session token.
- An identity is matched on an address the provider vouches for — never on one anybody could type.
- `inactive` is enforced in `finalize_login`, after the credential is verified, and is not counted as
  a wrong password.
- A `state` is single-use, kept server-side, and bound to the browser that received its cookie.
- Nothing a provider answers creates privileges. An administrator does.
