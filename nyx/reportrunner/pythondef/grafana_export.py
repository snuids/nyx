#!/usr/bin/env python3
"""
Export the data behind every queryable panel of a Grafana dashboard.

This script is run by nyx_reportrunner.py as:

    python3 grafana_export.py '<job-json>'

The NYX report definition sent by the UI must contain:

    reportType: "python"
    exec: "./reports/pythondef/grafana_export.py"
    output: ["xlsx"]
    parameters:
      - dashboardUid : Grafana dashboard UID
      - from         : epoch milliseconds or ISO-8601
      - to           : epoch milliseconds or ISO-8601
      - variables    : optional JSON object with variable overrides

The script queries Grafana's HTTP API with a service account token and writes
one Excel workbook with:

    * Metadata      : dashboard, time range, user and run information
    * Panels        : list of panels that were processed
    * one sheet per panel with the panel query result(s)
    * Warnings      : panels/queries that could not be exported

Grafana applies panel transformations, overrides and value mappings in the
browser, so the export contains the raw datasource query result, not the final
formatted table shown on the dashboard.

Dashboard variables are resolved from the saved dashboard values, the URL
overrides passed by the UI, or by querying Grafana when a variable has no saved
value (datasource, Prometheus label_values/query_result, Elasticsearch and
generic datasource variable queries).

Environment variables:
    GRAFANA_URL                 Base URL reachable from the reportrunner container
    GRAFANA_API_KEY             Grafana service account token (read-only/viewer)
    GRAFANA_VERIFY_SSL          true/false, default true
    GRAFANA_TIMEOUT             HTTP timeout in seconds, default 60
    GRAFANA_MAX_DATAPOINTS      Max points requested per panel, default 1000
    GRAFANA_MAX_ROWS_PER_SHEET  Max rows written per panel sheet, default 100000
"""

import json
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
import requests
from dateutil import parser as date_parser

GRAFANA_URL = os.environ.get("GRAFANA_URL", "").rstrip("/")
GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY", "")
GRAFANA_VERIFY_SSL = os.environ.get("GRAFANA_VERIFY_SSL", "true").lower() not in (
    "0",
    "false",
    "no",
    "off",
)
GRAFANA_TIMEOUT = int(os.environ.get("GRAFANA_TIMEOUT", "60"))
MAX_DATA_POINTS = int(os.environ.get("GRAFANA_MAX_DATAPOINTS", "1000"))
MAX_ROWS_PER_SHEET = int(os.environ.get("GRAFANA_MAX_ROWS_PER_SHEET", "100000"))

DATASOURCE_CACHE = {}
DATASOURCES_CACHE = None
DEFAULT_DATASOURCE = None

VARIABLE_PATTERN = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([A-Za-z0-9_]+))?\}"
    r"|\$([A-Za-z_][A-Za-z0-9_]*)"
    r"|\[\[([A-Za-z_][A-Za-z0-9_]*)(?::([A-Za-z0-9_]+))?\]\]"
)


class GrafanaError(Exception):
    """Raised when Grafana cannot satisfy an API request."""


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def grafana_request(method, path, **kwargs):
    if not GRAFANA_URL:
        raise GrafanaError("GRAFANA_URL is not configured in the report runner")
    if not GRAFANA_API_KEY:
        raise GrafanaError("GRAFANA_API_KEY is not configured in the report runner")

    headers = dict(kwargs.pop("headers", {}) or {})
    headers.setdefault("Authorization", "Bearer " + GRAFANA_API_KEY)
    headers.setdefault("Accept", "application/json")
    if "json" in kwargs:
        headers.setdefault("Content-Type", "application/json")

    try:
        response = requests.request(
            method,
            GRAFANA_URL + path,
            headers=headers,
            timeout=GRAFANA_TIMEOUT,
            verify=GRAFANA_VERIFY_SSL,
            **kwargs,
        )
    except requests.RequestException as exc:
        raise GrafanaError("Unable to reach Grafana at %s: %s" % (GRAFANA_URL, exc))

    if response.status_code >= 400:
        body = (response.text or "").strip().replace("\n", " ")[:1000]
        raise GrafanaError(
            "%s %s returned HTTP %s: %s"
            % (method, path, response.status_code, body)
        )

    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        raise GrafanaError("%s %s did not return JSON" % (method, path))


# ---------------------------------------------------------------------------
# Job helpers
# ---------------------------------------------------------------------------
def load_report(job):
    report = job.get("report") or {}
    if isinstance(report, str):
        report = json.loads(report)
    return report


def parameter_map(report):
    result = {}
    for param in report.get("parameters") or []:
        name = param.get("name")
        if name:
            result[name] = param.get("value")
    return result


