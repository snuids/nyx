[Back](README.md)

# Automation

Two things in this repository are automated, both because they were done by hand often enough to
go wrong: the image bump after a release, and the documentation drift it exposes.

## Bumping the application images

`.github/workflows/bump-compose-images.yml` compares the tags pinned in
`nyx/docker-compose/docker-compose.yml` with what Docker Hub publishes, and opens a pull request
when an image is behind.

| | |
| --- | --- |
| Runs | every day at 06:17 UTC, on demand (`workflow_dispatch`), and on a `repository_dispatch` of type `image-published` |
| Script | `scripts/bump_compose_images.py` (`--apply` rewrites the file, `--json` for machines) |
| Branch | `chore/compose-image-bump`, force-pushed on each run so only one pull request is ever open |
| Checks | the compose file is parsed again before the commit (PyYAML), and the service count is asserted |

```shell
# what is behind, without touching anything
python3 scripts/bump_compose_images.py

# the same, on one image only
python3 scripts/bump_compose_images.py --image snuids/nyx_rest
```

Only the images built by the NYX workflows are considered: `nyx_ui`, `nyx_rest`,
`nyx-reportrunner`, `nyx_lambda`, `nyx_reportscheduler`, `nyx_rest_helper`, `nyx_mobile`,
`nyx_xlsimport`, `monitordocker`. The infrastructure images (PostgreSQL, Elasticsearch, Kibana,
Redis, OpenResty, ActiveMQ, Node-RED, Camel) are never touched: their version is a platform
decision, and a newer tag is not an upgrade.

A candidate tag must look like `vX.Y.Z` — `latest`, `buildcache` and `sha-…` are ignored, which is
what keeps this safe against the cache tags the build workflows push.

### Instant bump after a release

The daily run is enough in practice. If a component workflow should trigger the check immediately,
it can dispatch the event — this needs a token with `contents: write` on this repository, stored as
a secret in the component repository:

```shell
curl -X POST https://api.github.com/repos/snuids/nyx/dispatches \
  -H "Authorization: Bearer $PAT" \
  -d '{"event_type":"image-published","client_payload":{"image":"snuids/nyx_rest"}}'
```

`client_payload.image` restricts the comparison to that repository; without it, all of them are
checked.

## What it does not do

- It does not merge. The pull request lists each bump with its current and new tag, and merging it
  is the operator's decision: a release can require a configuration change (a new environment
  variable, a migration) that the tag alone does not reveal.
- It does not touch the platform version of Elasticsearch, Kibana or PostgreSQL.
- It does not verify that the new image starts. That is the test plan of the pull request:
  `docker compose pull && docker compose up -d`, then `/api/v1/config` and `/api/v1/healthz`.
