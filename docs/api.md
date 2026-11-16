[Back](README.md)

# REST API

Flask-RESTX application served by gunicorn on port 8000, reached through nginx at `/api/`.
This page describes the contract as implemented in `nyx_rest` 3.21.x. When it disagrees with
`nyx_rest/sources/routes/*.py`, the code is right.

## Documentation endpoints

| URL | What it is |
| --- | --- |
| `/api/doc/` | interactive Swagger UI (this is the one to bookmark) |
| `/swagger.json` | the OpenAPI description, for code generation |
| `/swaggerui/...` | the static assets the Swagger UI loads — not a page by itself |

## Authentication

Configuration of each way in — password, Active Directory, GitHub, Entra ID — the policies that decide
who is let through, and the troubleshooting table are in [Signing in](authentication.md). What follows
is the API contract.

Almost every route takes a token. Two forms are accepted, and the header is preferred:

```shell
curl -sk -H "Authorization: Bearer $TOKEN" https://HOST/api/v1/status   # since 3.22.1
curl -sk "https://HOST/api/v1/status?token=$TOKEN"                      # historical form
```

The query parameter ends up in nginx access logs, browser history and `Referer` headers, so it is
kept only for the console and the mobile app to keep working. Running the API log at `DEBUG` names
the routes that still receive it.

```shell
TOKEN=$(curl -sk -X POST https://HOST/api/v1/cred/login \
  -H 'Content-Type: application/json' \
  -d '{"login":"admin","password":"..."}' | jq -r .cred.token)

curl -sk "https://HOST/api/v1/generic_search/nyx_app?token=$TOKEN" \
  -H 'Content-Type: application/json' -d '{"size":10}'
```

- The token is a UUID stored in Redis for 24 h; the API also caches it in memory for 5 minutes.
- Signing in also sets one cookie per tool the user may reach (`nyx_kibana`, `nyx_nodered`, …).
  They are read by nginx, not by the API.
- `POST /api/v1/cred/login` accepts `app` to filter the returned menus for the mobile app.
- Users marked `doublePhase` receive `{"error": "DoublePhase"}` and a code by `/topic/AUTH_SMS`;
  call again with `doublecode`.
- LDAP/AD is tried when the local password check fails (`AD_SERVER`, `AD_DOMAIN`, `AD_BASE_DN`,
  `GROUP_ROLE_MAP`).
- `/api/v1/lambdas/*` is the only route that accepts `?apikey=` instead of a token, and that
  key must be a `nyx_apikey` document: a session token is refused since `nyx_rest` 3.22.23.
- Every authenticated call is recorded in `nyx_apicalls-YYYY.MM.DD` with a **fingerprint** of the
  token, never the token itself.

### Signing in with GitHub

An account can sign in from its GitHub identity instead of a password. GitHub says **who** you are;
`nyx_user` still decides **what you may open** — an identity with no account is refused, and nothing
is provisioned on the fly.

```shell
# 1. what to open, and the cookie that goes with it
curl -sk -c jar.txt https://HOST/api/v1/cred/oauth/state
# {"error": "", "url": "https://github.com/login/oauth/authorize?..."}

# 2. the browser comes back to https://HOST/oauth?code=...&state=...
curl -sk -b jar.txt -X POST https://HOST/api/v1/cred/login_github \
  -H 'Content-Type: application/json' -d '{"code":"...","state":"..."}'
```

- Three settings are needed: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI`
  (the registered callback, `https://HOST/oauth`). Until all three are set the route answers
  `{"error": "github login not configured"}` and `/config` says `login.github: false`, so the console
  shows no button.
- `state` is one-time (Redis, 10 min) **and** must match an HttpOnly `nyx_oauth_state` cookie: a
  state obtained in another browser cannot sign anybody in, which is what stops a login CSRF.
- The account is matched on a **verified** e-mail from GitHub (primary preferred), then on
  `login.keyword`. A refused identity is written to `nyx_authfail-*` with `NO_ACCOUNT_GITHUB`.
- The GitHub access token is used and dropped: the session token is minted by the platform like any
  other login, and the provider token is never stored.
- The accounts still need `login`, `language` and `privileges` — `computeMenus()` builds the console
  menus from them, as with a password login.

### Signing in with Microsoft Entra ID

