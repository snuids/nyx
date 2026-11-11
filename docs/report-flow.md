[Back](README.md)

# Report generation, end to end

What happens between a click on **Generate** in the console and a file in the user's mailbox or in
the generated-reports folder. Six actors take part and each hands the job to the next through the
broker; no component calls the next one directly except where noted, which is why a report that
never arrives can be stuck in five different places.

This page describes the **pipeline**, not the report definitions themselves (those are data: see
[data model](data-model.md)) and not the queue names in isolation (see [broker contract](broker-contract.md)).

## The actors

| Actor | Image | Its part of the job |
| --- | --- | --- |
| Console | `snuids/nyx_ui` | Collects the parameters, posts one job to the broker through the API |
| API | `snuids/nyx_rest` | Checks the destination, publishes the job (`/sendmessage`) |
| Node-RED | `snuids/nodered` | Owns the *state* of the job: creates the task document, then updates it, then mails |
| Report runner | `snuids/nyx-reportrunner` | Renders the file, writes the downloads, publishes the outcome |
| Jasper creator | `snuids/nyx_jasper_creator` | Renders `jasper` / `jasper_jdbc` templates over HTTP (external service) |
| WS gateway | `snuids/nyx_ws_server` | Delivers the "report ready" notification to the user's browser |

The scheduler (`snuids/nyx_reportscheduler`) does not render anything: it pushes the same job as the
console, on the same queue, at the time the periodic definition says.

## The sequence

```
console            API              broker            Node-RED        report runner      jasper creator
   |                |                  |                 |                  |                  |
   |-- parameters ->|                  |                 |                  |                  |
   |  POST /sendmessage -destination-> |                 |                  |                  |
   |                |-- publish STEP1 ->|                  |                  |                  |
   |                |                  |- STEP1 --------->|                  |                  |
   |                |                  |                 |-- create task --->|                  |
   |                |                  |                 |   nyx_reporttask-YYYY.MM             |
   |                |                  |                 |- STEP2 ---------->|                  |
   |                |                  |                 |                  |-- render ------->|
   |                |                  |                 |                  |<- file ----------|
   |                |                  |                 |                  |- STEP3 --------->|
   |                |                  |                 |<- update task ---|                  |
   |                |                  |                 |   (status, downloads)               |
   |                |                  |                 |- STEP4 ----------                   |
   |                |                  |                 |-- e-mail (one per recipient)        |
   |                |                  |<- TO_UI --------|                  |                  |
   |<-- websocket --|  (ws_server)     |                 |                  |                  |
```

## Step by step

### 1. The console posts the job

`ReportList.vue` shows the report definitions; the generate button opens `ReportGenerator.vue`, which
builds the dialog from the definition's `parameters` (a `text`, an `interval`, a `date`, an
`escombo`…) and, on **Generate**, posts to the API (`ReportGenerator.vue:406`):

```json
POST /api/v1/sendmessage?token=<token>
{ "destination": "/queue/NYX_REPORT_STEP1",
  "body": "{\"id\":\"id_<rand>_<rand>\",\"creds\":{…},\"report\":{…},\"privileges\":[…],
           \"task\":{\"mailingList\":[],\"mailingListCc\":[],\"mailingListCci\":[],
                    \"mailSubject\":\"\",\"mailTemplate\":\"\"}}" }
```

Two details matter when debugging this step. The `creds` object is the **whole session of the
user**, token included: the rest of the pipeline renders and mails *as that user*. And the `report`
here is the definition as the console had it, not a reference — a definition edited between the click
and the run does not change the job in flight.

### 2. The API checks the destination and publishes

