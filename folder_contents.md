[Back](README.md)

# NYX Folder Contents

Annotated layout of this repository. Everything the platform runs is under `nyx/`; root-level
files are documentation. `docker-compose.yml` sits in `nyx/docker-compose/`, so relative volume
paths (`../logs`, `../certs`, …) resolve **inside `nyx/`**, not at the repository root.

```text
.
├── README.md               # overview, quick start, configuration, security
├── SECURITY.md             # how to report a vulnerability
├── AGENTS.md               # working notes for coding agents
├── docs/                   # architecture, broker contract, data model, API, operations
├── medias/                 # screenshots and the overview animation used by the README
├── running_locally.md      # first start, step by step
├── troubleshooting.md      # recovery checklist
├── folder_contents.md      # this file
└── nyx/                    # everything the platform runs (detailed below)
```

```text
nyx/
├── ELK/
│   ├── esnodebal/conf/          # ACTIVE Elasticsearch 7.2 node
│   │   ├── elasticsearch.yml
│   │   └── jvm.options
│   ├── esnodebal/data/          # leftover node state, committed before the ignore rule
│   ├── esnode1/                 # reserved: multi-node layout, commented out in compose
│   ├── esnode2/
│   └── esnode3/
├── camelworkers/
│   └── camelworker1/
│       ├── config.xml          # Apache Camel ETL routes
│       └── log4j.xml
├── certs/
│   └── nyx.crt                 # TLS certificate used by nginx
│                               # nyx.key is git-ignored — generate it locally
├── curator/
│   ├── action_file.yml         # what to delete (old indices)
│   └── curator_config.yml      # how to reach Elasticsearch
├── docker-compose/
│   ├── docker-compose.yml      # single source of truth: services, images, ports, volumes
│   └── .env.example            # copy to .env and fill in (passwords, Grafana access)
├── elastalert/
│   ├── config.json             # ElastAlert server settings
│   └── config.yaml             # ElastAlert rules/settings
│                               # rules/, alerts.py, elastalert.py are not tracked in git
├── kibana/
│   ├── kibanaclassic.yml       # stock Kibana, reachable at /kibana/
│   └── kibananyx.yml           # Kibana with the NYX dashboards, at /kibananyx/
├── logstash/
│   └── config/
│       ├── logstash.conf       # pipeline definition (mounted into the container)
│       ├── logstash.conf.old   # previous pipeline, kept for reference
│       ├── logstash.yml
│       ├── jvm.options
│       ├── pipelines.yml
│       ├── log4j2.properties
│       ├── startup.options
│       └── patterns/camelworker  # grok pattern used by the pipeline
├── nginx/
│   ├── default.conf            # reverse proxy / routing table for the whole platform
│   ├── server.crt              # local development certificate
│   └── server.csr
│                               # logs, *.pid and .htpasswd are git-ignored at runtime
├── reportrunner/
│   ├── jasper/                 # Jasper report definitions (.jrxml) and compiled (.jasper)
│   │   ├── myjasper.jrxml
│   │   ├── myjasper.jasper
│   │   └── firstjasper.jrxml
│   ├── pythondef/
│   │   └── grafana_export.py   # Grafana data export used by the report runner
│   └── generated/              # report output (created at runtime, git-ignored)
├── scripts/                    # host-side backup scripts, hardcoded to /home/nyxinstall/nyx
│   ├── backuplambda.sh
│   └── backupreport.sh
└── sqlopendistro/              # Open Distro SQL plugin jars, mounted into esnodebal
```

## Where each part is described

| Folder | Documentation |
| --- | --- |
| `docs/` | The documentation set. Start at [docs/README.md](docs/README.md). |
| `ELK/` | Elasticsearch node configuration. Only `esnodebal` is started by default; `esnode1`–`3` exist for a multi-node deployment and are commented out in the compose file. |
| `camelworkers/` | One folder per Camel worker. Each worker is an XML route definition; add more workers by copying the folder and declaring a new service in the compose file. |
| `certs/` | TLS material mounted at `/etc/certs/` in the nginx container. |
| `curator/` | Index lifecycle cleanup, run as a scheduled container. |
| `docker-compose/` | The stack itself. Images are prebuilt and tagged in the component repositories. |
| `elastalert/` | Alerting on log anomalies; rules live in `rules/` (not tracked — see above). |
| `kibana/` | Two Kibana configurations: a stock instance and one preloaded with the NYX dashboards. |
| `logstash/` | Log shipping pipeline. |
| `nginx/` | Routes every service on one host: `/`, `/api/`, `/kibana/`, `/nodered/`, `/cerebro/`, `/amqc/`, `/ipython/`, `/logs/`, `/generatedreports/`. Also holds the Basic Auth and cache rules. |
| `reportrunner/` | Report templates and the Python definition driving scheduled generation. |
| `scripts/` | Backup routines meant to run on the host, not in a container. They assume the `/home/nyxinstall/nyx/...` layout. |
| `sqlopendistro/` | SQL query support for Elasticsearch (Open Distro plugin jars). |

## Runtime data (not in git)

These are bind-mounted from the host, are listed in `.gitignore` or simply absent from a fresh
clone, and must exist before the first start:

```text
nyx/logs/                       # logs of every service (also harvested by Log.io and Logstash)
nyx/generatedreports/           # files produced by the report runner
nyx/generatedreports/rapi/      # API-generated files
nyx/backup/                     # working directory for the backup scripts / Camel worker
nyx/config_backup/              # Camel worker configuration backups
nyx/notebooks/                  # user notebooks, including notebooks/Lambdas
nyx/node_red_data/              # Node-RED flows
nyx/public_www/                 # static files served by nginx
nyx/reportrunnerold/            # archived reports
nyx/reportrunner/generated/     # compiled report output
```

Four volumes additionally use hardcoded absolute paths (`/home/nyx/elkdata/esnodebal/data`,
`/home/nyxinstall/nyx/postgresqldata/data`, and two Kibana plugin directories). See
[Configuration](README.md#configuration).

## Two leftovers worth knowing about

- `nyx/ELK/esnodebal/data/` contains a few Elasticsearch node-state files (`nodes/0/node.lock`,
  `_state/node-*.st`) committed before `**/data/nodes/**` was added to `.gitignore`. They are
  inert; `git rm -r --cached nyx/ELK/esnodebal/data` would remove them from the index without
  touching a running installation (the live data lives under `/home/nyx/elkdata`).
- `nyx/logstash/config/logstash.conf.old` is the previous pipeline definition, kept for
  reference; only `logstash.conf` is mounted into the container.
