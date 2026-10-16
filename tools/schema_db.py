#!/usr/bin/env python3
"""JSON Schemas in schema/ are the source of truth for the public data model.

The build copies them to /api/v1/schema/, draws the relation diagram, and renders /db/
in every site language. tests/test_schema.py fails when a data file does not match.

Private stores (reader tips, newsletter addresses) are named here only. Their columns
and contents are not part of the public schema.
"""
import datetime as dt
import html
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(ROOT, "schema")
REPO = "https://github.com/nordic-crypto-org/nordic-crypto"
SKIP_KEYS = {"description", "title", "examples", "default", "$schema", "$id", "$comment",
             "x-nordic", "$defs"}


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def schema_files():
    names = sorted(n for n in os.listdir(SCHEMA_DIR) if n.endswith(".schema.json"))
    return [os.path.join(SCHEMA_DIR, n) for n in names]


def load_schemas():
    out = []
    for path in schema_files():
        doc = load_json(path)
        meta = doc.get("x-nordic") or {}
        if not meta.get("id"):
            raise SystemExit(f"schema: {path} has no x-nordic.id")
        out.append((os.path.basename(path), doc))
    out.sort(key=lambda pair: ((pair[1].get("x-nordic") or {}).get("order", 1000), pair[0]))
    return out


def _typeof(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


class SchemaError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors[:8]))


class Validator:
    """Draft 2020-12 subset: type, enum, const, properties, required, additionalProperties,
    items, anyOf, oneOf, allOf, $ref, numeric and string bounds."""

    def __init__(self, root):
        self.root = root
        self.errors = []

    def check(self, instance):
        self.errors = []
        self._check(instance, self.root, "$")
        return self.errors

    def _fail(self, path, message):
        self.errors.append(f"{path}: {message}")

    def _resolve(self, ref):
        if not isinstance(ref, str) or not ref.startswith("#/"):
            self._fail("$", f"unsupported $ref {ref}")
            return {}
        node = self.root
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                self._fail("$", f"dangling $ref {ref}")
                return {}
        return node

    def _check(self, instance, schema, path):
        if not isinstance(schema, dict):
            self._fail(path, "schema is not an object")
            return
        if "$ref" in schema:
            self._check(instance, self._resolve(schema["$ref"]), path)
            return
        if "allOf" in schema:
            for sub in schema["allOf"]:
                self._check(instance, sub, path)
        if "anyOf" in schema:
            before = len(self.errors)
            matched = False
            for sub in schema["anyOf"]:
                probe = Validator(self.root)
                if not probe.check_against(instance, sub, path):
                    matched = True
                    break
            if not matched:
                self._fail(path, "no anyOf branch matched")
            else:
                del self.errors[before:]
        if "oneOf" in schema:
            hits = 0
            for sub in schema["oneOf"]:
                probe = Validator(self.root)
                if not probe.check_against(instance, sub, path):
                    hits += 1
            if hits != 1:
                self._fail(path, f"{hits} oneOf branches matched")
        if "enum" in schema and instance not in schema["enum"]:
            shown = ", ".join(json.dumps(x, ensure_ascii=False) for x in schema["enum"][:12])
            self._fail(path, f"{json.dumps(instance, ensure_ascii=False)[:80]} is not one of {shown}")
        if "const" in schema and instance != schema["const"]:
            self._fail(path, "const mismatch")
        if "type" in schema:
            allowed = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            got = _typeof(instance)
            ok = got in allowed or (got == "integer" and "number" in allowed)
            if not ok:
                self._fail(path, f"expected {' or '.join(allowed)}, got {got}")
                return
        if isinstance(instance, str):
            if "minLength" in schema and len(instance) < schema["minLength"]:
                self._fail(path, "shorter than minLength")
            if "maxLength" in schema and len(instance) > schema["maxLength"]:
                self._fail(path, "longer than maxLength")
            if "pattern" in schema and re.search(schema["pattern"], instance) is None:
                self._fail(path, "does not match pattern")
        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if "minimum" in schema and instance < schema["minimum"]:
                self._fail(path, "below minimum")
            if "maximum" in schema and instance > schema["maximum"]:
                self._fail(path, "above maximum")
        if isinstance(instance, list):
            if "minItems" in schema and len(instance) < schema["minItems"]:
                self._fail(path, "fewer than minItems")
            if "maxItems" in schema and len(instance) > schema["maxItems"]:
                self._fail(path, "more than maxItems")
            if "items" in schema:
                for i, item in enumerate(instance):
                    self._check(item, schema["items"], f"{path}[{i}]")
        if isinstance(instance, dict):
            props = schema.get("properties") or {}
            required = schema.get("required") or []
            for key in required:
                if key not in instance:
                    self._fail(path, f"missing {key}")
            additional = schema.get("additionalProperties", True)
            for key, value in instance.items():
                if key in props:
                    self._check(value, props[key], f"{path}.{key}")
                elif additional is False:
                    self._fail(path, f"unexpected property {key}")
                elif isinstance(additional, dict):
                    self._check(value, additional, f"{path}.{key}")

    def check_against(self, instance, schema, path):
        """Return errors for one branch. Does not touch self.errors."""
        probe = Validator(self.root)
        probe._check(instance, schema, path)
        return probe.errors


