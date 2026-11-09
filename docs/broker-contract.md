[Back](README.md)

# Broker contract

ActiveMQ is the only coupling between services. A worker is a process that connects to the
broker with `amqstompclient`, subscribes to a queue or topic, publishes a life sign, and exits
with code 0 on `SIGTERM`.

Connection parameters come from the environment, identically for every component:

```shell
AMQC_URL=<broker host>     # "amqc" inside the Docker network
AMQC_PORT=61613            # STOMP
AMQC_LOGIN=admin
AMQC_PASSWORD=<AMQC_PASSWORD>
```

## Queues

Point-to-point: exactly one consumer, and the message is lost if no consumer is running. Names
include their prefix (`/queue/NAME`).

| Queue | Producer | Consumer | Payload |
| --- | --- | --- | --- |
| `/queue/NYX_REPORT_STEP1` | report scheduler | Node-RED | scheduled report job |
| `/queue/NYX_REPORT_STEP2` | Node-RED | report runner | job to render |
| `/queue/NYX_REPORT_STEP3` | report runner | Node-RED | render result, follow-up (mail) |
| `/queue/REST_LOAD_DATA` | API (export above 5000 rows) | rest_helper | `{index, data, doc_type, download, cui, is_rest_api, user, outputformat}` |
| `/queue/REST_LOAD_PGDATA` | API (SQL export above the inline threshold) | rest_helper | same shape for a SQL application |
| `/queue/REST_LOAD_KIBANA` | API (Kibana export above 3000 hits) | rest_helper | `{matchrequest, user, outputformat, is_rest_api}` |

The report chain is the one exception to "a queue has one consumer": Node-RED sits in the middle
because it owns the mail step and the file naming.

## Topics

Publish/subscribe: every subscriber that is connected receives a copy. A message published while
a subscriber reconnects is lost — these are notifications, not work items.

| Topic | Publisher | Subscriber | Purpose |
| --- | --- | --- | --- |
| `/topic/AUTH_SMS` | API | SMS worker | `{message, phone}` for the second authentication factor |
| `/topic/LOGOUT_EVENT` | API | every API instance | invalidate a token after logout |
| `/topic/NYX_MODULE_INFO` | every module | whatever collects life signs | module name, version, status |
| `/topic/NYX_LAMBDA_COMMAND` | API, Node-RED | lambda runner | `{runner, action: "execute", restapi, body, guid}` |
| `/topic/NYX_LAMBDA_RESTAPI` | lambda runner | API | `{guid, return}` — correlated by `guid`, 5 s timeout |
| `/topic/NYX_REPORTRUNNER_COMMAND` | Node-RED, console | report runner | add or replace a report definition |
| `/topic/ONFLEET_WEBHOOK` | API | delivery worker | raw Onfleet webhook payload |
| `/topic/TO_UI` | report runner (since 1.9.24) | `nyx_ws_server` | report finished/failed, addressed to a login |
| `/topic/NYX_LOG` | workers | log collector | free-text worker log line |

`TO_WEBSOCKETS` is the topic `nyx_ws_server` subscribes to (MQTT side), fed by whatever needs to
push something to a browser:

```json
{ "type": "message", "login": "<login>", "target": "<ws server name>", "data": { } }
```

`login` and `target` are both optional: with `target` the message goes to that WebSocket server,
without it the server resolves the login globally; a message with neither is logged and dropped.

## Conventions for a new worker

- Copy `nyx_containers/sources/nyx_skeleton.py` — it already connects to the broker, publishes
  the life sign and handles shutdown.
- Declare the contract in the module docstring: what it listens to, what it publishes, and a
  version history (`* 25 Oct 2026 1.9.24 **AMA** ...`). That docstring is the only changelog
  these containers have.
- Read configuration from the environment only, and never log a password or a token.
- Version the container from the commit message (`reportrunner:v1.9.24` style) — the build
  workflow keys on it.
- Remember that the compose file and the documentation table are the only places where a new
  queue becomes discoverable: update both.

## Life signs

Every module publishes to `/topic/NYX_MODULE_INFO` every few seconds with its name, its version
and a status. `monitordocker` collects container state separately; the two views answer different
questions (is the process alive vs is the container running).

```json
{ "name": "nyx_rest_42", "version": "3.21.18", "lifesign": "/topic/NYX_MODULE_INFO" }
```
