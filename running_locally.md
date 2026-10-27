[Back](README.md)

# Running Locally

This walks through a first start on a single machine. Expect roughly 8 GB of RAM to be
consumed: Elasticsearch, Kibana, PostgreSQL, ActiveMQ and the Python/Java workers all run at
once.

## Requirements

- A Linux host (Ubuntu 20.04+, Debian, RHEL) or macOS/Windows with Docker Desktop and at
  least 8 GB of memory allocated to the Docker VM.
- `git`
- Docker Engine and **Docker Compose v2** (the `docker compose` subcommand). The legacy
  `docker-compose` binary works too — it uses the same `docker-compose.yml` (`version: '2'`).

## Step 1 — clone and prepare the host directories

The compose file bind-mounts a number of directories that are not part of the git repository.
Create them once, from the `nyx/` folder (the one containing `docker-compose/`):

```shell
git clone https://github.com/snuids/nyx.git
cd nyx/nyx
mkdir -p logs generatedreports/rapi backup config_backup notebooks \
         node_red_data public_www reportrunnerold reportrunner/generated
```

## Step 2 — provide a TLS key

`nyx/certs/nyx.crt` is committed but `nyx.key` is **git-ignored**, so a fresh clone has no
private key and nginx will not start. From the `nyx/` folder, generate a self-signed pair (this
replaces the demo certificate; use a real one for anything beyond local testing):

```shell
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/nyx.key -out certs/nyx.crt \
  -subj "/CN=localhost"
```

## Step 3 — create the `.env` file

`docker-compose.yml` reads required variables from `.env`, and refuses to start if they are
not set:

```shell
cd docker-compose
cp .env.example .env
```

Edit `.env` and set at least:

- `PG_PASSWORD` — PostgreSQL password, used by `postgres`, `nyx_restapi`, `nodered` and
  `camelworker1`.
- `AMQC_PASSWORD` — ActiveMQ admin/STOMP password, used by the broker, the API and every worker.

The `GRAFANA_*` entries are optional; leave them empty unless you connect a Grafana instance.

## Step 4 — review the absolute host paths

Four volumes point at hardcoded server paths. Either create them:

```shell
sudo mkdir -p /home/nyx/elkdata/esnodebal/data
sudo mkdir -p /home/nyxinstall/nyx/postgresqldata/data
sudo mkdir -p /home/nyxinstall/nyx/kibana/kibana/elastalert-kibana-plugin
sudo mkdir -p /home/nyxinstall/nyx/kibana/kibana/TrafficLightVisKibana6
```

or, preferably, edit those four lines in `docker-compose.yml` to point somewhere under the
repository. Notebooks, logs and generated reports are already relative and need no change.

> **Known gap in a fresh clone:** the `elastalertrest` service bind-mounts
> `nyx/elastalert/rules/`, `alerts.py` and `elastalert.py`, which are not tracked in git.
> Provide them from the ElastAlert project, or comment the `elastalertrest` service out in
> `docker-compose.yml` for a first local run.

## Step 5 — start

```shell
docker compose up -d
```

On Linux, if `esnodebal` keeps restarting, check its log and raise the memory map limit:

```shell
sudo sysctl -w vm.max_map_count=262144
docker logs -f esnodebal
```

## Step 6 — are all containers up?

```shell
docker ps -a | grep -v Up
```

This should print nothing. If a container is down, start it again with `docker compose up -d`
(it is safe to repeat) and inspect it with `docker logs --tail 100 <container>`.

## Step 7 — open the platform

Use a browser to open:

> https://localhost/

The certificate in `nyx/certs/` is a demo one, so the browser will warn — accept the exception.

Check the API health endpoint:

> https://localhost/api/v1/status

It should return a JSON status page. If you get a 404 or 503, nginx started before the API was
ready:

```shell
docker restart nginx
```

then reload the two URLs above.

## Step 8 — log in and explore

The web interface is at `/`, its documentation and API explorer at `/swaggerui/`. Administration
panels are proxied on the same host:

| URL | What it is |
| --- | --- |
| `/kibana/` | Kibana |
| `/kibananyx/` | Kibana with the NYX dashboards |
| `/cerebro/` | Elasticsearch cluster admin |
| `/amqc/` | ActiveMQ monitoring console |
| `/ipython/` | Jupyter notebooks |
| `/nodered/` | Node-RED flow editor |
| `/logs/` | Log.io live logs |
| `/generatedreports/` | Files produced by the report runner |

Some of these routes are protected by Basic Auth (`.htpasswd` inside the nginx container);
see `nyx/nginx/default.conf` and [Security](README.md#security) before exposing the host.

## Next steps

- Change `server_name` in `nyx/nginx/default.conf` and the TLS pair in `nyx/certs/` for
  anything other than local use.
- Read [Configuration](README.md#configuration) for the full list of settings.
- If something fails: [Troubleshooting](troubleshooting.md).