The same contract, for a directory instead of a profile: `nyx_user` still decides what you may open.

```shell
# 1. what to open, and the cookie that goes with it
curl -sk -c jar.txt 'https://HOST/api/v1/cred/oauth/state?provider=entra'
# {"error": "", "url": "https://login.microsoftonline.com/<tenant>/oauth2/v2.0/authorize?...",
#  "provider": "entra"}

# 2. the browser comes back to https://HOST/oauth?code=...&state=...
curl -sk -b jar.txt -X POST https://HOST/api/v1/cred/login_sso \
  -H 'Content-Type: application/json' -d '{"code":"...","state":"..."}'
```

- Four settings: `ENTRA_TENANT_ID` (the **directory id**, a GUID — not `contoso.com`),
  `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, `ENTRA_REDIRECT_URI` (the registered callback,
  `https://HOST/oauth`, platform **Web**). Until all four are set the route answers
  `{"error": "entra login not configured"}` and `/config` says `login.entra: false`.
- The identity token is read from the token endpoint's answer and checked: `aud` is the client id,
  `tid` is the configured directory, `iss` repeats that directory, `exp`/`nbf` are current, and
  `nonce` is the one this browser was given. Nothing is read from a token a browser sends.
- The account is matched on the `email` claim, then on `preferred_username` — full addresses the
  directory vouches for, never a short name derived from them. A refused identity is written to
  `nyx_authfail-*` with `NO_ACCOUNT_ENTRA`; `ENTRA_UNKNOWN_ACCOUNTS=inactive` files a disabled
  account instead, exactly as `GITHUB_UNKNOWN_ACCOUNTS` does.
- `cred/login_sso` takes either provider: the state record kept in Redis says which one issued it,
  so the return page does not have to know. `cred/login_entra` names Entra explicitly.
- MFA and conditional access are Microsoft's: NYX never sees a Microsoft credential, and the
  `doublePhase` SMS of the password route does not apply.