def parse_time_ms(value, default=None):
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return int(float(text))
    parsed = date_parser.parse(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def iso_utc(milliseconds):
    return datetime.fromtimestamp(milliseconds / 1000.0, tz=timezone.utc).isoformat()


def format_duration(milliseconds):
    seconds = max(1, int(milliseconds / 1000))
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm" % (seconds // 60)
    if seconds < 86400:
        return "%dh" % (seconds // 3600)
    return "%dd" % (seconds // 86400)


def parse_dashboard_time(value, now_ms):
    """Resolve the simple relative time formats used by Grafana dashboards."""
    if value is None or value == "":
        return now_ms
    text = str(value).strip()
    if text == "now":
        return now_ms

    match = re.fullmatch(r"now([+-])(\d+)([smhdwMy])", text)
    if match:
        sign = 1 if match.group(1) == "+" else -1
        amount = int(match.group(2))
        unit = match.group(3)
        seconds = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
            "w": 604800,
            "M": 2592000,
            "y": 31536000,
        }[unit]
        return now_ms + sign * amount * seconds * 1000

    try:
        parsed = date_parser.parse(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)
    except (ValueError, TypeError):
        return now_ms


def dashboard_time_range(dashboard):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    dashboard_time = dashboard.get("time") or {}
    from_ms = parse_dashboard_time(dashboard_time.get("from", "now-6h"), now_ms)
    to_ms = parse_dashboard_time(dashboard_time.get("to", "now"), now_ms)
    return from_ms, to_ms


# ---------------------------------------------------------------------------
# Dashboard variables
# ---------------------------------------------------------------------------
def is_empty_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple)):
        return len(value) == 0 or all(
            item is None or str(item).strip() == "" for item in value
        )
    return False


def is_all_value(value):
    return value == "$__all" or (
        isinstance(value, (list, tuple)) and "$__all" in value
    )


def all_value_for_variable(variable):
    all_value = variable.get("allValue")
    if all_value not in (None, ""):
        return all_value
    options = variable.get("options") or []
    values = [
        option.get("value")
        for option in options
        if option.get("value") not in (None, "", "$__all")
    ]
    if values:
        return values if variable.get("multi") else values[0]
    return "*"


def split_variable_args(text):
    parts = []
    current = []
    depth = 0
    quote = None
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue
        if char in "{[(":
            depth += 1
            current.append(char)
            continue
        if char in "}])":
            depth = max(0, depth - 1)
            current.append(char)
            continue
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    parts.append("".join(current).strip())
    return [part for part in parts if part]


def prometheus_variable_value(query_text, datasource, variables, builtins):
    text = interpolate_text(query_text or "", variables, builtins, set()).strip()
    if not text:
        return None

    match = re.fullmatch(r"label_values\((.*)\)", text, re.S)
    if match:
        args = split_variable_args(match.group(1))
        if len(args) == 1:
            metric, label = None, args[0]
        elif len(args) == 2:
            metric, label = args
        else:
            return None
        path = (
            "/api/datasources/uid/%s/resources/api/v1/label/%s/values"
            % (quote(str(datasource.get("uid")), safe=""), quote(label, safe=""))
        )
        params = {}
        if metric:
            params["match[]"] = metric
        data = grafana_request("GET", path, params=params)
        values = data.get("data") if isinstance(data, dict) else None
        if isinstance(values, list) and values:
            return values[0]
        return None

    match = re.fullmatch(r"query_result\((.*)\)", text, re.S)
    if match:
        expression = interpolate_text(
            match.group(1), variables, builtins, set()
        ).strip()
        path = "/api/datasources/uid/%s/resources/api/v1/query" % quote(
            str(datasource.get("uid")), safe=""
        )
        data = grafana_request("GET", path, params={"query": expression})
        result = ((data or {}).get("data") or {}).get("result") or []
        for item in result:
            metric = item.get("metric") or {}
            for label, value in metric.items():
                if label != "__name__" and value not in (None, ""):
                    return value
            value = item.get("value")
            if isinstance(value, (list, tuple)) and len(value) > 1:
                return value[1]
        return None

    return None


def build_es_variable_query(query):
    if not isinstance(query, dict) or not query.get("field"):
        return None
    if query.get("find", "terms") != "terms":
        return None
    return {
        "refId": "var",
        "query": query.get("query") or "*",
        "queryType": "lucene",
        "metrics": [{"id": "1", "type": "count"}],
        "bucketAggs": [
            {
                "id": "2",
                "type": "terms",
                "field": query["field"],
                "settings": {
                    "min_doc_count": "1",
                    "order": "asc",
                    "orderBy": "_term",
                    "size": "10000",
                },
            }
        ],
        "timeField": query.get("timeField") or "@timestamp",
    }


