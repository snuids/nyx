#!/usr/bin/env python3
"""Check the report flows before they are imported into Node-RED.

    python3 nodered/check_report_flows.py [nodered/report-flows.json]

Two things are worth catching before an import destroys a working host: a wire that points at a node
that is not in the file (Node-RED imports it silently and the flow stops halfway), and a credential
that ended up in a file meant for a public repository. The second check is the reason this file
exists at all — the deployed flows carry their secrets in `.flows_cred.json`, keyed by node id, and
an export that includes them would publish the broker and SMTP accounts.

Exit code 0 when the file is importable, 1 with the list of problems otherwise.
"""

import json
import re
import sys
from pathlib import Path

DEFAULT = Path(__file__).with_name("report-flows.json")
SECRET_KEYS = re.compile(r"password|passwd|secret|apikey|client_?secret|access_token", re.I)
SECRET_VALUES = re.compile(r"(?i)([?&;](?:token|password|passwd|secret|key)=)[^&;\s\"']+")


def check(path):
    problems = []
    nodes = json.loads(path.read_text())
    by_id = {node["id"]: node for node in nodes}

    # every node has an identity and a type
    for node in nodes:
        if not node.get("id") or not node.get("type"):
            problems.append("a node has no id or no type: %r" % (node,))

    # every wire points at a node of the file
    for node in nodes:
        for group in node.get("wires") or []:
            for target in group:
                if target not in by_id:
                    problems.append("%s (%s) wires to %s, which is not in the file"
                                    % (node["id"], node.get("type"), target))

    # every node that belongs to a flow belongs to a tab of the file
    tabs = {node["id"] for node in nodes if node.get("type") == "tab"}
    for node in nodes:
        z = node.get("z")
        if z and z not in tabs:
            problems.append("%s (%s) belongs to flow %s, which is not in the file"
                            % (node["id"], node.get("type"), z))

    # no credential, by key name or inside a value
    for node in nodes:
        for key, value in node.items():
            if SECRET_KEYS.search(key):
                problems.append("%s: field %r looks like a credential" % (node["id"], key))
            if isinstance(value, str) and SECRET_VALUES.search(value):
                problems.append("%s: field %r carries a secret in its value" % (node["id"], key))

    # what the report pipeline cannot work without
    topics = {node.get("topic") for node in nodes if node.get("type") == "stomp in"}
    for expected in ("/queue/NYX_REPORT_STEP1", "/queue/NYX_REPORT_STEP3", "/queue/NYX_REPORT_STEP4"):
        if expected not in topics:
            problems.append("no subscription to " + expected)
    if not any(node.get("type") == "e-mail" for node in nodes):
        problems.append("no e-mail node: STEP4 could not mail anything")
    if not any(node.get("type") == "stomp-server" for node in nodes):
        problems.append("no stomp-server configuration: the flow could not reach the broker")

    return nodes, problems


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT
    nodes, problems = check(path)
    print("%s: %d nodes, %d flows" % (path, len(nodes),
                                      len([n for n in nodes if n.get("type") == "tab"])))
    if problems:
        print("problems:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("importable, no credential found")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
