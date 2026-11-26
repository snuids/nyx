# TLS material for the reverse proxy

This directory holds the certificate and key OpenResty serves (`/etc/certs/` inside the
container, mounted from here). **Nothing in it is tracked by git** — a distribution must not ship
certificate material, and the files a checkout generates are specific to that host.

## Fresh clone

Nothing to do. The `certgen` service in `docker compose` generates a self-signed pair
(`nyx.crt`, `nyx.key`) the first time the stack starts, and leaves an existing pair alone:

```shell
NYX_HOST=nyx.example.com docker compose up -d    # CN + SAN for that name, plus localhost
```

`NYX_HOST` defaults to `localhost`. Without it, the certificate is valid for `localhost` and
`127.0.0.1` only, which is enough for a local instance and never for a real one.

## A real instance

Drop your certificate and key here under the same names, then restart the proxy:

```shell
cp /path/to/fullchain.pem nyx/certs/nyx.crt
cp /path/to/privkey.pem  nyx/certs/nyx.key
chmod 600 nyx/certs/nyx.key
docker compose restart nginx
```

`certgen` sees a pair and does nothing, so an operator's certificate is never overwritten. If the
file names must differ, change `ssl_certificate` / `ssl_certificate_key` in
`../nginx/default.conf` (two `server` blocks).

## What is ignored

`*.key` everywhere (`.gitignore`), plus `*.crt` and `*.csr` in this directory. A `.p12`, `.pem`
or `.jks` dropped here is only safe because it matches no pattern — check `git status` before
committing anything you put in this folder.