def ds_query_variable_value(query, datasource, from_ms, to_ms, warnings):
    target = dict(query)
    target.pop("hide", None)
    target.setdefault("refId", "var")
    target["datasource"] = datasource
    target["intervalMs"] = (
        max(1, int((to_ms - from_ms) / MAX_DATA_POINTS)) if to_ms > from_ms else 1000
    )
    target["maxDataPoints"] = MAX_DATA_POINTS

    body = {"from": str(from_ms), "to": str(to_ms), "queries": [target]}
    data = grafana_request("POST", "/api/ds/query", json=body)
    results = (data or {}).get("results") or {}
    for ref_id, result in results.items():
        if result.get("error"):
            warnings.append(
                {
                    "panelId": "",
                    "panelTitle": "",
                    "refId": ref_id,
                    "error": "Variable query failed: %s" % result["error"],
                }
            )
            continue
        for frame in result.get("frames") or []:
            frame_data = frame_to_dataframe({"refId": ref_id}, frame)
            if frame_data is None or frame_data.empty:
                continue
            for column in frame_data.columns:
                if column in (
                    "refId",
                    "panelId",
                    "panelTitle",
                    "time",
                    "series",
                    "value",
                ):
                    continue
                values = [
                    item
                    for item in frame_data[column].tolist()
                    if item not in (None, "")
                ]
                if values:
                    return values[0]
            if "value" in frame_data.columns:
                values = [
                    item
                    for item in frame_data["value"].tolist()
                    if item not in (None, "")
                ]
                if values:
                    return values[0]
    return None


def query_variable_value(
    variable, variables, from_ms, to_ms, builtins, warnings
):
    datasource_spec = interpolate_datasource(
        variable.get("datasource"), variables, builtins, set()
    )
    try:
        datasource = resolve_datasource(datasource_spec)
    except GrafanaError as exc:
        warnings.append(
            {
                "panelId": "",
                "panelTitle": "",
                "refId": "",
                "error": "Variable %s datasource failed: %s"
                % (variable.get("name"), exc),
            }
        )
        return None
    if not datasource:
        return None

    query = variable.get("query")
    if isinstance(query, str):
        try:
            parsed = json.loads(query)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            query = parsed
        elif datasource.get("type") == "prometheus":
            return prometheus_variable_value(
                query, datasource, variables, builtins
            )

    if isinstance(query, dict):
        if "find" in query:
            query = build_es_variable_query(query)
        if isinstance(query, dict):
            if (
                "metrics" not in query
                and "bucketAggs" not in query
                and "rawSql" not in query
                and "expr" not in query
            ):
                inner = query.get("query")
                if isinstance(inner, str) and datasource.get("type") == "prometheus":
                    return prometheus_variable_value(
                        inner, datasource, variables, builtins
                    )
            if (
                "metrics" in query
                or "bucketAggs" in query
                or "rawSql" in query
                or "expr" in query
            ):
                return ds_query_variable_value(
                    query, datasource, from_ms, to_ms, warnings
                )

    definition = variable.get("definition")
    if isinstance(definition, str) and definition:
        if datasource.get("type") == "prometheus":
            return prometheus_variable_value(
                definition, datasource, variables, builtins
            )
        try:
            parsed = json.loads(definition)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            if "find" in parsed:
                parsed = build_es_variable_query(parsed)
            if isinstance(parsed, dict):
                return ds_query_variable_value(
                    parsed, datasource, from_ms, to_ms, warnings
                )

    return None


def resolve_datasource_variable(variable):
    query = variable.get("query")
    if isinstance(query, dict):
        query = query.get("query") or query.get("type")
    datasource_type = str(query or "").strip()
    if not datasource_type:
        return (get_default_datasource() or {}).get("uid")
    datasource = find_datasource_by_type(datasource_type)
    return datasource.get("uid") if datasource else None


def resolve_variable(variable, variables, from_ms, to_ms, builtins, warnings):
    current = variable.get("current") or {}
    value = current.get("value")
    if value is None and not is_empty_value(current.get("text")):
        if current.get("text") != "All":
            value = current.get("text")

    if is_all_value(value):
        return all_value_for_variable(variable)
    if not is_empty_value(value):
        return value

    variable_type = variable.get("type")
    if variable_type == "datasource":
        return resolve_datasource_variable(variable)

    if variable_type in ("custom", "interval", "textbox", "constant"):
        query = variable.get("query") or variable.get("definition")
        if isinstance(query, str):
            values = [part.strip() for part in query.split(",") if part.strip()]
            if values:
                return values[0]
        return None

    if variable_type == "query":
        options = variable.get("options") or []
        values = [
            option.get("value")
            for option in options
            if option.get("value") not in (None, "", "$__all")
        ]
        if values:
            return values if variable.get("multi") else values[0]
        return query_variable_value(
            variable, variables, from_ms, to_ms, builtins, warnings
        )

    return None


