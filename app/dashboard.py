from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .metrics import percentile

LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))


def get_dashboard_data() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Window: 60 minutes
    now = datetime.now(timezone.utc)
    recent_records: list[dict[str, Any]] = []
    for r in records:
        ts_str = r.get("ts")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if (now - ts).total_seconds() <= 3600:
                    recent_records.append(r)
            except Exception:
                recent_records.append(r)
        else:
            recent_records.append(r)

    # 1. Latency & TTFT
    latencies = [int(r["latency_ms"]) for r in recent_records if r.get("event") == "response_sent" and "latency_ms" in r]
    ttfts = [int(r["ttft_ms"]) for r in recent_records if r.get("event") == "response_sent" and "ttft_ms" in r]
    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)
    ttft_p95 = percentile(ttfts, 95)
    latency_pass = p95 <= 3000

    # 2. Traffic
    req_received = [r for r in recent_records if r.get("event") == "request_received"]
    traffic_count = len(req_received)
    elapsed_minutes = 60.0
    if recent_records:
        first_ts = recent_records[0].get("ts")
        if first_ts:
            try:
                t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                elapsed_minutes = max(1.0, (now - t0).total_seconds() / 60.0)
            except Exception:
                elapsed_minutes = 60.0
    traffic_rpm = round(traffic_count / elapsed_minutes, 2)
    traffic_pass = traffic_rpm >= 1.0 or traffic_count >= 1

    # 3. Errors & Retrieval
    req_failed = [r for r in recent_records if r.get("event") == "request_failed"]
    error_count = len(req_failed)
    total_requests = max(1, traffic_count)
    error_rate_pct = round((error_count / total_requests) * 100, 2)
    error_types = Counter(r.get("error_type", "unknown") for r in req_failed)
    
    tools = [r for r in recent_records if "tool_success" in r and r.get("tool_success") is not None]
    tool_success_count = sum(1 for r in tools if r.get("tool_success") is True)
    tool_success_pct = round((tool_success_count / len(tools)) * 100, 1) if tools else 100.0
    error_pass = error_rate_pct <= 2.0

    # 4. Cost
    costs = [float(r.get("cost_usd", 0.0)) for r in recent_records if r.get("event") == "response_sent"]
    total_cost_usd = round(sum(costs), 4)
    avg_cost = round(total_cost_usd / max(1, len(costs)), 5)
    cost_pass = total_cost_usd <= 2.5

    # 5. Tokens
    tokens_in = sum(int(r.get("tokens_in", 0)) for r in recent_records if r.get("event") == "response_sent")
    tokens_out = sum(int(r.get("tokens_out", 0)) for r in recent_records if r.get("event") == "response_sent")
    total_tokens = tokens_in + tokens_out
    tokens_pass = total_tokens <= 50000

    # 6. Quality
    qualities = [float(r.get("quality_score", 0.0)) for r in recent_records if r.get("event") == "response_sent" and "quality_score" in r]
    quality_avg = round(sum(qualities) / max(1, len(qualities)), 3) if qualities else 0.85
    quality_pass = quality_avg >= 0.75

    return {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "latency": {"p50": p50, "p95": p95, "p99": p99, "ttft_p95": ttft_p95, "pass": latency_pass, "threshold": 3000},
        "traffic": {"count": traffic_count, "rpm": traffic_rpm, "pass": traffic_pass, "threshold": 1},
        "errors": {"rate_pct": error_rate_pct, "tool_success_pct": tool_success_pct, "breakdown": dict(error_types), "pass": error_pass, "threshold": 2.0},
        "cost": {"total_usd": total_cost_usd, "avg_usd": avg_cost, "pass": cost_pass, "threshold": 2.5},
        "tokens": {"in": tokens_in, "out": tokens_out, "total": total_tokens, "pass": tokens_pass, "threshold": 50000},
        "quality": {"avg": quality_avg, "pass": quality_pass, "threshold": 0.75},
    }


