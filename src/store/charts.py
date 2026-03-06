"""Lightweight HTTP chart server for browseable/linkable signal charts.

Routes:
  GET /charts/{kind}/{entity}/{type}/{field}[,field2]?periods=24&chart_type=line&archive=false
  GET /charts/                                — index: lists available entities/types

Runs on port 8066 by default (CHARTS_PORT env var).
Reuses DB and chart logic from server.py.

Example:
  https://assist.uber.space/charts/countries/DEU/indicators/gdp_growth_pct
  https://assist.uber.space/charts/stocks/AAPL/price/open,close?periods=60&chart_type=line
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os
import sys
import json

# Ensure we can import from the store module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from src.store.server import chart, _snap_col, _arch_col, _db, VALID_KINDS

PORT = int(os.environ.get("CHARTS_PORT", "8066"))

_INDEX_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Signal Charts</title>
<style>
body{font-family:system-ui;max-width:800px;margin:40px auto;padding:0 20px;color:#333}
h1{color:#1a1a2e}a{color:#0066cc}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:8px;border-bottom:1px solid #eee}
th{background:#f8f9fa}tr:hover{background:#f0f4ff}
.muted{color:#888;font-size:0.9em}
</style></head><body>
<h1>Signal Charts</h1>
<p class="muted">URL format: /charts/{kind}/{entity}/{type}/{field1,field2}</p>
<table><thead><tr><th>Kind</th><th>Entity</th><th>Type</th><th>Source</th><th>Fields (sample)</th></tr></thead>
<tbody>{rows}</tbody></table>
</body></html>"""

_ROW = '<tr><td>{kind}</td><td><a href="/charts/{kind}/{entity}/{type}/{fields}">{entity}</a></td><td>{type}</td><td>{source}</td><td><code>{fields}</code></td></tr>'


class ChartHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)

        if path in ("/charts", "/charts/", ""):
            self._serve_index()
        elif path.startswith("/charts/"):
            parts = path.split("/")[2:]  # skip "" and "charts"
            if len(parts) >= 4:
                kind = parts[0]
                entity = parts[1]
                typ = parts[2]
                fields = parts[3].split(",")
                periods = int(qs.get("periods", ["24"])[0])
                chart_type = qs.get("chart_type", ["line"])[0]
                archive = qs.get("archive", ["false"])[0].lower() == "true"
                self._serve_chart(kind, entity, typ, fields, periods, chart_type, archive)
            else:
                self._error(400, "URL format: /charts/{kind}/{entity}/{type}/{field1,field2}")
        elif path == "/health":
            self._respond(200, "text/plain", "ok")
        else:
            self._error(404, "Not found. Try /charts/")

    def _serve_chart(self, kind, entity, typ, fields, periods, chart_type, archive):
        try:
            html = chart(kind, entity, typ, fields, periods, archive, chart_type)
            if html.startswith("No data") or html.startswith("Unknown kind"):
                self._error(404, html)
            else:
                self._respond(200, "text/html", html)
        except Exception as e:
            self._error(500, f"Chart error: {e}")

    def _serve_index(self):
        try:
            rows = []
            for kind in sorted(VALID_KINDS):
                for col_name, col_fn in [("snap", _snap_col), ("arch", _arch_col)]:
                    try:
                        col = col_fn(kind)
                        pipeline = [
                            {"$group": {
                                "_id": {"entity": "$meta.entity", "type": "$meta.type"},
                                "source": {"$first": "$meta.source"},
                                "sample": {"$first": "$data"},
                            }},
                            {"$sort": {"_id.entity": 1, "_id.type": 1}},
                            {"$limit": 200},
                        ]
                        for doc in col.aggregate(pipeline):
                            eid = doc["_id"]["entity"] or ""
                            etype = doc["_id"]["type"] or ""
                            source = doc.get("source", "")
                            sample_fields = list((doc.get("sample") or {}).keys())[:5]
                            fields_str = ",".join(sample_fields) if sample_fields else "data"
                            rows.append(_ROW.format(
                                kind=kind, entity=eid, type=etype,
                                source=source, fields=fields_str,
                            ))
                    except Exception:
                        pass

            html = _INDEX_HTML.format(rows="\n".join(rows) if rows else "<tr><td colspan=5>No data yet</td></tr>")
            self._respond(200, "text/html", html)
        except Exception as e:
            self._error(500, f"Index error: {e}")

    def _respond(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)

    def _error(self, code, msg):
        self._respond(code, "text/plain", msg)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    # Uberspace web backends require 0.0.0.0 (not 127.0.0.1)
    server = HTTPServer(("0.0.0.0", PORT), ChartHandler)
    print(f"Chart server listening on http://0.0.0.0:{PORT}/charts/")
    server.serve_forever()