Roles are checked with `@token_required(...roles)`: `admin` always passes, other users need one
of the listed privileges. Role checks do **not** protect data — that is the index-level rule
described in the [data model](data-model.md#access-rules-nyx_indice).

## Routes

All paths below are relative to `/api/v1/`.

| Method and path | Body / parameters | Returns |
| --- | --- | --- |
| `POST cred/login` | `{login, password, app?, doublecode?}` | `{version, error, cred:{token,user}, menus, all_priv, all_filters}` |
| `POST cred/login_google` | `{auth_code, app?}` | same shape |
| `GET cred/oauth/state` | `?provider=github\|entra` | `{error, url, provider}`, plus the one-time `nyx_oauth_state` cookie |
| `POST cred/login_sso` | `{code, state, app?}` | same shape as `cred/login`; the provider is the one the state was issued for |
| `POST cred/login_github` | `{code, state, app?}` | same shape; GitHub only |
| `POST cred/login_entra` | `{code, state, app?}` | same shape; Entra ID only |
| `GET cred/logout` | `?token=` | `{error:""}`, invalidates the token everywhere |
| `POST cred/changepassword` | `{old_password, new_password}` | `{error:""}` or `wrongpassword` |
| `POST cred/resetpassword` | `{login, new_password, queue?}` — roles `admin`, `useradmin` | `{error:""}` |
| `POST generic_search/<index>` | Elasticsearch query body | `{error, took, total, records, aggs}` |
| `POST pg_search/<appid>` | `{size, page, query, range}` | same shape, from the SQL application |
| `POST queryFilter/<rec_id>` | `{selected[], timerange?}` | the app's query filters, with their buckets |
| `GET datasource/<dsid>` | `?start=&end=&flat=` | `{error, records}`, or the bare array with `flat` |
| `GET generic/<index>/<id>` | `?doc_type=` | `{error, data, seq_no?, primary_term?}`, with the version as `ETag` |
| `POST generic/<index>/<id>` | the document, `If-Match: "<seq_no>-<primary_term>"` (optional) | `{error, seq_no, primary_term}`; hashes `password` for `nyx_user`; **409** on a stale version |
| `DELETE generic/<index>/<id>` | `If-Match` (optional) | `{error:""}`; **409** on a stale version |
| `GET/POST/DELETE pg_generic/<table>/<col>/<pk>` | `?app=<rec_id>`, body `{record:{...}}` | `{error, data, columns}` |
| `POST listdir` | `{rec_id, path}` | directory listing |
| `GET files` | `?rec_id=&path=&files=a,b` | the file, or a ZIP when several are requested |
| `POST files` | `{files:[{file_name, data}]}` (base64) | `{error:""}` |
| `GET streamfile` | `?file=/absolute/path` | last 32 kB of a file, text |
| `POST upload` | multipart `file`, `?queue=` | publishes to the broker, `{error:""}` |
| `GET reloadconfig` | — | recomputed menus for the current user |
| `GET healthz` | — | liveness of Elasticsearch, Redis and the broker (**no token**), 503 when one is down |
| `GET metrics` | — | Prometheus exposition of the same checks plus per-worker counters (**no token**) |
| `GET config` | — | instance configuration (**no token required**) |
| `GET status` | — | `{status, version, name}` (**token required**) |
| `POST sendmessage` | `{destination, body, headers?}` | writes straight to the broker |
| `GET esmapping/<pattern>` | — | mappings of the matching indices |
| `POST lambdas/<runner>/<name>` | arbitrary JSON, `?apikey=` | the lambda return value |
| `GET grafana/dashboards` | — | dashboards visible to the configured Grafana token |
| `POST kibana_load` | `?token=&output=` | export of the dashboard query captured by nginx |
| `GET onfleet_webhook` | `?check=` | echoes the value as `text/plain` (Onfleet's validation) |
| `POST onfleet_webhook` | Onfleet payload + `X-Nyx-Webhook-Secret` (or `?secret=`) | forwards to `/topic/ONFLEET_WEBHOOK`; **503** when `ONFLEET_WEBHOOK_SECRET` is not configured, 403 on a wrong secret |
| `GET config/export` | `?indices=` (optional), admin | the platform design as one JSON bundle (from `nyx_rest` 3.22.0) |
| `POST config/import` | bundle in the body, `?apply=1`, `?prune=1`, admin | the plan, then what was applied |
| `GET ui_css` | — | the instance stylesheet |

## Exports

Add `?download=1&output=csv` (or `xlsx`) to `generic_search`, `pg_search` or `kibana_load`:

- below the threshold, the file is written to the API's `OUTPUT_FOLDER` and the response carries
  `{type: "direct", url, file}` — the URL is public under `/generatedreports/rapi/`;
- above it (5000 rows for Elasticsearch and SQL, 3000 rows for Kibana), the export is pushed to
  the broker and the response is `{type: "mail"}`: `nyx_rest_helper` produces the file and mails
  it using the `SMTP_*` settings.

`exportColumns` in the request body limits and renames the columns (`"field->Header"`), and dates
are converted to the container's timezone.

## Concurrent writes

Two operators editing the same record used to overwrite each other in silence: `POST
generic/<index>/<id>` indexed whatever the last browser had loaded. Since `nyx_rest` 3.22.39 the
write route honours a **precondition**, which the console sends for every row it edited:

```
GET  generic/rows/42            -> 200, ETag: "7-1", {"error":"", "data":{...}, "seq_no":7, "primary_term":1}
POST generic/rows/42            -> 200, {"error":"", "seq_no":8, "primary_term":1}
     If-Match: "7-1"
POST generic/rows/42            -> 409, {"error":"conflict", "data":{<the document that won>}, "seq_no":9}
     If-Match: "7-1"               (someone else saved in between: nothing was written)
```

- The header is `<seq_no>-<primary_term>`, the two numbers Elasticsearch keeps per document; a bare
  `"7"` is accepted (primary term 1), `W/` is stripped. `?seq_no=7&primary_term=1` works too, for a
  client that cannot set a header.
- `If-Match: *` means the document must **exist** (a save must not resurrect a row deleted
  meanwhile) and answers **412** when it does not.
- An unreadable header is a **400** (`bad If-Match`): a check silently turned into "no check" is
  worse than no check.
- **The header stays optional.** A write without it keeps the historical last-write-wins behaviour,
  which is what the workers, the mobile clients and the integrations rely on. The PostgreSQL
  applications are not covered: their tables carry no version column to compare.
- `generic_search` asks the cluster for `seq_no_primary_term`, so every row of a list carries
  `_seq_no`/`_primary_term` and the console's cell editor can assert them; the conflict body never
  contains a `nyx_user` password hash.

## Errors

Errors carry `{"error": "<code>"}`. Since `nyx_rest` 3.22.23 the **refusals of the token check**
answer their own status — 401 for `NO_TOKEN` / `UNKNOWN_TOKEN` (with `WWW-Authenticate: Bearer`), 403
for `NO_PRIVILEGE` / `MUST_CHANGE_PASSWORD` — while every other error keeps HTTP 200, because the
console reads that body in `.then()`. So: check the status for "am I authenticated", the `error`
field for "what went wrong".

| Code | Meaning |
| --- | --- |
| `NO_TOKEN` / `UNKNOWN_TOKEN` | missing or expired token |
| `NO_PRIVILEGE` | the route requires a privilege the user does not have |
| `Not Allowed` | the index rule refused the query for this user |
| `Bad Credentials` | wrong login or password |
| `DoublePhase` / `ErrorDoublePhase` | a second-factor code is required / rejected |
| `MISSING_PARAM:<name>` | the body lacks a required field |
| `unknown app` / `not allowed` | file or application access refused |
| `invalid SQL identifier` / `invalid record` | rejected SQL CRUD request |
| `No answer` / `Unknown lambda or lambda crashed` | the lambda did not reply within 5 s |

## Promoting a configuration between instances

`nyx_rest` 3.22.0 exports the design of an instance — screens (`nyx_app`), index rules
(`nyx_indice`), privileges, filters, translations, named queries — as one JSON bundle, and computes
the plan of importing it elsewhere. `nyx_config.py` in that repository is the client:

```shell
export NYX_TOKEN=...                                   # admin token, kept out of the arguments
tools/nyx_config.py export --url https://dev -o config/bundle.json
tools/nyx_config.py plan   config/bundle.json --url https://prod
tools/nyx_config.py apply  config/bundle.json --url https://prod --yes
```

Import is a dry run unless `apply=1`, and `apply` needs `--yes`: it prints the plan
(create/update/unchanged/delete per document, with the changed fields) and exits with code 2
otherwise. `--prune` also deletes the documents the bundle does not contain.

Not portable, and refused by the validator: `nyx_user` (password hashes), `nyx_apikey`,
`nyx_config`, the report definitions, the lambdas, and every runtime index. Commit the bundle in
the infrastructure repository so the platform design becomes reviewable.

## Probes and metrics

`/api/v1/status` requires a token, so it cannot be a probe. Since `nyx_rest` 3.22.1:

| Endpoint | Answers |
| --- | --- |
| `GET /api/v1/healthz` | `{status, version, elasticVersion, checks{elasticsearch, redis, broker}, time}` — **200** when everything is up, **503** otherwise, `Cache-Control: no-store` |
| `GET /api/v1/metrics` | `nyx_up`, `nyx_info`, `nyx_elasticsearch_up`, `nyx_redis_up`, `nyx_broker_up`, `nyx_broker_life_sign_age_seconds`, `nyx_requests_total`, `nyx_errors_total`, `nyx_active_tokens` |

The broker is up while its life sign on `/topic/NYX_MODULE_INFO` is younger than 30 s (the API
publishes one every 5 s), which catches a worker that runs but has lost its connection to the
broker. Neither endpoint leaks a host, a credential or a user.

The counters are per gunicorn worker (three by default): a Prometheus scrape sees whichever worker
answers, so sum them (`sum by (instance)`) or scrape each worker explicitly.

## Behaviour worth knowing

- `generic_search` uses the Elasticsearch scroll API. `extra: {currentpage, pagesize}` paginates;
  the scroll is closed before returning.
- Text fields are automatically sorted on their `.keyword` sub-field, and `interval` in a
  `date_histogram` is rewritten to `fixed_interval` so the same body works on older clusters.
- `nyx_reporttask` and `nyx_reportdef` are filtered by owner/privilege before being returned.
- The API needs a writable `logs/` directory (rotating log, 30 days) and `OUTPUT_FOLDER`.
- The token in the query string is a known weakness: it ends up in nginx access logs, browser
  history and `Referer` headers. Prefer calling the API server-side when the token is long-lived.