def resolve_variables(dashboard, overrides, from_ms, to_ms, builtins, warnings):
    if isinstance(overrides, str):
        try:
            overrides = json.loads(overrides)
        except ValueError:
            overrides = {}
    if not isinstance(overrides, dict):
        overrides = {}

    definitions = [
        variable
        for variable in (dashboard.get("templating") or {}).get("list") or []
        if variable.get("name")
    ]
    definition_by_name = {
        variable.get("name"): variable for variable in definitions
    }
    resolved = {}
    for name, value in overrides.items():
        variable = definition_by_name.get(name)
        if variable is not None and is_all_value(value):
            value = all_value_for_variable(variable)
        resolved[name] = value
    pending = [
        variable
        for variable in definitions
        if variable.get("name") not in resolved
    ]

    for _ in range(len(pending) + 1):
        if not pending:
            break
        progress = False
        for variable in list(pending):
            name = variable.get("name")
            value = resolve_variable(
                variable, resolved, from_ms, to_ms, builtins, warnings
            )
            if value is not None:
                resolved[name] = value
                pending.remove(variable)
                progress = True
        if not progress:
            break

    for variable in pending:
        warnings.append(
            {
                "panelId": "",
                "panelTitle": "",
                "refId": "",
                "error": "Unable to resolve dashboard variable: %s"
                % variable.get("name"),
            }
        )

    return resolved


def qsql(value):
    return "'" + str(value).replace("'", "''") + "'"


def format_variable(value, fmt=None):
    values = value if isinstance(value, (list, tuple)) else [value]
    values = ["" if item is None else str(item) for item in values]
    fmt = (fmt or "").lower()

    if fmt == "csv":
        return ",".join(values)
    if fmt == "json":
        return json.dumps(values if len(values) > 1 else values[0])
    if fmt == "pipe":
        return "|".join(values)
    if fmt in ("singlequote", "sqlstring"):
        return ",".join(qsql(item) for item in values)
    if fmt == "doublequote":
        return ",".join('"' + item.replace('"', '\\"') + '"' for item in values)
    if fmt == "regex":
        return "(" + "|".join(re.escape(item) for item in values) + ")"
    if fmt == "glob":
        return "{" + ",".join(values) + "}"
    if fmt == "lucene":
        return "(" + " OR ".join('"' + item.replace('"', '\\"') + '"' for item in values) + ")"
    if fmt == "percentencode":
        return ",".join(quote(item, safe="") for item in values)
    if fmt in ("raw", "text"):
        return ",".join(values)
    return ",".join(values)


def interpolate_text(text, variables, builtins, unresolved):
    def replace(match):
        if match.group(1) is not None:
            name, fmt = match.group(1), match.group(2)
        elif match.group(3) is not None:
            name, fmt = match.group(3), None
        elif match.group(4) is not None:
            name, fmt = match.group(4), match.group(5)
        else:
            return match.group(0)

        if name in builtins:
            return format_variable(builtins[name], fmt)
        if name in variables:
            return format_variable(variables[name], fmt)
        if not name.startswith("__"):
            unresolved.add(name)
        return match.group(0)

    return VARIABLE_PATTERN.sub(replace, text)


def interpolate_object(value, variables, builtins, unresolved, parent_key=None):
    if isinstance(value, str):
        return interpolate_text(value, variables, builtins, unresolved)
    if isinstance(value, list):
        return [
            interpolate_object(item, variables, builtins, unresolved, parent_key)
            for item in value
        ]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == "datasource":
                result[key] = item
            else:
                result[key] = interpolate_object(
                    item, variables, builtins, unresolved, key
                )
        return result
    return value


# ---------------------------------------------------------------------------
# Datasource and panel helpers
# ---------------------------------------------------------------------------
def all_datasources():
    global DATASOURCES_CACHE
    if DATASOURCES_CACHE is None:
        DATASOURCES_CACHE = grafana_request("GET", "/api/datasources") or []
    return DATASOURCES_CACHE


def get_default_datasource():
    global DEFAULT_DATASOURCE
    if DEFAULT_DATASOURCE is not None:
        return DEFAULT_DATASOURCE

    try:
        for datasource in all_datasources():
            if datasource.get("isDefault"):
                DEFAULT_DATASOURCE = {
                    "type": datasource.get("type", ""),
                    "uid": datasource.get("uid", ""),
                }
                return DEFAULT_DATASOURCE
    except GrafanaError:
        pass

    DEFAULT_DATASOURCE = {}
    return None


def find_datasource_by_type(datasource_type):
    candidates = []
    try:
        for datasource in all_datasources():
            if datasource.get("type") == datasource_type:
                candidates.append(datasource)
    except GrafanaError:
        return None

    for datasource in candidates:
        if datasource.get("isDefault"):
            return {
                "type": datasource.get("type", ""),
                "uid": datasource.get("uid", ""),
            }
    if candidates:
        datasource = candidates[0]
        return {
            "type": datasource.get("type", ""),
            "uid": datasource.get("uid", ""),
        }
    return None


