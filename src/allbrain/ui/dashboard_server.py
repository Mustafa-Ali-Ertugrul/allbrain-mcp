from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from allbrain.config import default_db_path
from allbrain.storage import BrainRepository, create_engine_for_path, init_db
from allbrain.ui import GraphExplorer, MetricsDashboard

_HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AllBrain Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0d1117; color: #c9d1d9; padding: 20px; }
  h1 { color: #58a6ff; font-size: 1.5rem; margin-bottom: 4px; }
  .subtitle { color: #8b949e; font-size: 0.9rem; margin-bottom: 20px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .card h2 { font-size: 1rem; color: #58a6ff; margin-bottom: 12px;
             border-bottom: 1px solid #21262d; padding-bottom: 8px; }
  .stat { display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.85rem; }
  .stat .val { color: #7ee787; font-weight: 600; }
  table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
  th, td { text-align: left; padding: 6px 4px; border-bottom: 1px solid #21262d; }
  th { color: #8b949e; font-weight: 500; }
  .badge { display: inline-block; padding: 1px 6px; border-radius: 8px; font-size: 0.75rem; }
  .badge-ok { background: #1b4721; color: #7ee787; }
  .badge-warn { background: #4d3400; color: #d29922; }
  .badge-err { background: #49241e; color: #f85149; }
  .ttrunc { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .nav a { color: #58a6ff; text-decoration: none; margin-right: 16px; font-size: 0.85rem; }
  .nav a:hover { text-decoration: underline; }
  .nav { margin-bottom: 16px; }
  pre { font-size: 0.75rem; max-height: 300px; overflow: auto; }
  .refresh { float: right; color: #8b949e; font-size: 0.8rem; cursor: pointer; }
  .refresh:hover { color: #58a6ff; }
</style>
</head>
<body>
<h1>AllBrain Dashboard</h1>
<div class="subtitle" id="subtitle">loading...</div>
<div class="nav">
  <a href="#" onclick="showTab('overview')">Overview</a>
  <a href="#" onclick="showTab('events')">Events</a>
  <a href="#" onclick="showTab('graph')">Graph</a>
  <span class="refresh" onclick="refresh()">↻ refresh</span>
</div>
<div id="overview" class="tab-content"></div>
<div id="events" class="tab-content" style="display:none"></div>
<div id="graph" class="tab-content" style="display:none"></div>
<script>
async function api(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}
function esc(s) { const d = document.createElement('div'); d.textContent = String(s ?? ''); return d.innerHTML; }

function showTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
  document.getElementById(name).style.display = '';
}

async function refresh() {
  const subtitle = document.getElementById('subtitle');
  subtitle.textContent = 'refreshing...';
  await Promise.all([renderOverview(), renderEvents(), renderGraph()]);
  subtitle.textContent = 'last updated: ' + new Date().toLocaleTimeString();
}

async function renderOverview() {
  const data = await api('/api/overview');
  const el = document.getElementById('overview');
  let html = '<div class="grid">';
  html += `<div class="card"><h2>Database</h2>
    <div class="stat"><span>Events</span><span class="val">${data.event_count}</span></div>
    <div class="stat"><span>Sessions</span><span class="val">${data.session_count}</span></div>
    <div class="stat"><span>Conflicts</span><span class="val">${data.conflict_count}</span></div>
    <div class="stat"><span>Agents</span><span class="val">${data.agent_count}</span></div>
    <div class="stat"><span>DB size</span><span class="val">${data.db_size_mb} MB</span></div>
  </div>`;
  html += `<div class="card"><h2>Agents</h2>`;
  for (const a of (data.agents || [])) {
    const cls = a.status === 'active' ? 'badge-ok' : 'badge-warn';
    html += `<div class="stat"><span>${esc(a.name)}</span><span class="badge ${cls}">${esc(a.status)}</span></div>`;
  }
  html += '</div>';
  html += `<div class="card"><h2>Leaderboard</h2>`;
  for (const l of (data.leaderboard || [])) {
    html += `<div class="stat"><span>${esc(l.agent)}</span><span class="val">${l.events} events</span></div>`;
  }
  html += '</div></div>';
  el.innerHTML = html;
}

async function renderEvents() {
  const data = await api('/api/events?limit=50');
  const el = document.getElementById('events');
  let html = '<div class="card"><h2>Recent Events</h2>'
    + '<table><tr><th>Time</th><th>Agent</th><th>Type</th><th>Payload</th></tr>';
  for (const e of (data.events || [])) {
    const p = typeof e.payload === 'object' ? JSON.stringify(e.payload).slice(0, 120) : esc(e.payload);
    html += `<tr><td>${esc(e.created_at || '').slice(11,19)}</td>
      <td>${esc(e.agent_id || e.agent_name || '')}</td>
      <td>${esc(e.type)}</td>
      <td class="ttrunc">${p}</td></tr>`;
  }
  html += '</table></div>';
  el.innerHTML = html;
}

async function renderGraph() {
  const data = await api('/api/graph');
  const el = document.getElementById('graph');
  let html = '<div class="grid">';
  html += `<div class="card"><h2>Graph</h2>
    <div class="stat"><span>Nodes</span><span class="val">${data.node_count}</span></div>
    <div class="stat"><span>Edges</span><span class="val">${data.edge_count}</span></div>
    <div class="stat"><span>Has cycle</span><span class="val">${data.has_cycle ? 'yes' : 'no'}</span></div>
  </div>`;
  html += `<div class="card"><h2>Failed Paths</h2>`;
  for (const p of (data.failed_paths || [])) {
    html += `<div class="stat"><span class="ttrunc">${esc(p)}</span></div>`;
  }
  html += '</div></div>';
  el.innerHTML = html;
}

refresh();
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    repo: BrainRepository | None = None

    def _send_json(self, data: Any, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str, indent=2).encode())

    def _send_html(self, html: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def _get_events(self, limit: int = 100) -> list:
        from allbrain.models.schemas import EventRead

        if self.repo is None:
            return []
        events = self.repo.list_events(limit=limit)
        return [EventRead.model_validate(e).model_dump(mode="json") for e in events]

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            return self._send_html(_HTML_PAGE)
        elif self.path == "/api/overview":
            return self._overview()
        elif self.path.startswith("/api/events"):
            return self._events()
        elif self.path == "/api/graph":
            return self._graph()
        elif self.path == "/api/metrics":
            return self._metrics()
        elif self.path == "/health":
            self._send_json({"status": "ok"})
        else:
            self._send_json({"error": "not found"}, 404)

    def _overview(self) -> None:
        from sqlmodel import select as sql_select

        from allbrain.storage.repository import Event as EventModel
        from allbrain.storage.repository import Session as SessionModel

        if self.repo is None:
            return self._send_json({"error": "no repo"})
        events = self._get_events()
        with self.repo.engine.connect() as conn:
            session_count = len(conn.execute(sql_select(SessionModel)).fetchall())
            event_count = len(conn.execute(sql_select(EventModel)).fetchall())
        db_path = default_db_path()
        db_size = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0.0
        agent_names: set[str] = set()
        for e in events:
            name = e.get("agent_id") or e.get("agent_name") or "?"
            agent_names.add(name)
        leaderboard: list[dict] = []
        seen: dict[str, int] = {}
        for e in events:
            name = e.get("agent_id") or e.get("agent_name") or "?"
            seen[name] = seen.get(name, 0) + 1
        for name, count in sorted(seen.items(), key=lambda x: -x[1]):
            leaderboard.append({"agent": name, "events": count})
        self._send_json(
            {
                "event_count": event_count,
                "session_count": session_count,
                "conflict_count": sum(1 for e in events if e.get("type", "").startswith("conflict")),
                "agent_count": len(agent_names),
                "agents": [{"name": n, "status": "active"} for n in sorted(agent_names)],
                "leaderboard": leaderboard,
                "db_size_mb": round(db_size, 2),
            }
        )

    def _events(self) -> None:
        import urllib.parse

        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        limit = int(qs.get("limit", [50])[0])
        events = self._get_events(limit=limit)
        self._send_json({"events": events, "count": len(events)})

    def _graph(self) -> None:
        events = self._get_events(limit=200)
        if not events:
            return self._send_json({"node_count": 0, "edge_count": 0, "has_cycle": False, "failed_paths": []})
        from allbrain.models.schemas import EventRead

        parsed = [EventRead(**e) for e in events]
        graph = GraphExplorer().build(parsed)
        self._send_json(
            {
                "node_count": len(graph.get("nodes", [])),
                "edge_count": len(graph.get("edges", [])),
                "has_cycle": graph.get("has_cycle", False),
                "failed_paths": graph.get("path_traces", {}).get("failed", []),
            }
        )

    def _metrics(self) -> None:
        events = self._get_events(limit=200)
        if not events:
            return self._send_json({})
        from allbrain.models.schemas import EventRead

        parsed = [EventRead(**e) for e in events]
        metrics = MetricsDashboard().build(parsed)
        self._send_json(metrics)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(f"[dashboard] {args[0]} {args[1]} {args[2]}\n")


def start_dashboard(host: str = "127.0.0.1", port: int = 8080) -> None:
    engine = create_engine_for_path(default_db_path())
    init_db(engine)
    DashboardHandler.repo = BrainRepository(engine)

    server = HTTPServer((host, port), DashboardHandler)
    print(f"\n  AllBrain Dashboard → http://{host}:{port}/\n")
    print("  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        engine.dispose()
        server.server_close()
