# AGENTS.md

## What this repo is

This is the **deployment/config repository** for the NYX platform, not the application source. The actual services (NYX_UI, NYX_REST, NYX_CONTAINERS, NYX_MOB, NYX_WS_SERVER) live in separate GitHub repos and are consumed here as **prebuilt Docker images**. Changing application behavior usually means bumping an image tag in `nyx/docker-compose/docker-compose.yml`, not editing code in this repo.

Component sources are checked out as sibling repos: the UI (`nyx_ui`) at `../nyx_ui` (`/Users/snuids/Documents/GitHub/nyx_ui`) and the REST API (`nyx_rest`) at `../nyx_rest` (`/Users/snuids/Documents/GitHub/nyx_rest`); each has its own `AGENTS.md`. The Docker images consumed here are built and tagged from those repos, not from this one.

All real deployment files are under `nyx/`. Root-level files are documentation only.

## Commands

There is no build, test, lint, typecheck, or CI in this repo. The only workflow is Docker Compose:

```shell
cd nyx/docker-compose
docker-compose up -d
```

- Uses legacy compose file `version: '2'` (not v3+).
- Verify health with `docker ps -a | grep -v Up` (should be empty) and `https://YOUR_DOMAIN/api/v1/status`.
- If nginx returns 404/503 on first boot, it started before the API: `docker restart nginx`.
- Config files are **bind-mounted** into containers, so after editing them you restart/recreate the container (`docker restart <name>`); there is no image rebuild step.

## Layout

- `nyx/docker-compose/docker-compose.yml` — the single source of truth for services, images, ports, env, and volume mounts.
- `nyx/nginx/default.conf` — reverse proxy / routing table for the whole platform; also adds Basic Auth and Redis-cookie-based auth for Kibana/Node-RED/Cerebro/logs. Adding a proxied service means adding both a compose service and an nginx `location`.
- `nyx/ELK/` — Elasticsearch node config; only `esnodebal` is active (`discovery.type: single-node`). `esnode1/2/3` are commented out in compose.
- `nyx/camelworkers/camelworker1/config.xml` — Apache Camel ETL routes (XML).
- `nyx/logstash/`, `nyx/curator/`, `nyx/elastalert/`, `nyx/kibana/` — pipeline/config files for those containers.
- `nyx/scripts/*.sh` — host-side backup scripts hardcoded to `/home/nyxinstall/nyx/...`; not runnable from this checkout.
- `folder_contents.md` is only a rough, partly stale map (e.g. it omits `scripts/` and lists a non-existent `reportrunner/pythondef`). Verify against disk.

## Gotchas

- The compose file uses **hardcoded absolute host paths** for several mounts, e.g. `/home/nyx/elkdata/esnodebal/data`, `/home/nyxinstall/nyx/postgresqldata/data`, and Kibana plugin dirs. It will not run on a machine without that exact layout or an edit.
- Most app data is bind-mounted to paths under the repo parent (`../logs`, `../generatedreports`, `../backup`, `../notebooks`), which `.gitignore` excludes. Some of these sibling directories do not exist in a fresh clone and must be created before `docker-compose up`.
- **Secrets are committed**: DB/broker passwords, TLS certs/keys, `.htpasswd`, and zip passwords in `nyx/scripts/`. Do not assume they are placeholders; avoid copying them into new files or logs.
- There are many commented-out alternate image lines and a mix of registries/owners (e.g. `lapin/nyx_ui` vs `snuids/*`). When changing a version, edit the active line and confirm the registry/owner.
- Most containers set `TZ=Europe/Paris`; keep that convention when adding services.

## Docs

- `running_locally.md` — local prerequisites and startup, but incomplete (truncates mid-step).
- `troubleshooting.md` — operational recovery: restarting stopped containers, checking logs, disk space (>75% breaks Elasticsearch).
- `README.md` — high-level architecture and links to the separate component repos.