def resolve_datasource(datasource):
    if isinstance(datasource, dict):
        uid = datasource.get("uid")
        if uid:
            datasource_type = datasource.get("type", "")
            if not datasource_type:
                try:
                    data = grafana_request(
                        "GET", "/api/datasources/uid/" + quote(str(uid), safe="")
                    )
                    datasource_type = data.get("type", "")
                except GrafanaError:
                    datasource_type = ""
            return {"type": datasource_type, "uid": uid}
        datasource = datasource.get("type") or datasource.get("name")

    if datasource in (None, ""):
        return get_default_datasource()
    if datasource in ("-- Mixed --", "-- Dashboard --", "-- Grafana --"):
        return None

    key = str(datasource)
    if key in DATASOURCE_CACHE:
        return DATASOURCE_CACHE[key]

    try:
        data = grafana_request(
            "GET", "/api/datasources/name/" + quote(key, safe="")
        )
        resolved = {"type": data.get("type", ""), "uid": data.get("uid", "")}
    except GrafanaError:
        if key.lower() == "default":
            resolved = get_default_datasource()
        else:
            raise

    DATASOURCE_CACHE[key] = resolved
    return resolved


def iter_panels(panels, seen=None):
    if seen is None:
        seen = set()
    for panel in panels or []:
        if not isinstance(panel, dict):
            continue
        panel_id = panel.get("id")
        if panel_id is not None and panel_id in seen:
            continue
        if panel_id is not None:
            seen.add(panel_id)

        if panel.get("type") == "row":
            yield from iter_panels(panel.get("panels"), seen)
            continue

        yield panel
        if panel.get("panels"):
            yield from iter_panels(panel.get("panels"), seen)


def expand_library_panel(panel):
    library = panel.get("libraryPanel") or {}
    uid = library.get("uid")
    if not uid:
        return panel

    try:
        data = grafana_request(
            "GET", "/api/library-elements/" + quote(str(uid), safe="")
        )
    except GrafanaError as exc:
        raise GrafanaError("Unable to load library panel %s: %s" % (uid, exc))

    result = data.get("result") or data
    model = result.get("model") if isinstance(result, dict) else None
    if isinstance(model, str):
        model = json.loads(model)
    if not isinstance(model, dict):
        return panel

    merged = dict(panel)
    merged.update(model)
    merged["libraryPanel"] = library
    return merged


def interpolate_datasource(datasource, variables, builtins, unresolved):
    if isinstance(datasource, str):
        return interpolate_text(datasource, variables, builtins, unresolved)
    if isinstance(datasource, dict):
        result = dict(datasource)
        for key in ("uid", "name", "type"):
            if isinstance(result.get(key), str):
                result[key] = interpolate_text(
                    result[key], variables, builtins, unresolved
                )
        return result
    return datasource


def build_queries(
    panel,
    variables,
    builtins,
    from_ms,
    to_ms,
    max_points,
    warnings,
    unresolved,
):
    queries = []
    targets = panel.get("targets") or []

    for index, target in enumerate(targets):
        if not isinstance(target, dict) or target.get("hide"):
            continue

        ref_id = str(target.get("refId") or chr(ord("A") + index))
        datasource_spec = target.get("datasource") or panel.get("datasource")
        datasource_spec = interpolate_datasource(
            datasource_spec, variables, builtins, unresolved
        )
        if datasource_spec in ("-- Mixed --", "-- Dashboard --") and not target.get(
            "datasource"
        ):
            warnings.append(
                {
                    "panelId": panel.get("id"),
                    "panelTitle": panel.get("title", ""),
                    "refId": ref_id,
                    "error": "Panel uses %s but the target has no datasource"
                    % datasource_spec,
                }
            )
        try:
            datasource = resolve_datasource(datasource_spec)
        except GrafanaError as exc:
            datasource = None
            warnings.append(
                {
                    "panelId": panel.get("id"),
                    "panelTitle": panel.get("title", ""),
                    "refId": ref_id,
                    "error": "Datasource resolution failed: %s" % exc,
                }
            )

        query = dict(target)
        query.pop("hide", None)
        query["refId"] = ref_id
        if datasource:
            query["datasource"] = datasource
        else:
            query.pop("datasource", None)

        interval_ms = (
            max(1, int((to_ms - from_ms) / max_points)) if to_ms > from_ms else 1000
        )
        query["intervalMs"] = interval_ms
        query["maxDataPoints"] = int(panel.get("maxDataPoints") or max_points)
        query = interpolate_object(query, variables, builtins, unresolved)
        query["refId"] = ref_id
        query["intervalMs"] = interval_ms
        query["maxDataPoints"] = int(panel.get("maxDataPoints") or max_points)
        queries.append(query)

    return queries


def query_panel(panel, queries, from_ms, to_ms):
    body = {"from": str(from_ms), "to": str(to_ms), "queries": queries}
    data = grafana_request("POST", "/api/ds/query", json=body)
    results = (data or {}).get("results") or {}

    frames = []
    for query in queries:
        ref_id = query.get("refId")
        result = results.get(ref_id) or {}
        error = result.get("error")
        if error:
            frames.append(
                {
                    "query": query,
                    "error": error,
                }
            )
            continue
        for frame in result.get("frames") or []:
            frames.append({"query": query, "frame": frame})
        for series in result.get("series") or []:
            frames.append({"query": query, "series": series})
    return frames


