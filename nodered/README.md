[Back](../README.md)

# The report flows, as source

`report-flows.json` is the Node-RED part of the report pipeline, taken out of the running instance and
put under version control. It holds two flows — **REPORTS (Server)** and **REPORTS (Mail)** — with the
broker configuration they use, in a form the editor accepts as is.

What the flows do, step by step, belongs to [the report flow](../docs/report-flow.md). This page is
about the file: what it contains, what it deliberately does not, and how to put it back on a host.

## What is in it

| flow | nodes | its job |
| --- | --- | --- |
| REPORTS (Server) | `STEP1`, `STEP3` subscriptions, the two functions that shape the document, the HTTP request to Elasticsearch, the `TO STEP 2` / `TO STEP 4` publishers | creates the task document in `nyx_reporttask-<YYYY.MM>` before rendering, updates it after |
| REPORTS (Mail) | `STEP4` subscription, two functions, a `split`, the SMTP node | mails the finished report, one message per recipient |

Twenty-two nodes in total, including the two flow tabs and one `stomp-server` configuration
(`amqc:61613`).

## What is *not* in it

**Credentials.** Node-RED keeps them in a separate file, `.flows_cred.json`, keyed by node id: the
broker account on the `stomp-server` node, and the SMTP login on the e-mail node. An export that
carried them would publish both to a public repository, so they are absent here and have to be typed
once after an import, in the editor.

**The rest of the platform's flows.** The volume holds other things (spreadsheet upload, lambda
commands, demonstrations). Only what the report pipeline needs is here, which is also why the file is
readable.

## What the target instance must have

The file uses ten node types; nine come from installed packages, and `tab` is Node-RED's own flow
container:

| type | package |
| --- | --- |
| `stomp in`, `stomp out`, `stomp-server` | `node-red-node-stomp` |
| `e-mail` | `node-red-node-email` |
| `function`, `http request`, `json`, `split`, `debug` | Node-RED core |

Importing on an instance without the first two creates unknown-type nodes that do nothing until the
palette is installed (menu → **Manage palette**). Checked against the palette of the production
instance on 11/11/2026 (Node-RED 4.0.9).

## Putting it back on a host

Through the editor (`/nodered/`, credentials of the Node-RED instance):

1. menu → **Import**, and paste the content of `report-flows.json`, or drop the file on the canvas;
2. the two tabs appear with their node ids intact, so the `z` references and the wires keep working;
3. open the `stomp-server` configuration node and type the broker account, then the e-mail node and its
   SMTP account;
4. **Deploy**, then send one job and watch `docker logs nyx_reportrunner_1`.

Replacing the whole volume is the other route — copy `flows.json` and `.flows_cred.json` into
`/data/` — but it overwrites every flow of the host, including the ones this repository does not
track. Prefer the import.

## Before committing a change

```bash
python3 nodered/check_report_flows.py
```

It loads the file and refuses it when a wire points at a node that is not there (Node-RED imports
that silently and the flow stops halfway), when a node belongs to a flow tab that is missing, when a
field looks like a credential, or when one of the three subscriptions, the SMTP node or the broker
configuration has disappeared. Exit code 0 means importable.

## Keeping it true

The file is a snapshot of a *deployed* flow: the instance in the volume stays the reference for what is
running, and this copy is what a new host, a review or a rollback starts from. When a flow changes on
the instance, export it again, run the checker, and commit the difference — otherwise the next reader
will restore an older pipeline and wonder why the mail has no `$URL$`.