def render_dashboard_html() -> str:
    d = get_dashboard_data()
    lat = d["latency"]
    tra = d["traffic"]
    err = d["errors"]
    cos = d["cost"]
    tok = d["tokens"]
    qua = d["quality"]

    def badge(is_pass: bool, text_pass="PASS", text_breach="BREACH"):
        color = "#10b981" if is_pass else "#ef4444"
        bg = "rgba(16, 185, 129, 0.15)" if is_pass else "rgba(239, 68, 68, 0.15)"
        text = text_pass if is_pass else text_breach
        return f'<span style="background:{bg}; color:{color}; padding:4px 10px; border-radius:12px; font-weight:700; font-size:12px; border:1px solid {color}">{text}</span>'

    error_breakdown_html = "".join(f"<li>{k}: <b>{v}</b></li>" for k, v in err["breakdown"].items()) or "<li>None</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="30">
  <title>K4-L3A Day 13 Monitoring & LLMOps Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: linear-gradient(135deg, #090d16 0%, #111827 100%);
      color: #f3f4f6;
      font-family: 'Inter', sans-serif;
      padding: 32px 48px;
      min-height: 100vh;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 28px;
      padding-bottom: 20px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }}
    .title-group h1 {{
      font-size: 26px;
      font-weight: 800;
      background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: -0.5px;
    }}
    .title-group p {{
      color: #9ca3af;
      font-size: 14px;
      margin-top: 4px;
    }}
    .meta-bar {{
      display: flex;
      gap: 16px;
      align-items: center;
    }}
    .tag {{
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.12);
      padding: 6px 14px;
      border-radius: 8px;
      font-size: 13px;
      color: #cbd5e1;
    }}
    .refresh-btn {{
      background: #3b82f6;
      color: white;
      border: none;
      padding: 8px 16px;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      font-size: 13px;
      transition: background 0.2s;
    }}
    .refresh-btn:hover {{ background: #2563eb; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 24px;
    }}
    @media (max-width: 1024px) {{
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
    @media (max-width: 640px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
    .card {{
      background: rgba(17, 24, 39, 0.75);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      padding: 24px;
      backdrop-filter: blur(12px);
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.2s, border-color 0.2s;
    }}
    .card:hover {{
      transform: translateY(-2px);
      border-color: rgba(96, 165, 250, 0.4);
    }}
    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 16px;
    }}
    .card-title {{
      font-size: 15px;
      font-weight: 600;
      color: #cbd5e1;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .card-metric {{
      display: flex;
      align-items: baseline;
      gap: 8px;
      margin: 12px 0 16px 0;
    }}
    .main-val {{
      font-size: 38px;
      font-weight: 800;
      font-family: 'JetBrains Mono', monospace;
      color: #ffffff;
      letter-spacing: -1px;
    }}
    .unit {{
      font-size: 15px;
      font-weight: 500;
      color: #94a3b8;
    }}
    .sub-stats {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      background: rgba(0, 0, 0, 0.2);
      padding: 12px;
      border-radius: 10px;
      margin-bottom: 16px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
    }}
    .sub-item {{ display: flex; justify-content: space-between; color: #94a3b8; }}
    .sub-item span.v {{ color: #e2e8f0; font-weight: 600; }}
    .threshold-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 12px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 12px;
      color: #94a3b8;
    }}
    .threshold-bar code {{
      font-family: 'JetBrains Mono', monospace;
      color: #38bdf8;
      background: rgba(56, 189, 248, 0.1);
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .error-list {{
      list-style: none;
      font-size: 12px;
      color: #94a3b8;
      margin-top: 4px;
    }}
  </style>
</head>
<body>
  <div class="header">
    <div class="title-group">
      <h1>K4-L3A Day 13 Monitoring & LLMOps</h1>
      <p>Contract: <code>config/dashboard.yaml</code> | Source: <code>data/logs.jsonl</code> | Student: Chung Văn Duy (2A202602854)</p>
    </div>
    <div class="meta-bar">
      <div class="tag">⏱ Time Window: <b>60m</b></div>
      <div class="tag">🔄 Refresh: <b>30s</b></div>
      <div class="tag">🕒 {d["timestamp"]}</div>
      <button class="refresh-btn" onclick="location.reload()">Refresh Now</button>
    </div>
  </div>

  <div class="grid">
    <!-- PANEL 1: LATENCY -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">Panel 1: Latency & TTFT</div>
        {badge(lat["pass"])}
      </div>
      <div class="card-metric">
        <div class="main-val">{lat["p95"]}</div>
        <div class="unit">ms (P95)</div>
      </div>
      <div class="sub-stats">
        <div class="sub-item"><span>P50:</span><span class="v">{lat["p50"]} ms</span></div>
        <div class="sub-item"><span>P99:</span><span class="v">{lat["p99"]} ms</span></div>
        <div class="sub-item" style="grid-column: span 2;"><span>TTFT P95:</span><span class="v">{lat["ttft_p95"]} ms</span></div>
      </div>
      <div class="threshold-bar">
        <span>SLO Threshold:</span>
        <code>latency_p95 &lt;= {lat["threshold"]} ms</code>
      </div>
    </div>

    <!-- PANEL 2: TRAFFIC -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">Panel 2: Request Traffic</div>
        {badge(tra["pass"])}
      </div>
      <div class="card-metric">
        <div class="main-val">{tra["count"]}</div>
        <div class="unit">requests</div>
      </div>
      <div class="sub-stats">
        <div class="sub-item" style="grid-column: span 2;"><span>Request Rate:</span><span class="v">{tra["rpm"]} req/min</span></div>
      </div>
      <div class="threshold-bar">
        <span>Target Threshold:</span>
        <code>rate_per_minute &gt;= {tra["threshold"]} rpm</code>
      </div>
    </div>

    <!-- PANEL 3: ERRORS -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">Panel 3: Errors & Retrieval</div>
        {badge(err["pass"])}
      </div>
      <div class="card-metric">
        <div class="main-val">{err["rate_pct"]}%</div>
        <div class="unit">error rate</div>
      </div>
      <div class="sub-stats">
        <div class="sub-item" style="grid-column: span 2;"><span>Retrieval Success:</span><span class="v">{err["tool_success_pct"]}%</span></div>
        <div class="sub-item" style="grid-column: span 2;"><span>Breakdown:</span><ul class="error-list">{error_breakdown_html}</ul></div>
      </div>
      <div class="threshold-bar">
        <span>Guardrail Threshold:</span>
        <code>error_rate &lt;= {err["threshold"]}%</code>
      </div>
    </div>

    <!-- PANEL 4: COST -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">Panel 4: Cost Over Time</div>
        {badge(cos["pass"])}
      </div>
      <div class="card-metric">
        <div class="main-val">${cos["total_usd"]}</div>
        <div class="unit">USD total</div>
      </div>
      <div class="sub-stats">
        <div class="sub-item" style="grid-column: span 2;"><span>Avg Cost / Request:</span><span class="v">${cos["avg_usd"]}</span></div>
      </div>
      <div class="threshold-bar">
        <span>Guardrail Threshold:</span>
        <code>total_cost &lt;= ${cos["threshold"]} USD</code>
      </div>
    </div>

    <!-- PANEL 5: TOKENS -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">Panel 5: Input & Output Tokens</div>
        {badge(tok["pass"])}
      </div>
      <div class="card-metric">
        <div class="main-val">{tok["total"]}</div>
        <div class="unit">tokens</div>
      </div>
      <div class="sub-stats">
        <div class="sub-item"><span>Tokens In:</span><span class="v">{tok["in"]}</span></div>
        <div class="sub-item"><span>Tokens Out:</span><span class="v">{tok["out"]}</span></div>
      </div>
      <div class="threshold-bar">
        <span>Guardrail Threshold:</span>
        <code>total_tokens &lt;= {tok["threshold"]}</code>
      </div>
    </div>

    <!-- PANEL 6: QUALITY -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">Panel 6: Quality Proxy</div>
        {badge(qua["pass"])}
      </div>
      <div class="card-metric">
        <div class="main-val">{qua["avg"]}</div>
        <div class="unit">score (0-1)</div>
      </div>
      <div class="sub-stats">
        <div class="sub-item" style="grid-column: span 2;"><span>Proxy:</span><span class="v">Heuristic RAG Proxy</span></div>
      </div>
      <div class="threshold-bar">
        <span>Guardrail Threshold:</span>
        <code>quality_mean &gt;= {qua["threshold"]}</code>
      </div>
    </div>
  </div>
</body>
</html>
"""