# ---------------------------------------------------------------------------
# DataFrame conversion
# ---------------------------------------------------------------------------
def to_datetime_series(values):
    series = pd.Series(values)
    sample = series.dropna()
    if not sample.empty and pd.api.types.is_numeric_dtype(sample):
        converted = pd.to_datetime(series, unit="ms", utc=True, errors="coerce")
    else:
        converted = pd.to_datetime(series, utc=True, errors="coerce")
    return converted.dt.tz_convert("UTC").dt.tz_localize(None)


def unique_columns(fields):
    columns = []
    used = {}
    for index, field in enumerate(fields):
        name = field.get("name") or "field%d" % index
        base = name
        if base in used:
            used[base] += 1
            name = "%s_%d" % (base, used[base])
        else:
            used[base] = 0

        labels = field.get("labels") or {}
        if labels:
            label_text = ", ".join(
                "%s=%s" % (key, labels[key]) for key in sorted(labels)
            )
            series_name = "%s (%s)" % (name, label_text) if name else label_text
        else:
            series_name = name
        columns.append(
            {
                "name": name,
                "series": series_name,
                "type": field.get("type"),
            }
        )
    return columns


def frame_to_dataframe(query, frame):
    if "series" in frame:
        series = frame.get("series") or {}
        points = series.get("points") or []
        if not points:
            return None
        data = pd.DataFrame(points, columns=["time", "value"])
        data["time"] = to_datetime_series(data["time"])
        data.insert(0, "refId", query.get("refId"))
        data.insert(1, "series", series.get("name") or query.get("refId"))
        return data[["refId", "series", "time", "value"]]

    schema = frame.get("schema") or {}
    fields = schema.get("fields") or []
    payload = frame.get("data") or {}
    values = payload.get("values")
    if values is None:
        rows = payload.get("data")
        if isinstance(rows, list):
            values = []
            for index in range(len(fields)):
                values.append([row[index] for row in rows])
        else:
            return None

    if not values:
        return None

    length = len(values[0]) if values else 0
    if length == 0:
        return None

    columns = unique_columns(fields)
    time_columns = [column for column in columns if column["type"] == "time"]
    non_time_columns = [column for column in columns if column["type"] != "time"]
    frame_name = schema.get("name") or ""
    is_table = not frame_name and (
        len(non_time_columns) > 1
        or any(column["type"] in ("string", "other") for column in non_time_columns)
    )

    if time_columns and not is_table:
        time_index = next(
            index
            for index, column in enumerate(columns)
            if column is time_columns[0]
        )
        time_values = to_datetime_series(values[time_index])
        parts = []
        for index, column in enumerate(columns):
            if column["type"] == "time":
                continue
            if len(values[index]) != length:
                continue
            series_name = column["series"]
            if frame_name:
                if len(non_time_columns) == 1:
                    series_name = frame_name
                else:
                    series_name = "%s %s" % (frame_name, column["series"])
            part = pd.DataFrame(
                {
                    "time": time_values,
                    "series": series_name,
                    "value": values[index],
                }
            )
            part.insert(0, "refId", query.get("refId"))
            parts.append(part)
        if parts:
            return pd.concat(parts, ignore_index=True, sort=False)
        return pd.DataFrame(
            {"refId": query.get("refId"), "time": time_values}
        )

    data = {}
    for index, column in enumerate(columns):
        if len(values[index]) != length:
            continue
        column_values = values[index]
        if column["type"] == "time":
            column_values = to_datetime_series(column_values)
        data[column["name"]] = column_values
    if not data:
        return None
    result = pd.DataFrame(data)
    result.insert(0, "refId", query.get("refId"))
    return result


def scalarize(value):
    if isinstance(value, (list, dict, tuple, set)):
        return json.dumps(value, default=str)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def sanitize_frame(frame):
    for column in frame.columns:
        if frame[column].dtype == object:
            frame[column] = frame[column].map(scalarize)
    return frame


def normalise_frame(df, panel):
    if df is None or df.empty:
        return None
    if "panelId" not in df.columns:
        df.insert(0, "panelId", panel.get("id"))
    if "panelTitle" not in df.columns:
        df.insert(1, "panelTitle", panel.get("title", ""))
    return sanitize_frame(df)


# ---------------------------------------------------------------------------
# Workbook helpers
# ---------------------------------------------------------------------------
def safe_sheet_name(name, used):
    name = re.sub(r"[\[\]:*?/\\]", " ", str(name or "Panel"))
    name = re.sub(r"\s+", " ", name).strip() or "Panel"
    name = name[:31]
    base = name
    counter = 2
    while name in used:
        suffix = " (%d)" % counter
        name = base[: 31 - len(suffix)] + suffix
        counter += 1
    used.add(name)
    return name