`/sendmessage` (`nyx_rest/sources/routes/misc.py:201`) refuses any destination outside
`PLATFORM_DESTINATIONS` unless the caller holds `admin` (`nyx_rest/sources/lib/amq_destinations.py`),
then publishes the body on the broker. See [known gaps](#known-gaps) — `/queue/NYX_REPORT_STEP1` is
not in that list.

### 3. Node-RED creates the task document

The `STEP1` subscription (`stomp in`, topic `/queue/NYX_REPORT_STEP1`) runs a function node that:

- sets `treatment = {status: "Waiting", creation: <now>}` and `@timestamp = <now>`;
- turns `report` back into a string (`JSON.stringify`), because the runner expects it as text;
- sets the target `http://elasticsearch:9200/nyx_reporttask-<YYYY.MM>/_doc/<id>` — **one index per
  month**, the document id is the job id;

then POSTs it to Elasticsearch and forwards the same message to `/queue/NYX_REPORT_STEP2`.

This is where a job acquires a visible trace: `nyx_reporttask-*` is what the console's **Tasks** tab
reads, and a job that never appears there never reached Node-RED.

> The flow itself is not tracked in git (`node_red_data` is a volume). What is written above is what
> the deployed flow does, read from `/data/flows.json` in the `nodered` container on 11/11/2026, and
> from the messages the runner logs — see [operations](operations.md#the-node-red-flows).

### 4. The report runner renders the file

`nyx_reportrunner` subscribes to `/queue/NYX_REPORT_STEP2` (`nyx_reportrunner.py:82`) and, per
`report.reportType`:

| `reportType` | what runs |
| --- | --- |
| `python` | the definition's `exec` (a script under `./reports/pythondef/`), which writes the outputs |
| `notebook` | the notebook builder (`nyx_buildreport.py`), which writes the requested `output` formats |
| `jasper` | a POST to `JASPER_API` (`http://nyx-jasper-creator:8080/api/v1/generate-report`) with the template, the parameters and a `jsonUrl` pointing at `/api/v1/datasource/<datasource>?flat=true&start=…&end=…` |
| `jasper_jdbc` | the same POST, with the JDBC URL of the datasource instead of the JSON one |

Then, for every requested output: `generatePDF` converts the other formats with
`./shellscripts/converttopdsf.sh`, the file is checked to exist (a missing output becomes
`status = "Error"` with the path in the message), and the runner builds the download list:

```json
"downloads": [{"extension": "xlsx",
               "url": "https://<host>/generatedreports/<id>.xlsx"}]
```

The files land in the runner's `generated/` volume, served by nginx at `/generatedreports/`. The
python and notebook builders also write one document per run into `nyx_reportlog` (`nyx_buildreport.py:41`),
keyed by the job id: that is the "logs" button of the Tasks tab.

Finally the runner posts the whole message, now carrying `treatment.start/end/duration/status/error`
and `downloads`, to `/queue/NYX_REPORT_STEP3`, and notifies the requesting user on `/topic/TO_UI`
(`notifyReportFinished`, `nyx_reportrunner.py:346`). Jobs whose `creds.user` is the scheduler are not
notified — nobody is waiting in a browser.

### 5. Node-RED updates the task and mails

The `STEP3` subscription posts the finished document to the same `nyx_reporttask-<YYYY.MM>/_doc/<id>`
(the POST replaces the waiting document: status, error and downloads now come from the runner), then
forwards to `/queue/NYX_REPORT_STEP4`.

`STEP4` is the mail: the payload is kept aside, `task.mailingList` is split into one message per
address, and each message becomes an e-mail whose subject is `task.mailSubject` (else `NYX report`),
whose body is `task.mailTemplate` with `$URL$` replaced by the first download URL, sent through the
SMTP server configured on the e-mail node (`ssl0.ovh.net:465` on this installation) — a send failure
shows up in `docker logs nodered`, not in the task document, which is already `Finished`. A job that produced no file has an empty download list, so `$URL$` becomes an empty
string and the failure notification still goes out.

> The attachments are **not** carried by the broker: the mail body links to `/generatedreports/<id>.<ext>`.
> A report is therefore only downloadable while the runner's `generated/` volume holds the file.

### 6. The console learns about it

Two independent paths, and it is worth knowing both:

- the **websocket**: the runner's `/topic/TO_UI` message reaches `nyx_ws_server` (MQTT topic `TO_UI`,
  `IN_TOPIC`), which pushes it to that user's socket; the console shows the global notification with
  the report title and the download links;
- the **local bus**: the console itself emits `reportgenerated` on `$globalbus` right after the API
  accepted the job (`ReportGenerator.vue:446`), and `GenericComponent` switches to the `ReportTask`
  tab when it hears it. This one fires on *submission*, not on completion — the Tasks tab may still
  show `Waiting` when it appears.

## Periodic reports

`nyx_reportscheduler` reads the definitions of type `periodic`, computes their next run with `cron`,
and at that time builds **the same job** and publishes it directly on `/queue/NYX_REPORT_STEP1`
(`nyx_reportscheduler.py:184`) — so everything above applies unchanged, from the task document to the
mail.

Differences worth knowing:

- `creds` are synthetic: a `reportscheduler` account holding `admin`, which is why the runner's
  notification is skipped for those jobs;
- `task.mailSubject` is resolved **in the task** before publishing (`${DATE:…}` placeholders), because
  the mail is built by Node-RED from the task, not from the top-level message;
- a task that comes due while the scheduler was down is rescheduled from *now*, not from its stored
  next run: after a long stop it fires once, not once per missed period.

## What the user sees when it fails

| Symptom | Where the job stopped |
| --- | --- |
| "Failed" notification, job absent from Tasks | the API refused it (`403 destination not allowed`), the broker is down, or Node-RED could not write the task document (its POST to Elasticsearch is what creates it, and the job only carries on if that POST succeeds) |
| job in Tasks with `Waiting` for ever | Node-RED created the document but nothing consumed STEP2 — report runner down |
| `Error` with a path in the message | the renderer produced nothing: missing output file, crashed script, unreachable datasource |
| `Finished`, no e-mail | STEP4/SMTP: the mail body and its `$URL$` come from `task.mailSubject`/`mailTemplate` |
| `Finished`, link returns 404 | the file is gone from the runner's `generated/` volume (cleanup or a new container) |

## Where to look

```bash
docker logs -f nyx_reportrunner_1        # one block per job: message, type, JASPER_API call, status
docker logs nodered | tail -50           # flow errors, ES POST failures
docker exec nodered cat /data/flows.json # the flow itself (STEP1 … STEP4, e-mail)
```

- task documents: index `nyx_reporttask-<YYYY.MM>`, id = job id (`id_<n>_<n>`);
- run logs (python/notebook): index `nyx_reportlog`, same id;
- files: the runner's `generated/` volume, served at `/generatedreports/<id>.<ext>`;
- environment the runner depends on: `JASPER_API`, `REPORT_URL` (the public base of
  `/generatedreports/`), `AMQC_URL`.

## Known gaps

Verified on 11/11/2026; listed here so the next reader does not discover them the hard way.

1. **`/queue/NYX_REPORT_STEP1` is not in the API's allow-list.** `PLATFORM_DESTINATIONS` lists the
   load queues and the two command topics, not the report queues. `/sendmessage` therefore answers
   `403 destination not allowed` to anyone who is not `admin`, and the generate button of the console
   is not gated by a privilege: a `reporteditor` user sees the dialog, gets the job refused, and the
   console only logs "Report list error…" — no visible error. Fixing it by adding the queue to the
   allow-list would hand every account the ability to forge a job carrying any `creds` it likes (the
   consumer trusts them), so the right fix is a dedicated route that builds the STEP1 message from the
   authenticated session.
2. **The runner logs the Jasper request with the user's token in clear**
   (`nyx_reportrunner.py:250`, `Posting to Jasper Generator API: {…"token": …}`), and the `jsonUrl` it
   builds carries the token too. That contradicts the redaction the rest of the worker applies
   (`redact_message`); the same masking should be applied to that body.
3. **The Node-RED flows are not in git.** The two report flows and the mail flow exist only in the
   `node_red_data` volume of a running host; this page is their only written description.
