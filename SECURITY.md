# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Report them privately through
GitHub's [Security advisories](https://github.com/snuids/nyx/security/advisories/new) on this
repository, including:

- the affected file or service,
- steps to reproduce,
- the impact you believe it has.

You can expect an acknowledgement within a few days.

## Scope

This repository contains the **deployment and configuration** of the NYX platform: the Docker
Compose stack, nginx routing, service configuration and backup scripts. Vulnerabilities in the
application code belong to the matching component repository:

| Component | Repository |
| --- | --- |
| Web interface | [snuids/nyx_ui](https://github.com/snuids/nyx_ui) |
| REST API | [snuids/nyx_rest](https://github.com/snuids/nyx_rest) |
| Container definitions | [snuids/nyx_containers](https://github.com/snuids/nyx_containers) |
| Mobile application | [snuids/nyx_mob](https://github.com/snuids/nyx_mob) |
| WebSocket server | [snuids/nyx_ws_server](https://github.com/snuids/nyx_ws_server) |

Third-party images (Elasticsearch, Kibana, PostgreSQL, ActiveMQ, …) should be reported upstream.

## Credentials in this repository

This repository is a deployment template and **contains demo credentials**: database and broker
passwords, a TLS certificate and key, `.htpasswd` entries and passwords used by the backup
scripts. They are not secrets and must not be treated as such.

Before running NYX on any network you do not fully control:

1. Generate new values for every variable in `nyx/docker-compose/.env` (see `.env.example`).
2. Rotate the credentials referenced by `nyx/camelworkers/camelworker1/config.xml`,
   `nyx/elastalert/` and `nyx/scripts/*.sh`.
3. Replace `nyx/certs/nyx.crt` and `nyx/certs/nyx.key` with a certificate you issued.
4. Enable `auth_basic` in `nyx/nginx/default.conf` on the administration routes (Kibana,
   Node-RED, Cerebro, Log.io) and create the matching `.htpasswd` file.
5. Keep ports `5444`, `61613`–`61616` and `9200` closed to the internet; only `80`/`443` need
   to be reachable.