def validate(instance, schema):
    return Validator(schema).check(instance)


def _pointer(doc, pointer):
    if not pointer or pointer == "/":
        return doc
    node = doc
    for part in pointer.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            node = node[part]
        elif isinstance(node, list):
            node = node[int(part)]
        else:
            raise KeyError(pointer)
    return node


def data_targets(schema):
    """(abspath, label) pairs this schema validates. Empty when the schema is documentation only."""
    meta = schema.get("x-nordic") or {}
    if meta.get("validate") is False:
        return []
    return [(os.path.join(ROOT, rel), rel) for rel in meta.get("files") or []]


def validate_repo():
    """Return a list of human-readable failures. Empty means every mapped file matches."""
    failures = []
    for name, schema in load_schemas():
        for path, label in data_targets(schema):
            if not os.path.exists(path):
                failures.append(f"{name}: missing data file {label}")
                continue
            errors = validate(load_json(path), schema)
            for err in errors[:12]:
                failures.append(f"{label}: {err}")
            if len(errors) > 12:
                failures.append(f"{label}: {len(errors) - 12} more")
    return failures


_HISTORY = {}


def history():
    """Commits that touched schema/, newest first. Empty when git has no such commit."""
    if ROOT in _HISTORY:
        return _HISTORY[ROOT]
    try:
        proc = subprocess.run(
            ["git", "-C", ROOT, "log", "--format=%H%x09%cI%x09%s", "--", "schema"],
            check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        _HISTORY[ROOT] = []
        return []
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3 or not parts[0]:
            continue
        sha, iso, subject = parts
        rows.append({
            "sha": sha,
            "short": sha[:7],
            "committed_at": iso,
            "date": iso[:10],
            "subject": subject.strip(),
            "url": f"{REPO}/commit/{sha}",
        })
    _HISTORY[ROOT] = rows
    return rows


def version_info():
    rows = history()
    if not rows:
        return {"version": None, "commit": None, "committed_at": None, "changelog": []}
    latest = rows[0]
    return {
        "version": latest["date"],
        "commit": latest["short"],
        "sha": latest["sha"],
        "committed_at": latest["committed_at"],
        "url": latest["url"],
        "changelog": rows,
    }


def _resolve_local(schema, ref):
    if ref in ("#", "#/", ""):
        return schema
    if not isinstance(ref, str) or not ref.startswith("#/"):
        raise KeyError(ref)
    node = schema
    for part in ref[2:].split("/"):
        if not part:
            continue
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def type_label(schema):
    if not isinstance(schema, dict):
        return ""
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in schema:
        return " or ".join(type_label(part) for part in schema["anyOf"])
    if "oneOf" in schema:
        return " or ".join(type_label(part) for part in schema["oneOf"])
    kind = schema.get("type")
    if isinstance(kind, list):
        return " or ".join(kind)
    if kind == "array":
        item = type_label(schema.get("items") or {})
        return f"array of {item}" if item else "array"
    if kind == "object":
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict) and not schema.get("properties"):
            inner = type_label(extra)
            return f"object of {inner}" if inner else "object"
    return kind or "value"


