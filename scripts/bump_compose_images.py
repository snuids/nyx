#!/usr/bin/env python3
"""
Compare the images pinned in `docker-compose.yml` with what Docker Hub publishes, and bump them.

This exists because a release in a component repository does not touch the deployment repository:
without this, the stack silently runs an older API for months (it happened with nyx_rest, left at
v2.11.0 while the repository was at v3.21.x).

    scripts/bump_compose_images.py                      # report only
    scripts/bump_compose_images.py --apply              # rewrite docker-compose.yml
    scripts/bump_compose_images.py --json               # machine readable
    scripts/bump_compose_images.py --image snuids/nyx_rest

Only the images built by the NYX workflows are considered (`BUMPED`): the infrastructure images
(postgres, elasticsearch, kibana, redis, openresty, …) are pinned on purpose and a "newer tag" is
not an upgrade, it is a platform change. A tag is only a candidate when it looks like `vX.Y.Z`:
`latest`, `buildcache` and `sha-…` are ignored.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

COMPOSE = Path(__file__).resolve().parents[1] / "nyx" / "docker-compose" / "docker-compose.yml"
HUB = "https://hub.docker.com/v2/repositories"

# Images published by the component workflows, with the version scheme they follow.
BUMPED = {
    "snuids/nyx_ui",
    "snuids/nyx_rest",
    "snuids/nyx-reportrunner",
    "snuids/nyx_lambda",
    "snuids/nyx_reportscheduler",
    "snuids/nyx_rest_helper",
    "snuids/nyx_mobile",
    "snuids/nyx_xlsimport",
    "snuids/monitordocker",
}

SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
IMAGE_LINE = re.compile(r"^(?P<indent>\s*)image:\s*(?P<image>[^\s#]+)(?P<rest>.*)$")


def parse_semver(tag):
    match = SEMVER.match(tag)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def split_image(reference):
    """`snuids/nyx_rest:v3.22.1` → (`snuids/nyx_rest`, `v3.22.1`)."""
    if ":" not in reference:
        return reference, None
    repository, _, tag = reference.rpartition(":")
    return repository, tag


def published_tags(repository, size=100):
    url = f"{HUB}/{repository}/tags?page_size={size}&ordering=last_updated"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return []
        raise
    return [tag["name"] for tag in payload.get("results", [])]


def latest_version(repository):
    """Highest `vX.Y.Z` tag published for the repository, or None."""
    candidates = [(parse_semver(tag), tag) for tag in published_tags(repository)]
    candidates = [(version, tag) for version, tag in candidates if version]
    if not candidates:
        return None
    return max(candidates)[1]


def inspect(compose_path=COMPOSE, only=None):
    """Return one record per bumped image found in the compose file."""
    lines = compose_path.read_text(encoding="utf-8").splitlines()
    records = []
    for position, line in enumerate(lines):
        match = IMAGE_LINE.match(line)
        if not match:
            continue
        repository, current = split_image(match.group("image"))
        if repository not in BUMPED:
            continue
        if only and repository != only:
            continue
        latest = latest_version(repository)
        current_version = parse_semver(current or "")
        latest_version_tuple = parse_semver(latest or "")
        action = "keep"
        if latest is None or latest_version_tuple is None:
            action = "no-tag"
        elif current_version is None:
            action = "unpinned"
        elif latest_version_tuple > current_version:
            action = "bump"
        records.append(
            {
                "line": position,
                "indent": match.group("indent"),
                "rest": match.group("rest"),
                "repository": repository,
                "current": current,
                "latest": latest,
                "action": action,
            }
        )
    return records


def apply(records, compose_path=COMPOSE):
    """Rewrite the image tags of the records whose action is `bump`."""
    changed = [record for record in records if record["action"] == "bump"]
    if not changed:
        return 0
    lines = compose_path.read_text(encoding="utf-8").splitlines()
    for record in changed:
        lines[record["line"]] = (
            f"{record['indent']}image: {record['repository']}:{record['latest']}{record['rest']}"
        )
    compose_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(changed)


def render(records):
    width = max((len(record["repository"]) for record in records), default=10)
    out = [f"{'image':<{width}}  {'current':<12} {'latest':<12} action"]
    for record in records:
        out.append(
            f"{record['repository']:<{width}}  {str(record['current']):<12} "
            f"{str(record['latest']):<12} {record['action']}"
        )
    pending = [r for r in records if r["action"] == "bump"]
    out.append("")
    out.append(f"{len(pending)} image(s) to bump")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bump the images pinned in docker-compose.yml.")
    parser.add_argument("--apply", action="store_true", help="rewrite the compose file")
    parser.add_argument("--json", action="store_true", help="machine readable output")
    parser.add_argument("--image", help="restrict to one repository, e.g. snuids/nyx_rest")
    parser.add_argument("--compose", default=str(COMPOSE), help="compose file to inspect")
    args = parser.parse_args(argv)

    records = inspect(Path(args.compose), only=args.image)
    if args.json:
        print(json.dumps({"records": records, "pending": [r for r in records if r["action"] == "bump"]}, indent=2))
    else:
        print(render(records))

    if args.apply:
        count = apply(records, Path(args.compose))
        print(f"\n{count} image(s) rewritten in {args.compose}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
