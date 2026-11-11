[Back](../README.md)

# Documentation

The platform is five repositories: this one ships the running stack, the others ship the
services. These documents describe the running stack and the contracts between it and the
services, so that an operator can run it and a developer can extend it without reading the
compose file and the nginx configuration line by line.

| Document | Read it when |
| --- | --- |
| [Architecture](architecture.md) | you need the service map, the routing table, the volumes, or the request/data flows |
| [Broker contract](broker-contract.md) | you write or debug a worker: queues, topics, payloads, life signs |
| [Data model](data-model.md) | you create a screen, a privilege rule or a translation, or you need to know where a setting lives |
| [Report generation](report-flow.md) | you debug a report that never arrives, or you render one somewhere new: console → API → Node-RED → runner → Jasper → mail |
| [Node-RED flows](../nodered/README.md) | you need to restore, review or re-export the flows behind the report pipeline |
| [REST API](api.md) | you call the API from a script, or you debug a 403/`NO_TOKEN` on a route |
| [Operations](operations.md) | you deploy, upgrade, back up or troubleshoot an installation |
| [Automation](automation.md) | you wonder who bumps the image tags after a release |
| [Running locally](../running_locally.md) | first start on a laptop or a fresh host |
| [Troubleshooting](../troubleshooting.md) | something is down and you want the checklist |
| [Folder contents](../folder_contents.md) | you look for a file and want to know what it is for |

## The five repositories

| Repository | What it is | How it lands in the stack |
| --- | --- | --- |
| [`nyx`](https://github.com/snuids/nyx) (this one) | Compose stack, nginx routing, service configuration, backup scripts | Run directly |
| [`nyx_rest`](https://github.com/snuids/nyx_rest) | REST API (Flask-RESTX, gunicorn) | Image `snuids/nyx_rest` |
| [`nyx_ui`](https://github.com/snuids/nyx_ui) | Web console (Vue 2 + Element UI) | Image `snuids/nyx_ui` |
| [`nyx_containers`](https://github.com/snuids/nyx_containers) | Workers: report runner, report scheduler, XLS importer, lambda runner, format converter, Docker monitor | Images `snuids/nyx-reportrunner`, `snuids/nyx_lambda`, … |
| [`nyx_ws_server`](https://github.com/snuids/nyx_ws_server) | Broker → WebSocket fan-out per user | Not part of this stack yet (see [Architecture](architecture.md#known-gaps)) |
| [`nyx_jasper_creator`](https://github.com/snuids/nyx_jasper_creator) | Java JasperReports service (queue + REST) | External service, called by the report runner |
| [`nyx_mob`](https://github.com/snuids/nyx_mob) | Mobile forms (Quasar), served at `/mobile/` — **deprecated and archived** | Image `snuids/nyx_mobile:v1.0.2` frozen, not deployed |

## Documenting conventions

- Anything that is **data** (screens, privileges, filters, translations, report definitions)
  belongs to the [data model](data-model.md) — it is not in this repository.
- Anything that is **wiring** (a port, a route, a queue, a volume) belongs to
  [architecture](architecture.md) or [broker contract](broker-contract.md).
- Behaviour of an endpoint is defined by `nyx_rest/sources/routes/*.py`, not by these pages:
  when the two disagree, the code wins and the page is a bug.