def _example_text(schema):
    examples = schema.get("examples") if isinstance(schema, dict) else None
    if not examples:
        return None
    return json.dumps(examples[0], ensure_ascii=False)


def field_rows(schema, row, prefix="", required=False, omitted=()):
    """Flatten a row schema into table rows. Field names stay as stored."""
    if not isinstance(row, dict):
        return []
    if "$ref" in row:
        return field_rows(schema, _resolve_local(schema, row["$ref"]), prefix, required, omitted)
    rows = []
    name = prefix or (schema.get("x-nordic") or {}).get("id") or "value"
    if prefix:
        rows.append({
            "name": prefix,
            "type": type_label(row),
            "required": required,
            "enum": row.get("enum"),
            "example": _example_text(row),
            "description": row.get("description") or "",
            "omitted": prefix.split(".")[-1].split("[")[0] in omitted or prefix in omitted,
        })
    props = row.get("properties") or {}
    req = set(row.get("required") or [])
    for key, sub in props.items():
        child = f"{prefix}.{key}" if prefix else key
        nested = sub
        if isinstance(sub, dict) and "$ref" in sub:
            nested = _resolve_local(schema, sub["$ref"])
        rows.append({
            "name": child,
            "type": type_label(sub),
            "required": key in req,
            "enum": (nested or {}).get("enum") if isinstance(nested, dict) else None,
            "example": _example_text(nested if isinstance(nested, dict) else sub),
            "description": (nested or {}).get("description") if isinstance(nested, dict) else (sub.get("description") if isinstance(sub, dict) else ""),
            "omitted": key in omitted or child in omitted,
        })
        if isinstance(nested, dict) and nested.get("properties") and prefix.count(".") < 2 and "[]" not in prefix:
            rows.extend(field_rows(schema, nested, child, key in req, omitted)[1:])
        items = nested.get("items") if isinstance(nested, dict) else None
        if isinstance(items, dict) and "$ref" in items:
            items = _resolve_local(schema, items["$ref"])
        if isinstance(items, dict) and items.get("properties") and prefix.count(".") < 1:
            rows.extend(field_rows(schema, items, child + "[]", False, omitted)[1:])
    if not props and not prefix:
        rows.append({
            "name": name,
            "type": type_label(row),
            "required": True,
            "enum": row.get("enum"),
            "example": _example_text(row),
            "description": row.get("description") or "",
            "omitted": False,
        })
    return rows


def _sections(schema):
    meta = schema.get("x-nordic") or {}
    if meta.get("sections"):
        return meta["sections"]
    if meta.get("row"):
        return [{"id": meta["id"], "title": None, "row": meta["row"]}]
    if schema.get("properties") or schema.get("$ref"):
        return [{"id": meta.get("id") or "value", "title": None, "row": "#"}]
    return []


def _envelope_schema(schema):
    """Root fields that are not a row array already shown as its own section."""
    props = {}
    for key, sub in (schema.get("properties") or {}).items():
        items = sub.get("items") if isinstance(sub, dict) else None
        if isinstance(sub, dict) and sub.get("type") == "array" and isinstance(items, dict) and "$ref" in items:
            continue
        props[key] = sub
    if not props:
        return None
    return {
        "type": "object",
        "properties": props,
        "required": [key for key in (schema.get("required") or []) if key in props],
    }


