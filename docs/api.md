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

Almost every route takes a token as a **query parameter**: `?token=<uuid>`.

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
- `/api/v1/lambdas/*` is the only route that accepts `?apikey=` instead of a token.
- Every authenticated call is recorded in `nyx_apicalls-YYYY.MM.DD` with a **fingerprint** of the
  token, never the token itself.

Roles are checked with `@token_required(...roles)`: `admin` always passes, other users need one
of the listed privileges. Role checks do **not** protect data — that is the index-level rule
described in the [data model](data-model.md#access-rules-nyx_indice).

## Routes

All paths below are relative to `/api/v1/`.

| Method and path | Body / parameters | Returns |
| --- | --- | --- |
| `POST cred/login` | `{login, password, app?, doublecode?}` | `{version, error, cred:{token,user}, menus, all_priv, all_filters}` |
| `POST cred/login_google` | `{auth_code, app?}` | same shape |
| `GET cred/logout` | `?token=` | `{error:""}`, invalidates the token everywhere |
| `POST cred/changepassword` | `{old_password, new_password}` | `{error:""}` or `wrongpassword` |
| `POST cred/resetpassword` | `{login, new_password, queue?}` — roles `admin`, `useradmin` | `{error:""}` |
| `POST generic_search/<index>` | Elasticsearch query body | `{error, took, total, records, aggs}` |
| `POST pg_search/<appid>` | `{size, page, query, range}` | same shape, from the SQL application |
| `POST queryFilter/<rec_id>` | `{selected[], timerange?}` | the app's query filters, with their buckets |
| `GET datasource/<dsid>` | `?start=&end=&flat=` | `{error, records}`, or the bare array with `flat` |
| `GET generic/<index>/<id>` | `?doc_type=` | `{error, data}` |
| `POST generic/<index>/<id>` | the document | `{error:""}`; hashes `password` for `nyx_user` |
| `DELETE generic/<index>/<id>` | — | `{error:""}` |
| `GET/POST/DELETE pg_generic/<table>/<col>/<pk>` | `?app=<rec_id>`, body `{record:{...}}` | `{error, data, columns}` |
| `POST listdir` | `{rec_id, path}` | directory listing |
| `GET files` | `?rec_id=&path=&files=a,b` | the file, or a ZIP when several are requested |
| `POST files` | `{files:[{file_name, data}]}` (base64) | `{error:""}` |
| `GET streamfile` | `?file=/absolute/path` | last 32 kB of a file, text |
| `POST upload` | multipart `file`, `?queue=` | publishes to the broker, `{error:""}` |
| `GET reloadconfig` | — | recomputed menus for the current user |
| `GET config` | — | instance configuration (**no token required**) |
| `GET status` | — | `{status, version, name}` (**token required**) |
| `POST sendmessage` | `{destination, body, headers?}` | writes straight to the broker |
| `GET esmapping/<pattern>` | — | mappings of the matching indices |
| `POST lambdas/<runner>/<name>` | arbitrary JSON, `?apikey=` | the lambda return value |
| `GET grafana/dashboards` | — | dashboards visible to the configured Grafana token |
| `POST kibana_load` | `?token=&output=` | export of the dashboard query captured by nginx |
| `POST onfleet_webhook` | Onfleet payload | forwards to `/topic/ONFLEET_WEBHOOK` |
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

## Errors

Errors are returned as `{"error": "<code>"}` with HTTP 200. Check the `error` field, not the
status code.

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

## Behaviour worth knowing

- `generic_search` uses the Elasticsearch scroll API. `extra: {currentpage, pagesize}` paginates;
  the scroll is closed before returning.
- Text fields are automatically sorted on their `.keyword` sub-field, and `interval` in a
  `date_histogram` is rewritten to `fixed_interval` so the same body works on older clusters.
- `nyx_reporttask` and `nyx_reportdef` are filtered by owner/privilege before being returned.
- The API needs a writable `logs/` directory (rotating log, 30 days) and `OUTPUT_FOLDER`.
- The token in the query string is a known weakness: it ends up in nginx access logs, browser
  history and `Referer` headers. Prefer calling the API server-side when the token is long-lived.
