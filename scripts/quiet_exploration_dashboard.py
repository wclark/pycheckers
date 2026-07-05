import argparse
import csv
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from run_quiet_exploration import METRIC_FIELDS
from pycheckers.quiet import QuietPositionGraph


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quiet Checkers Exploration</title>
  <style>
    body { margin: 0; font-family: system-ui, sans-serif; background: #f7f7f4; color: #151515; }
    main { padding: 18px 22px 24px; }
    h1 { font-size: 20px; margin: 0 0 8px; }
    #summary { font-size: 14px; margin-bottom: 14px; white-space: pre-wrap; }
    canvas { width: 100%; height: 620px; background: white; border: 1px solid #b8b8b8; }
    table { border-collapse: collapse; width: 100%; margin-top: 14px; font-size: 12px; background: white; }
    th, td { border: 1px solid #d1d1d1; padding: 5px 7px; text-align: right; }
    th { background: #ecece7; }
    th:first-child, td:first-child { text-align: left; }
    a { color: #064f91; }
  </style>
</head>
<body>
<main>
  <h1>Quiet Checkers Exploration</h1>
  <div id="summary">Waiting for the first round...</div>
  <canvas id="chart" width="1500" height="720"></canvas>
  <table>
    <thead>
      <tr>
        <th>round</th><th>sec</th><th>frontier</th><th>new</th><th>total</th>
        <th>pruned states</th><th>pruned moves</th><th>terminal total</th><th>round sec</th>
      </tr>
    </thead>
    <tbody id="rows"></tbody>
  </table>
</main>
<script>
const canvas = document.getElementById("chart");
const ctx = canvas.getContext("2d");

function n(value) {
  return Number(value || 0);
}

function fmt(value) {
  return n(value).toLocaleString();
}

function maxValue(rows, keys) {
  let max = 1;
  for (const row of rows) {
    for (const key of keys) max = Math.max(max, n(row[key]));
  }
  return max;
}

function drawPanel(x, y, w, h, title, rows, specs, options = {}) {
  ctx.save();
  ctx.strokeStyle = "#d4d4d4";
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(x, y, w, h);
  ctx.strokeRect(x, y, w, h);
  ctx.fillStyle = "#151515";
  ctx.font = "16px system-ui, sans-serif";
  ctx.fillText(title, x + 12, y + 24);

  const left = x + 54;
  const top = y + 42;
  const right = x + w - 18;
  const bottom = y + h - 34;
  const plotW = Math.max(1, right - left);
  const plotH = Math.max(1, bottom - top);
  const maxY = maxValue(rows, specs.map(spec => spec.key));
  const scaleY = options.log ? Math.log10(maxY + 1) : maxY;

  ctx.strokeStyle = "#e5e5e5";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const yy = top + (plotH * i / 4);
    ctx.beginPath();
    ctx.moveTo(left, yy);
    ctx.lineTo(right, yy);
    ctx.stroke();
  }

  ctx.strokeStyle = "#3c3c3c";
  ctx.beginPath();
  ctx.moveTo(left, top);
  ctx.lineTo(left, bottom);
  ctx.lineTo(right, bottom);
  ctx.stroke();

  ctx.font = "12px system-ui, sans-serif";
  ctx.fillStyle = "#555";
  ctx.fillText(fmt(maxY), x + 8, top + 4);
  ctx.fillText("0", x + 30, bottom);

  const count = rows.length;
  specs.forEach((spec, specIndex) => {
    ctx.strokeStyle = spec.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    rows.forEach((row, index) => {
      const raw = n(row[spec.key]);
      const scaled = options.log ? Math.log10(raw + 1) : raw;
      const xx = left + (count <= 1 ? 0 : plotW * index / (count - 1));
      const yy = bottom - (plotH * scaled / scaleY);
      if (index === 0) ctx.moveTo(xx, yy);
      else ctx.lineTo(xx, yy);
    });
    ctx.stroke();

    ctx.fillStyle = spec.color;
    ctx.fillRect(left + specIndex * 150, y + h - 22, 10, 10);
    ctx.fillStyle = "#333";
    ctx.fillText(spec.label, left + 15 + specIndex * 150, y + h - 12);
  });
  ctx.restore();
}

function draw(data) {
  const rows = data.rows || [];
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!rows.length) return;

  const latest = rows[rows.length - 1];
  const status = data.running ? "running" : "stopped";
  document.getElementById("summary").textContent =
    `Status: ${status} (${data.stop_reason || "no stop reason yet"})\\n` +
    `Round ${latest.round}: total ${fmt(latest.total_states)}, new ${fmt(latest.new_states)}, ` +
    `frontier ${fmt(latest.next_frontier)}, pruned leaf states ${fmt(latest.pruned_leaf_states)}, ` +
    `terminal total ${fmt(latest.terminal_states_total)}, round ${latest.round_sec}s\\n` +
    `CSV: ${data.csv_path}\\nJSONL: ${data.jsonl_path}`;

  const margin = 18;
  const panelW = (canvas.width - margin * 3) / 2;
  const panelH = (canvas.height - margin * 3) / 2;
  drawPanel(margin, margin, panelW, panelH, "Total quiet states", rows, [
    { key: "total_states", label: "total", color: "#1f77b4" },
    { key: "expanded_total", label: "expanded", color: "#2ca02c" }
  ], { log: true });
  drawPanel(margin * 2 + panelW, margin, panelW, panelH, "Round growth", rows, [
    { key: "new_states", label: "new", color: "#ff7f0e" },
    { key: "existing_state_targets", label: "existing-state targets", color: "#9467bd" }
  ]);
  drawPanel(margin, margin * 2 + panelH, panelW, panelH, "Pruned exits", rows, [
    { key: "pruned_leaf_states", label: "source states", color: "#d62728" },
    { key: "pruned_leaf_moves", label: "moves", color: "#8c564b" },
    { key: "terminal_states_total", label: "terminal total", color: "#111111" }
  ]);
  drawPanel(margin * 2 + panelW, margin * 2 + panelH, panelW, panelH, "Time and throughput", rows, [
    { key: "round_sec", label: "round sec", color: "#17becf" },
    { key: "states_per_sec", label: "states/sec", color: "#bcbd22" }
  ], { log: true });

  document.getElementById("rows").innerHTML = rows.slice(-12).reverse().map(row => `
    <tr>
      <td>${row.round}</td><td>${row.elapsed_sec}</td><td>${fmt(row.frontier_in)}</td>
      <td>${fmt(row.new_states)}</td><td>${fmt(row.total_states)}</td>
      <td>${fmt(row.pruned_leaf_states)}</td><td>${fmt(row.pruned_leaf_moves)}</td>
      <td>${fmt(row.terminal_states_total)}</td><td>${row.round_sec}</td>
    </tr>`).join("");
}

async function refresh() {
  try {
    const response = await fetch("/metrics", { cache: "no-store" });
    draw(await response.json());
  } catch (error) {
    document.getElementById("summary").textContent = `Dashboard error: ${error}`;
  }
  setTimeout(refresh, 1000);
}

refresh();
</script>
</body>
</html>
"""


class SharedState:
    def __init__(self, csv_path, jsonl_path):
        self.lock = threading.Lock()
        self.rows = []
        self.running = True
        self.stop_reason = ""
        self.csv_path = str(csv_path.resolve())
        self.jsonl_path = str(jsonl_path.resolve())

    def append_row(self, row):
        with self.lock:
            self.rows.append(row)

    def finish(self, reason):
        with self.lock:
            self.running = False
            self.stop_reason = reason

    def snapshot(self):
        with self.lock:
            return {
                "rows": list(self.rows),
                "running": self.running,
                "stop_reason": self.stop_reason,
                "csv_path": self.csv_path,
                "jsonl_path": self.jsonl_path,
            }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Serve a live browser dashboard for quiet checkers exploration."
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--max-rounds", type=int, default=None)
    parser.add_argument("--max-seconds", type=float, default=120)
    parser.add_argument("--max-total-states", type=int, default=3_000_000)
    parser.add_argument("--out-dir", default="quiet_exploration_runs")
    parser.add_argument("--run-name", default=None)
    return parser.parse_args()


def explore(shared, args):
    graph = QuietPositionGraph()
    started = time.perf_counter()

    with open(shared.csv_path, "w", newline="", encoding="utf-8") as csv_file, open(
        shared.jsonl_path, "w", encoding="utf-8"
    ) as jsonl_file:
        writer = csv.DictWriter(csv_file, fieldnames=METRIC_FIELDS)
        writer.writeheader()

        stop_reason = "frontier exhausted"
        while graph.frontier_keys:
            elapsed = time.perf_counter() - started
            if args.max_rounds is not None and len(graph.rounds) >= args.max_rounds:
                stop_reason = "max rounds reached"
                break
            if args.max_seconds is not None and elapsed >= args.max_seconds:
                stop_reason = "max seconds reached"
                break
            if args.max_total_states is not None and len(graph.state_keys) >= args.max_total_states:
                stop_reason = "max total states reached"
                break

            row = graph.run_round(started=started)
            writer.writerow(row)
            csv_file.flush()
            jsonl_file.write(json.dumps(row, sort_keys=True) + "\n")
            jsonl_file.flush()
            shared.append_row(row)

    shared.finish(stop_reason)


def make_handler(shared):
    class DashboardHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(HTML.encode("utf-8"))
                return
            if path == "/metrics":
                payload = json.dumps(shared.snapshot()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)
                return
            self.send_response(404)
            self.end_headers()

    return DashboardHandler


def main():
    args = parse_args()
    run_name = args.run_name or time.strftime("dashboard-%Y%m%d-%H%M%S")
    out_dir = Path(args.out_dir) / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    shared = SharedState(out_dir / "round_metrics.csv", out_dir / "round_metrics.jsonl")

    worker = threading.Thread(target=explore, args=(shared, args), daemon=True)
    worker.start()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(shared))
    print(f"dashboard_url=http://127.0.0.1:{args.port}/", flush=True)
    print(f"metrics_csv={shared.csv_path}", flush=True)
    print(f"metrics_jsonl={shared.jsonl_path}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