def mermaid(schemas):
    ids = {}
    lines = ["erDiagram"]
    for _name, schema in schemas:
        meta = schema.get("x-nordic") or {}
        cid = meta["id"]
        ids[cid] = re.sub(r"[^A-Za-z0-9]", "_", cid).upper()
    seen = set()
    for _name, schema in schemas:
        meta = schema.get("x-nordic") or {}
        src = ids.get(meta["id"])
        for rel in meta.get("relations") or []:
            dst = ids.get(rel.get("to"))
            if not src or not dst:
                continue
            card = rel.get("cardinality") or "many-to-one"
            arrow = {
                "many-to-one": "}|--||",
                "one-to-many": "||--o{",
                "one-to-one": "||--||",
                "many-to-many": "}o--o{",
            }.get(card, "}|--||")
            label = re.sub(r"[^A-Za-z0-9_.-]+", "_", rel.get("field") or "rel").strip("_") or "rel"
            key = (src, arrow, dst, label)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"  {src} {arrow} {dst} : {label}")
    if len(lines) == 1:
        lines.append("  NEWS ||--|| SOURCES : source")
    return "\n".join(lines) + "\n"


def erd_svg(schemas):
    """Inline-friendly SVG. Strokes use the page's own colours when CSS is present."""
    nodes = []
    for _name, schema in schemas:
        meta = schema.get("x-nordic") or {}
        if meta.get("diagram") is False:
            continue
        nodes.append({"id": meta["id"], "title": schema.get("title") or meta["id"]})
    if not nodes:
        return ""
    present = {n["id"] for n in nodes}
    clusters = (
        ["news", "articles", "title-i18n", "blurbs", "illustrations"],
        ["events", "sponsors", "talks", "event-descriptions", "event-redirects"],
        ["sources", "logos", "newsletters"],
        ["orgchart", "profiles", "images", "developers"],
    )
    seen = set()
    columns = []
    for cluster in clusters:
        col = [item for item in cluster if item in present and item not in seen]
        if col:
            columns.append(col)
            seen.update(col)
    rest = [n["id"] for n in nodes if n["id"] not in seen]
    while rest:
        columns.append(rest[:6])
        rest = rest[6:]
    box_w, box_h, gap_x, gap_y = 210, 58, 44, 20
    pad_x, pad_top, pad_bottom = 20, 52, 20
    positions = {}
    col_of = {}
    for c, col in enumerate(columns):
        for r, nid in enumerate(col):
            x = pad_x + c * (box_w + gap_x)
            y = pad_top + r * (box_h + gap_y)
            title = next(n["title"] for n in nodes if n["id"] == nid)
            positions[nid] = (x, y, title)
            col_of[nid] = c
    n_cols = len(columns)
    n_rows = max(len(col) for col in columns)
    width = pad_x * 2 + n_cols * box_w + (n_cols - 1) * gap_x
    height = pad_top + pad_bottom + n_rows * box_h + (n_rows - 1) * gap_y
    ids = {n["id"]: re.sub(r"[^A-Za-z0-9]", "_", n["id"]).upper() for n in nodes}
    edges = []
    for _name, schema in schemas:
        meta = schema.get("x-nordic") or {}
        for rel in meta.get("relations") or []:
            if meta["id"] in positions and rel.get("to") in positions:
                edges.append((meta["id"], rel["to"], rel.get("field") or ""))
    parts = [
        f'<svg class="erd" viewBox="0 0 {width} {height}" role="img" xmlns="http://www.w3.org/2000/svg">',
        "<title>Relations between the public collections</title>",
        "<defs><marker id=\"erd-arrow\" markerWidth=\"8\" markerHeight=\"8\" refX=\"7\" refY=\"3\" orient=\"auto\">"
        "<path d=\"M0,0 L7,3 L0,6 Z\" class=\"erd-arrow\" fill=\"#8A5A0C\"/></marker></defs>",
    ]
    lane = {}

    def slot(key):
        n = lane.get(key, 0)
        lane[key] = n + 1
        return n

    for src, dst, _field in edges:
        x1, y1, _ = positions[src]
        x2, y2, _ = positions[dst]
        c1, c2 = col_of[src], col_of[dst]
        if src == dst:
            n = slot(("self", src))
            x = x1 + box_w
            y = y1 + 16 + n * 10
            d = f"M {x:.0f} {y:.0f} C {x + 26:.0f} {y - 14:.0f}, {x + 26:.0f} {y + 18:.0f}, {x:.0f} {y + 12:.0f}"
        elif c1 == c2:
            n = slot(("col", c1, min(y1, y2)))
            gutter = x1 - 8 - n * 4
            top, bot = (y1 + box_h, y2) if y1 < y2 else (y1, y2 + box_h)
            mid = x1 + box_w / 2 + (n - 1) * 8
            d = f"M {mid:.0f} {top:.0f} L {gutter:.0f} {top:.0f} L {gutter:.0f} {bot:.0f} L {mid:.0f} {bot:.0f}"
        elif abs(c1 - c2) == 1:
            n = slot(("adj", min(c1, c2), round(y1), round(y2)))
            if x1 < x2:
                leave, enter = x1 + box_w, x2
            else:
                leave, enter = x1, x2 + box_w
            y_leave = y1 + 18 + n * 8
            y_enter = y2 + 18 + (n % 3) * 8
            elbow = leave + (10 + n * 4) * (1 if leave < enter else -1)
            d = f"M {leave:.0f} {y_leave:.0f} L {elbow:.0f} {y_leave:.0f} L {elbow:.0f} {y_enter:.0f} L {enter:.0f} {y_enter:.0f}"
        else:
            n = slot(("bus", min(c1, c2), max(c1, c2)))
            bus = 8 + n * 4
            if x1 < x2:
                leave, enter = x1 + box_w, x2
            else:
                leave, enter = x1, x2 + box_w
            y_leave = y1 + box_h / 2
            y_enter = y2 + box_h / 2
            d = f"M {leave:.0f} {y_leave:.0f} L {leave + (8 if leave < enter else -8):.0f} {y_leave:.0f} L {leave + (8 if leave < enter else -8):.0f} {bus:.0f} L {enter + (-8 if leave < enter else 8):.0f} {bus:.0f} L {enter + (-8 if leave < enter else 8):.0f} {y_enter:.0f} L {enter:.0f} {y_enter:.0f}"
        parts.append(
            f'<path class="erd-edge" fill="none" stroke="#8A5A0C" stroke-width="1.25" opacity="0.8" '
            f'd="{d}" marker-end="url(#erd-arrow)"/>'
        )
    for node in nodes:
        x, y, title = positions[node["id"]]
        label = title if len(title) <= 32 else title[:31] + "…"
        parts.append(
            f'<g class="erd-node"><rect class="erd-box" x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="8" fill="#F0F1EC" stroke="#1E3A45"/>'
            f'<text x="{x + 14}" y="{y + 28}" class="erd-kicker" fill="#8A5A0C">{html.escape(ids[node["id"]])}</text>'
            f'<text x="{x + 14}" y="{y + 48}" class="erd-label" fill="#1D1C1A">{html.escape(label)}</text></g>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def page_body(lang):
    """/db/ body for one site language. Collection and field names stay English."""
    import i18n
    def t(key, **kw):
        return i18n.t(lang, key, **kw)
    schemas = load_schemas()
    info = version_info()
    if info.get("version"):
        version = f'{_esc(info["version"])} · <a href="{_esc(info["url"])}"><code>{_esc(info["commit"])}</code></a>'
        changed = _esc(info["committed_at"])
    else:
        version = _esc(t("db_no_history"))
        changed = _esc(t("db_none"))
    jump = []
    blocks = []
    for filename, schema in schemas:
        meta = schema.get("x-nordic") or {}
        cid = meta["id"]
        jump.append(f'<li><a href="#{_esc(cid)}">{_esc(schema.get("title") or cid)}</a></li>')
        blocks.append(_collection_html(lang, t, filename, schema))
    log_rows = []
    for row in info.get("changelog") or []:
        log_rows.append(
            "<tr>"
            f"<td><time datetime=\"{_esc(row['committed_at'])}\">{_esc(row['date'])}</time></td>"
            f"<td><a href=\"{_esc(row['url'])}\"><code>{_esc(row['short'])}</code></a></td>"
            f"<td>{_esc(row['subject'])}</td></tr>"
        )
    if not log_rows:
        log_rows.append(f"<tr><td colspan=\"3\">{_esc(t('db_no_history'))}</td></tr>")
    diagram = erd_svg(schemas)
    mmd = mermaid(schemas)
    changed_html = f'<time datetime="{changed}">{changed}</time>' if info.get("version") else changed
    return f"""<h1>{_esc(t("db_h1"))}</h1>
<p class="lead">{_esc(t("db_lead"))}</p>
<div class="dbpage">
<p class="meta dbmeta"><span><b>{_esc(t("db_version"))}</b> {version}</span>
<span><b>{_esc(t("db_changed"))}</b> {changed_html}</span>
<span><a href="/api/v1/schema/index.json"><code>/api/v1/schema/index.json</code></a></span></p>
<h2 id="private">{_esc(t("db_private_h"))}</h2>
<div class="notice"><p>{_esc(t("db_private_tips"))}</p><p>{_esc(t("db_private_mail"))}</p></div>
<h2 id="diagram">{_esc(t("db_erd"))}</h2>
<figure>{diagram}</figure>
<details class="mmd"><summary>{_esc(t("db_mermaid"))}</summary><pre>{_esc(mmd)}</pre></details>
<h2 id="collections">{_esc(t("db_collections"))}</h2>
<ul class="jump">{''.join(jump)}</ul>
{''.join(blocks)}
<h2 id="changelog">{_esc(t("db_changelog"))}</h2>
<div class="tablewrap"><table class="list"><thead><tr><th>{_esc(t("db_when"))}</th><th>{_esc(t("db_commit"))}</th><th>{_esc(t("db_change"))}</th></tr></thead>
<tbody>{''.join(log_rows)}</tbody></table></div>
</div>"""


def _collection_html(lang, t, filename, schema):
    meta = schema.get("x-nordic") or {}
    cid = meta["id"]
    files = meta.get("files") or []
    file_html = ", ".join(f"<code>{_esc(rel)}</code>" for rel in files) or _esc(t("db_none"))
    apis = []
    for ep in meta.get("api") or []:
        path = ep.get("path") or ""
        note = ep.get("note") or ""
        apis.append(f'<li><a href="{_esc(path)}"><code>{_esc(path)}</code></a>{(" — " + _esc(note)) if note else ""}</li>')
    pages = []
    for path in meta.get("pages") or []:
        pages.append(f'<li><a href="{_esc(path)}"><code>{_esc(path)}</code></a></li>')
    rels = []
    for rel in meta.get("relations") or []:
        rels.append(
            f'<li><code>{_esc(rel.get("field") or "")}</code> → <a href="#{_esc(rel.get("to") or "")}">'
            f'{_esc(rel.get("to") or "")}</a> <span class="meta">{_esc(rel.get("cardinality") or "")}</span>'
            f'{(" — " + _esc(rel["note"])) if rel.get("note") else ""}</li>'
        )
    omitted = set(meta.get("omitted_from_api") or [])
    parts = [
        f'<h2 id="{_esc(cid)}" lang="en" dir="ltr">{_esc(schema.get("title") or cid)}</h2>',
        f'<p lang="en" dir="ltr">{_esc(schema.get("description") or meta.get("summary") or "")}</p>',
        f'<p class="meta"><b>{_esc(t("db_file"))}</b> {file_html}'
        f' · <a href="/api/v1/schema/{_esc(filename)}">{_esc(t("db_json"))}</a></p>',
    ]
    if pages:
        parts.append(f'<p class="meta"><b>{_esc(t("db_page"))}</b></p><ul>{"".join(pages)}</ul>')
    if apis:
        parts.append(f'<p class="meta"><b>{_esc(t("db_api"))}</b></p><ul>{"".join(apis)}</ul>')
    else:
        parts.append(f'<p class="meta">{_esc(t("db_no_api"))}</p>')
    if rels:
        parts.append(f'<h3>{_esc(t("db_relations"))}</h3><ul>{"".join(rels)}</ul>')
    sections = _sections(schema)
    covers_root = any(section.get("row") in ("#", "#/") for section in sections)
    shown_derived = False
    if not covers_root:
        envelope = _envelope_schema(schema)
        if envelope and envelope.get("properties"):
            parts.append(f'<h3>{_esc(t("db_file_fields"))}</h3>')
            parts.append(_field_table(t, field_rows(schema, envelope, omitted=omitted), meta.get("derived") or []))
            shown_derived = True
    for section in sections:
        ref = section.get("row")
        if not ref:
            continue
        if ref in ("#", "#/"):
            row = schema
        elif ref.startswith("#/"):
            row = _resolve_local(schema, ref)
        else:
            continue
        if section.get("title"):
            parts.append(f'<h3 id="{_esc(cid)}-{_esc(section["id"])}" lang="en" dir="ltr">{_esc(section["title"])}</h3>')
        if section.get("summary"):
            parts.append(f'<p lang="en" dir="ltr">{_esc(section["summary"])}</p>')
        derived = [] if shown_derived else (meta.get("derived") or [])
        shown_derived = True
        parts.append(_field_table(t, field_rows(schema, row, omitted=omitted), derived))
    return "\n".join(parts)


def _field_table(t, rows, derived):
    body = []
    for row in rows:
        flags = []
        flags.append(_esc(t("db_required")) if row["required"] else _esc(t("db_optional")))
        if row.get("omitted"):
            flags.append(_esc(t("db_omitted")))
        enum = ""
        if row.get("enum"):
            enum = " ".join(f"<code>{_esc(json.dumps(v, ensure_ascii=False))}</code>" for v in row["enum"])
        example = f"<code>{_esc(row['example'])}</code>" if row.get("example") else _esc(t("db_none"))
        desc = _esc(row.get("description") or "")
        body.append(
            "<tr>"
            f"<th scope=\"row\"><code>{_esc(row['name'])}</code></th>"
            f"<td><code>{_esc(row['type'])}</code></td>"
            f"<td>{' · '.join(flags)}</td>"
            f"<td>{enum or _esc(t('db_none'))}</td>"
            f"<td>{example}</td>"
            f"<td>{desc}</td></tr>"
        )
    for item in derived:
        enum = " ".join(f"<code>{_esc(v)}</code>" for v in item.get("enum") or [])
        body.append(
            "<tr>"
            f"<th scope=\"row\"><code>{_esc(item.get('name'))}</code></th>"
            f"<td><code>{_esc(item.get('type') or 'string')}</code></td>"
            f"<td>{_esc(t('db_derived'))}</td>"
            f"<td>{enum or _esc(t('db_none'))}</td>"
            f"<td>{_esc(t('db_none'))}</td>"
            f"<td>{_esc(item.get('description') or '')}</td></tr>"
        )
    return (
        f'<div class="tablewrap" lang="en" dir="ltr"><table class="list fields"><thead><tr>'
        f'<th>{_esc(t("db_field"))}</th><th>{_esc(t("db_type"))}</th><th>{_esc(t("db_status"))}</th>'
        f'<th>{_esc(t("db_enum"))}</th><th>{_esc(t("db_example"))}</th><th>{_esc(t("db_notes"))}</th>'
        f'</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    )


def catalog(base, generated_at=None):
    info = version_info()
    base = base if base.endswith("/") else base + "/"
    collections = []
    for filename, schema in load_schemas():
        meta = schema.get("x-nordic") or {}
        collections.append({
            "id": meta["id"],
            "title": schema.get("title"),
            "description": schema.get("description"),
            "files": meta.get("files") or [],
            "pages": meta.get("pages") or [],
            "api": meta.get("api") or [],
            "relations": meta.get("relations") or [],
            "derived": meta.get("derived") or [],
            "omitted_from_api": meta.get("omitted_from_api") or [],
            "schema_url": base + "api/v1/schema/" + filename,
        })
    return {
        "api_version": "1",
        "name": "Nordic Crypto",
        "generated_at": generated_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "title": "Nordic Crypto data model",
        "docs_url": base + "db/",
        "schema_version": info.get("version"),
        "commit": info.get("commit"),
        "committed_at": info.get("committed_at"),
        "commit_url": info.get("url"),
        "changelog_url": base + "api/v1/schema/changelog.json",
        "erd_svg_url": base + "api/v1/schema/erd.svg",
        "erd_mermaid_url": base + "api/v1/schema/erd.mmd",
        "note": (
            "These schemas are copied from schema/*.schema.json at build time. "
            "Field names are the stored names. Reader tips and newsletter subscriber addresses "
            "are private Cloudflare D1 stores and are not described field by field."
        ),
        "private": [
            {
                "id": "tips",
                "store": "Cloudflare D1",
                "summary": "Reader tips. The text of a tip is not in the public files and is not served under /api/v1/.",
            },
            {
                "id": "subscribers",
                "store": "Cloudflare D1",
                "summary": "Newsletter subscriber addresses. They are not in the public files and are not served under /api/v1/.",
            },
        ],
        "collections": collections,
    }


def publish(site, base, generated_at=None):
    """Write /api/v1/schema/ into the built site. Returns the catalogue."""
    doc = catalog(base, generated_at)
    out_dir = os.path.join(site, "api", "v1", "schema")
    os.makedirs(out_dir, exist_ok=True)
    for filename, schema in load_schemas():
        dump(os.path.join(out_dir, filename), schema)
    dump(os.path.join(out_dir, "index.json"), doc)
    dump(os.path.join(out_dir, "changelog.json"), {
        "schema_version": doc.get("schema_version"),
        "commit": doc.get("commit"),
        "committed_at": doc.get("committed_at"),
        "entries": version_info().get("changelog") or [],
    })
    mmd = mermaid(load_schemas())
    with open(os.path.join(out_dir, "erd.mmd"), "w", encoding="utf-8") as fh:
        fh.write(mmd)
    svg = erd_svg(load_schemas())
    style = (
        "<style>.erd-edge{stroke:#8A5A0C}.erd-arrow{fill:#8A5A0C}"
        ".erd-kicker{font:600 11px ui-monospace,monospace;letter-spacing:.06em}"
        ".erd-label{font:600 15px ui-sans-serif,system-ui,sans-serif}</style>"
    )
    with open(os.path.join(out_dir, "erd.svg"), "w", encoding="utf-8") as fh:
        fh.write(svg.replace("<title>", style + "<title>", 1))
    return doc


def contribute(feed):
    """Register the schema catalogue on the public API index. Called from tools/api_feed.py."""
    publish(feed.site, feed.base, generated_at=feed.generated)
    feed.add_endpoint(
        "api-v1-schema",
        "api/v1/schema/index.json",
        "JSON Schemas for the public data model: fields, enums, relations, schema version and changelog. "
        "Human page: /db/. Reader tips and newsletter addresses are named only, not described field by field.",
        "Document",
        example="api/v1/schema/news.schema.json",
        item_template="api/v1/schema/{name}.schema.json",
    )
