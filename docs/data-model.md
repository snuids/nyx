[Back](README.md)

# Data model

NYX keeps its own configuration in Elasticsearch, alongside the data it is used to query. There
is no migration system and no schema file: the platform reads documents, so a document *is* the
feature.

All documents are plain JSON in the `nyx_` namespace, addressed by `_id`. Before Elasticsearch 7
they carried `doc_type: doc`; the API branches on the cluster version, so new code must keep
using the version check.

## Indices

| Index | Holds |
| --- | --- |
| `nyx_app` | one document per screen (see below) — `_id` is the `rec_id` used in the URL |
| `nyx_user` | `login` (= `_id`), `password` (pbkdf2-sha256), `privileges[]`, `filters[]`, `language`, `firstname`, `phone`, `doublePhase`, `conexion_source`, `cn`, `mail` |
| `nyx_indice` | access rules per data index: `indicepattern`, `privileges[]`, `filtercolumn`, `privilegecolumn`, `notifications` |
| `nyx_privilege` | privilege catalogue, sent to `admin`/`user` at login so the console can offer them |
| `nyx_filter` | user filters catalogue, same delivery |
| `nyx_translation` | `area` (`menus`, …) + `item` + one field per language code (`en`, `fr`, `el`) |
| `nyx_config` | key/value documents, e.g. `nyx_css` whose `file` is served at `/api/v1/ui_css` |
| `nyx_datasource` | named query for Vega/forms/exports: `type` (`elasticsearch` or `postgres`), `query` with `@START@` / `@END@` placeholders |
| `nyx_lambda`, `nyx_lambdalog` | lambda definition (notebook, trigger) and its run history |
| `nyx_reportdef` | report definition (template, parameters, privileges) |
| `nyx_reporttask` | one document per generated report |
| `nyx_reportperiodic` | cron definition of a periodic report |
| `nyx_apikey` | API keys accepted by `/api/v1/lambdas/*` |
| `nyx_apicalls-YYYY.MM.DD` | audit trail written by the API on every authenticated call |
| `nyx_module_info-*`, `nyx_log-*`, `logstash-*` | operational indices |

Customer data lives in whatever indices the applications point at. It is only protected if a
`nyx_indice` pattern covers it — see *Access rules* below.

## `nyx_app`: one document per screen

```json
{
  "category": "Operations",
  "subcategory": "Field data",
  "title": "Deliveries",
  "order": 10,
  "icon": "truck",
  "apptags": [],
  "privileges": ["deliveries"],
  "type": "generic-table",
  "config": { }
}
```

- `category` and `title` become menu entries; `subcategory` becomes the group inside a category.
  Both are translated through `nyx_translation` (`area: "menus"`), the untranslated values are
  the keys.
- `order` sorts the category, then the apps.
- `apptags` empty means "console only"; a non-empty list targets the mobile application.
- `privileges` is any-of, and `admin` bypasses it.
- `type` selects the renderer:

| `type` | Renderer | Main `config` keys |
| --- | --- | --- |
| `generic-table` | Elasticsearch table | `index`, `pkey`, `headercolumns[]`, `queryfilters[]`, `timefield`, `queryBarChecked`, `graphicChecked`, `mapChecked`, `exportColumns`, `filtercolumn` |
| `pgsql-generic-table` | SQL table | `databaseType` (`postgres`/`sqlserver`), `database`, `sql` (may contain `${FILTER}`), `pkey`, `headercolumns[]`, `timefield`, `graphicChecked` |
| `kibana` | embedded dashboard | `kibanaId`, `kibanaTime`, `timeRefresh`, `timeRefreshValue`, `url`, `shorturl` |
| `grafana` | embedded dashboard | dashboard uid/url and time options |
| `form` | data entry | `fields[]`, target index or queue |
| `upload` | file upload | `queue` (defaults to the XLS importer) |
| `external` | iframe or link | `url` |
| `free-text` | static content | `freetext`, `controller: "FreeText"` |
| `vega` | Vega visualisation | specification, datasource, `controller: "Vega"` |
| `file-system` | file browser | `rootpath`, `regex` |
| `internal` | built-in console page | `controller` = component name (`Config`, `User`, `ProcessList`, `ReportList`, `ReportTask`, `SendMessage`, `LogViewer`, `Activity`, …) |

`config.controller` resolves against the Vue components directory, which is why an `internal`
screen can be added without touching the router.

A `kibana` screen is special: its URL is recomputed from the dashboard saved object at login, so
the stored `url` is a cache, not a setting.

## Access rules (`nyx_indice`)

An index is matched by `indicepattern` (a regular expression run against the index name, first
match wins). The matching document can do three things:

| Field | Effect |
| --- | --- |
| `privileges[]` | the user's privileges must intersect this list, otherwise the query is refused |
| `filtercolumn` | the user's `filters[]` are turned into `column:value` clauses and **and**-ed onto the query — this is the row-level restriction |
| `privilegecolumn` | after the query, rows whose column does not contain one of the user's privileges are dropped (used when the restriction lives in a document column instead of the query) |
| `notifications` | a broker destination that receives a message on every write to the index |

`admin` passes `privileges` but is still subject to nothing else; `user` receives every
privilege and filter document at login so that the console can offer them.

**An index with no matching `nyx_indice` document is open to every authenticated user.** When a
new data index is created, add its rule in the same change.

## Sessions

| Store | Key | Lifetime | Purpose |
| --- | --- | --- | --- |
| API memory | `state.tokens[token]` | 5 min (cache) | avoid a Redis round-trip per request |
| Redis | `nyx_tok_<token>` | 24 h | the token itself, shared by all API replicas |
| Redis | `nyx_<tool>_<token>` | 24 h | authorises `<tool>` in nginx (`kibana`, `kibananyx`, `grafananyx`, `nodered`, `cerebro`, `amqc`, `anaconda`, `logs`, `redis`) |
| Redis | `nyx_double_<login>` | 120 s | pending second-factor code |
| Redis | `nyx_kib_msearch<token>` | 60 s | query captured on `/kibananyx/` for the export |
| Cookie | `nyx_<tool>` | session | carries the token to nginx |

`/api/v1/cred/logout` deletes every key for the token and publishes `/topic/LOGOUT_EVENT` so the
other API instances drop their in-memory copy. A Redis flush therefore logs everybody out
immediately (the cookie still exists, but its Redis counterpart is gone).

## Retention

`nyx/curator/action_file.yml` decides how much history survives:

| Index prefix | Kept |
| --- | --- |
| `logstash-` | 20 days |
| `nyx_apicalls-` | 14 days |
| `nyx_module_info-` | 7 days |
| `nyx_log-` | 7 days |

The descriptions in that file were copy-pasted between rules (they mention "45 days" and the
wrong index); the `value` and `unit_count` entries are what Curator acts on.

## Where a setting lives

| You want to change | Go to |
| --- | --- |
| A screen, its columns, its filters | `nyx_app` |
| Who sees what | `nyx_user.privileges`, `nyx_app.privileges`, `nyx_indice` |
| Row-level restriction | `nyx_user.filters` + `nyx_indice.filtercolumn` |
| A menu label | `nyx_translation` |
| A report | `nyx_reportdef` (+ `nyx_reportperiodic` for the schedule) |
| A query used by a Vega graph or a form | `nyx_datasource` |
| The console stylesheet | `nyx_config/nyx_css` |
| Passwords, broker, ports | `.env` and `docker-compose.yml` |