def column_width(df, column):
    width = len(str(column)) + 2
    try:
        sample = df[column].head(100).astype(str)
        if not sample.empty:
            width = max(width, int(sample.str.len().max()) + 2)
    except Exception:
        pass
    return min(max(width, 10), 60)


def write_workbook(path, metadata, panels_df, sheets, warnings_df):
    used = {"Metadata", "Panels", "Warnings"}
    with pd.ExcelWriter(
        path,
        engine="xlsxwriter",
        engine_kwargs={"options": {"remove_timezone": True}},
    ) as writer:
        metadata.to_excel(writer, sheet_name="Metadata", index=False)
        panels_df.to_excel(writer, sheet_name="Panels", index=False)

        written = [("Metadata", metadata), ("Panels", panels_df)]
        for base_name, frame in sheets:
            sheet_name = safe_sheet_name(base_name, used)
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
            written.append((sheet_name, frame))

        if warnings_df is not None and not warnings_df.empty:
            warnings_df.to_excel(writer, sheet_name="Warnings", index=False)
            written.append(("Warnings", warnings_df))

        for sheet_name, frame in written:
            worksheet = writer.sheets.get(sheet_name)
            if worksheet is None:
                continue
            worksheet.freeze_panes(1, 0)
            for index, column in enumerate(frame.columns):
                worksheet.set_column(index, index, column_width(frame, column))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        raise GrafanaError("Missing report job JSON argument")

    job = json.loads(sys.argv[1])
    report = load_report(job)
    params = parameter_map(report)

    dashboard_uid = params.get("dashboardUid") or params.get("dashboard_uid")
    if not dashboard_uid:
        raise GrafanaError("dashboardUid is missing from the report parameters")

    dashboard_response = grafana_request(
        "GET", "/api/dashboards/uid/" + quote(str(dashboard_uid), safe="")
    )
    dashboard = (dashboard_response or {}).get("dashboard") or {}
    dashboard_meta = (dashboard_response or {}).get("meta") or {}

    from_ms = parse_time_ms(params.get("from"))
    to_ms = parse_time_ms(params.get("to"))
    if from_ms is None or to_ms is None:
        dashboard_from, dashboard_to = dashboard_time_range(dashboard)
        if from_ms is None:
            from_ms = dashboard_from
        if to_ms is None:
            to_ms = dashboard_to
    if from_ms is None or to_ms is None:
        raise GrafanaError("from/to are missing from the report parameters")
    if from_ms > to_ms:
        from_ms, to_ms = to_ms, from_ms
    if from_ms == to_ms:
        to_ms = from_ms + 60000

    output_path = job.get("output")
    if not output_path:
        raise GrafanaError("The report runner did not provide an output path")
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    overrides = params.get("variables") or {}
    if isinstance(overrides, str):
        try:
            overrides = json.loads(overrides)
        except ValueError:
            overrides = {}

    interval_ms = (
        max(1, int((to_ms - from_ms) / MAX_DATA_POINTS)) if to_ms > from_ms else 1000
    )
    builtins = {
        "__from": from_ms,
        "__to": to_ms,
        "__from_ms": from_ms,
        "__to_ms": to_ms,
        "__interval_ms": interval_ms,
        "__interval": format_duration(interval_ms),
        "__rate_interval_ms": interval_ms,
        "__range_ms": to_ms - from_ms,
        "__range_s": int((to_ms - from_ms) / 1000),
        "__range": format_duration(to_ms - from_ms),
        "__dashboard": dashboard_uid,
    }

    warnings = []
    variables = resolve_variables(
        dashboard, overrides, from_ms, to_ms, builtins, warnings
    )

    panels = list(iter_panels(dashboard.get("panels") or []))
    panel_rows = []
    sheets = []
    unresolved_variables = set()
    total_rows = 0

    print(
        "Exporting Grafana dashboard %s (%s), %s -> %s"
        % (dashboard.get("title", ""), dashboard_uid, iso_utc(from_ms), iso_utc(to_ms))
    )

    for panel in panels:
        panel_id = panel.get("id")
        panel_title = panel.get("title", "")
        panel_type = panel.get("type", "")

        try:
            panel = expand_library_panel(panel)
        except GrafanaError as exc:
            warnings.append(
                {
                    "panelId": panel_id,
                    "panelTitle": panel_title,
                    "refId": "",
                    "error": str(exc),
                }
            )
            panel_rows.append(
                {
                    "panelId": panel_id,
                    "title": panel_title,
                    "type": panel_type,
                    "refIds": "",
                    "status": "Error",
                }
            )
            continue

        targets = panel.get("targets") or []
        if not targets:
            panel_rows.append(
                {
                    "panelId": panel_id,
                    "title": panel_title,
                    "type": panel_type,
                    "refIds": "",
                    "status": "Skipped (no queries)",
                }
            )
            continue

        if panel.get("repeat"):
            warnings.append(
                {
                    "panelId": panel_id,
                    "panelTitle": panel_title,
                    "refId": "",
                    "error": "Panel uses repeat '%s'; only the template instance was exported"
                    % panel.get("repeat"),
                }
            )

        queries = build_queries(
            panel,
            variables,
            builtins,
            from_ms,
            to_ms,
            MAX_DATA_POINTS,
            warnings,
            unresolved_variables,
        )
        if not queries:
            panel_rows.append(
                {
                    "panelId": panel_id,
                    "title": panel_title,
                    "type": panel_type,
                    "refIds": "",
                    "status": "Skipped (no queryable targets)",
                }
            )
            continue

        try:
            results = query_panel(panel, queries, from_ms, to_ms)
        except GrafanaError as exc:
            warnings.append(
                {
                    "panelId": panel_id,
                    "panelTitle": panel_title,
                    "refId": ",".join(str(q.get("refId")) for q in queries),
                    "error": str(exc),
                }
            )
            panel_rows.append(
                {
                    "panelId": panel_id,
                    "title": panel_title,
                    "type": panel_type,
                    "refIds": ",".join(str(q.get("refId")) for q in queries),
                    "status": "Error",
                }
            )
            continue

        panel_frames = []
        panel_errors = 0
        for result in results:
            if "error" in result:
                panel_errors += 1
                warnings.append(
                    {
                        "panelId": panel_id,
                        "panelTitle": panel_title,
                        "refId": result["query"].get("refId", ""),
                        "error": result["error"],
                    }
                )
                continue
            frame = frame_to_dataframe(
                result["query"], result.get("frame") or result
            )
            frame = normalise_frame(frame, panel)
            if frame is not None and not frame.empty:
                panel_frames.append(frame)

        ref_ids = ",".join(str(q.get("refId")) for q in queries)
        panel_frames = [
            frame.dropna(axis=1, how="all") for frame in panel_frames
        ]
        panel_frames = [frame for frame in panel_frames if not frame.empty]
        if panel_frames:
            frame = pd.concat(panel_frames, ignore_index=True, sort=False)
            if len(frame) > MAX_ROWS_PER_SHEET:
                warnings.append(
                    {
                        "panelId": panel_id,
                        "panelTitle": panel_title,
                        "refId": ref_ids,
                        "error": "Truncated to %d rows (export had %d)"
                        % (MAX_ROWS_PER_SHEET, len(frame)),
                    }
                )
                frame = frame.head(MAX_ROWS_PER_SHEET)
            sheet_base = "P%s %s" % (panel_id if panel_id is not None else "", panel_title)
            sheets.append((sheet_base, frame))
            total_rows += len(frame)
            status = "Exported"
            if panel_errors:
                status = "Exported with warnings"
        else:
            status = "No data" if not panel_errors else "Error"

        panel_rows.append(
            {
                "panelId": panel_id,
                "title": panel_title,
                "type": panel_type,
                "refIds": ref_ids,
                "status": status,
            }
        )

    # Variables that could not be resolved are reported once, after all panels.
    for name in sorted(unresolved_variables):
        warnings.append(
            {
                "panelId": "",
                "panelTitle": "",
                "refId": "",
                "error": "Unresolved dashboard variable: %s" % name,
            }
        )

    metadata = pd.DataFrame(
        [
            ["Dashboard", dashboard.get("title", "")],
            ["Dashboard UID", dashboard_uid],
            ["Folder", dashboard_meta.get("folderTitle", "")],
            ["Grafana URL", GRAFANA_URL],
            ["From (UTC)", iso_utc(from_ms)],
            ["To (UTC)", iso_utc(to_ms)],
            ["Report ID", job.get("id", "")],
            [
                "User",
                ((job.get("creds") or {}).get("user") or {}).get("login", ""),
            ],
            ["Generated (UTC)", datetime.now(timezone.utc).isoformat()],
            ["Panels", len(panels)],
            ["Exported rows", total_rows],
            [
                "Variables",
                json.dumps(variables, sort_keys=True, default=str),
            ],
        ],
        columns=["Property", "Value"],
    )
    panels_df = pd.DataFrame(
        panel_rows,
        columns=["panelId", "title", "type", "refIds", "status"],
    )
    warnings_df = pd.DataFrame(
        warnings,
        columns=["panelId", "panelTitle", "refId", "error"],
    )

    write_workbook(output_path + ".xlsx", metadata, panels_df, sheets, warnings_df)

    if total_rows == 0:
        raise GrafanaError(
            "No panel data was returned. See the Warnings sheet in %s.xlsx"
            % output_path
        )

    print(
        "Wrote %s.xlsx (%d panels, %d rows, %d warnings)"
        % (output_path, len(sheets), total_rows, len(warnings))
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - report runner needs a clear failure
        print("ERROR: %s" % exc, file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
