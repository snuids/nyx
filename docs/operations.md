[Back](README.md)

# Operations

## First start

[running_locally.md](../running_locally.md) has the full walkthrough. The short version, from the
`nyx/` folder (the one containing `docker-compose/`):

```shell
mkdir -p logs generatedreports/rapi backup config_backup notebooks \
         node_red_data public_www reportrunnerold reportrunner/generated
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/nyx.key -out certs/nyx.crt -subj "/CN=localhost"
cd docker-compose
cp .env.example .env     # set PG_PASSWORD and AMQC_PASSWORD at least
docker compose up -d
```

## Is it healthy?

```shell
docker ps -a | grep -v Up        # must print nothing
curl -sk https://HOST/api/v1/config
```

`/api/v1/config` needs no token: it answers with the version, the welcome message and the
Elasticsearch major version. `/api/v1/status` exists too but requires `?token=`, so it is not a
liveness probe — use `/api/v1/config` for that.

```json
{"error":"","status":"ok","version":"3.21.18","welcome":"...","icon":"...","elastic_version":7}
```

If nginx answers 404 or 503 right after a start, it won the race against the API:

```shell
docker restart nginx
```

## Upgrading

Application images are built by each component repository and pinned by tag in
`docker-compose.yml`. The stack is upgraded by changing those tags — never by editing code in
this repository.

1. **Release in the component repository.** The build workflow extracts the version from the
   **commit message**: a commit that does not contain `vX.Y.Z` fails the workflow and publishes
   nothing. A release commit therefore carries the version in three places:
   - `package.json` / module `VERSION` bumped,
   - a new entry in that repository's changelog (`versions.md`, or the module docstring),
   - a commit message starting with the version (`v3.30.0 Add ...`).
2. **Confirm the image exists** before touching the compose file:
   `https://hub.docker.com/v2/repositories/snuids/<image>/tags/<tag>` must answer 200.
3. **Bump the tag** in `nyx/docker-compose/docker-compose.yml`, then:

```shell
cd nyx/docker-compose
docker compose pull
docker compose up -d
curl -sk https://HOST/api/v1/config      # check the reported version
```

4. **Read the release notes of the API** before jumping several minor versions: behaviour changes
   (token required on `/api/v1/upload`, allowed roots for `/api/v1/streamfile`, HTTP status codes)
   are documented in the version history at the top of `nyx_rest/sources/nyx_rest_api_plus.py`.

Kibana, Elasticsearch and PostgreSQL are pinned platform versions. Upgrading them is a separate
operation with a data migration, not a tag change.

## Backup and restore

There are two kinds of state, and both need saving.

| What | How |
| --- | --- |
| PostgreSQL | `pg_dump` inside the `postgres` container, or a dump of `/home/nyxinstall/nyx/postgresqldata` with the container stopped |
| Elasticsearch | a snapshot repository (preferred) or a copy of `/home/nyx/elkdata/esnodebal/data` with the container stopped |
| Platform configuration | the `nyx_*` indices — they are part of the Elasticsearch snapshot |
| Generated reports, notebooks | `nyx/generatedreports`, `nyx/notebooks`, `nyx/reportrunner` |
| Node-RED flows | `nyx/node_red_data` |

`nyx/scripts/backuplambda.sh` and `nyx/scripts/backupreport.sh` are host-side helpers hardcoded to
`/home/nyxinstall/nyx/...`; they zip a directory and require `BACKUP_ZIP_PASSWORD` in the
environment. Adapt the paths before using them on another machine.

A restore is only useful if it has been tried: restore the PostgreSQL dump into a scratch
container and confirm the API answers with the expected menus before declaring the backup valid.

## Disk and Elasticsearch

Elasticsearch refuses to allocate shards once the disk passes 75 % full, and the platform starts
failing in ways that look unrelated (reports, imports, logins).

```shell
df -h
du -sh nyx/* | sort -h | tail
```

`curator` prunes the operational indices (see [retention](data-model.md#retention)); the
`generatedreports` folder and the Docker volumes are the usual culprits. `ncdu` makes the search
quicker.

On Linux, if `esnodebal` restarts in a loop:

```shell
sudo sysctl -w vm.max_map_count=262144
docker logs --tail 100 esnodebal
```

## Troubleshooting matrix

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| Login page spins forever | the API is not answering `/api/v1/config` | `docker logs nyx_restapi`, then `docker restart nginx` |
| Login works, a tool says 403/406 | the cookie has no matching Redis key | the user's privileges, then `nyx_<tool>_<token>` in Redis |
| `UNKNOWN_TOKEN` on some requests | a replica cannot reach Redis | `REDIS_IP`, `docker logs redis` |
| A table is empty although the data is there | the index rule refuses or filters the rows | `nyx_indice` for that pattern, and the API log line `Must be filtered:` |
| An export never arrives | it went to the mail path | `docker logs nyx_rest_helper`, `SMTP_*` settings |
| Kibana export empty | the query was not captured by nginx | `nyx_kib_msearch<token>` in Redis, `/kibananyx/` route |
| Reports never appear | the chain is blocked in Node-RED | `docker logs nyx_reportrunner_1`, `nyx_reportlog`, `/generatedreports/` |
| A report fails with `KeyError: 'JASPER_API'` | the report runner needs the Jasper service | set `JASPER_API` (and `DATA_SOURCE_API`) or stop using JadeP reports |
| Containers restart after a reboot | they are `restart: always`, but the host paths are missing | `docker ps -a`, the four absolute paths in the compose file |
| Everything slow after a while | Elasticsearch disk watermark or heap | `df -h`, `docker logs esnodebal`, `ELK/esnodebal/conf/jvm.options` |

## Security checklist before exposing the host

- Replace every password in `.env`, and the ones referenced by `nyx/camelworkers`,
  `nyx/elastalert` and `nyx/scripts`.
- Replace `nyx/certs/nyx.crt` and generate `nyx.key`; never reuse the demo pair.
- Fill `.htpasswd` inside the nginx container and keep `auth_basic` on the administrative routes
  (Node-RED, Kibana, Cerebro, Elasticsearch, Log.io, Jupyter).
- Do not publish ports 9200, 5444, 61613-61616 or 5801 (Kibana bypasses the cookie check).
- Set `server_name` in `nyx/nginx/default.conf` and keep the certificate valid.
- Point `OUTPUT_URL` at the real host: exported files are served from there.
- Review `nyx_indice`: an index with no rule is readable by every authenticated user.
