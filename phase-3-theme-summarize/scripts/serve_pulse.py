#!/usr/bin/env python3
"""Serve the Phase 3 pulse output as an interactive local dashboard."""

from __future__ import annotations

import argparse
import json
import re
import webbrowser
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

THEME_KEYWORDS = {
    "KYC / Onboarding": r"\b(kyc|pan|aadhaar|verification|onboard|signup|register)\b",
    "Payments / UPI": r"\b(upi|payment|pay|transaction|transfer|failed|pending|refund)\b",
    "Withdrawals": r"\b(withdraw|withdrawal|payout|redeem)\b",
    "App stability": r"\b(crash|freeze|hang|not working|bug|glitch|error|slow)\b",
    "Customer support": r"\b(support|customer care|call|response|ticket|help)\b",
    "Trading / F&O": r"\b(option|f&o|trade|trading|order|margin|intraday|broker)\b",
    "Fees / charges": r"\b(charge|fee|brokerage|deduct|commission)\b",
}


def esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def review_text(review: dict) -> str:
    return f"{review.get('title', '')} {review.get('text', '')}".strip()


def compute_analytics(reviews: list[dict]) -> dict:
    if not reviews:
        return {}

    ratings = Counter(int(r["rating"]) for r in reviews)
    sources = Counter(r.get("source", "unknown") for r in reviews)
    total = len(reviews)
    low = sum(1 for r in reviews if int(r["rating"]) <= 2)
    high = sum(1 for r in reviews if int(r["rating"]) >= 4)
    avg_rating = sum(int(r["rating"]) for r in reviews) / total

    monthly: dict[str, int] = defaultdict(int)
    dates = []
    for review in reviews:
        date_str = str(review.get("date", ""))[:7]
        if date_str:
            monthly[date_str] += 1
        if review.get("date"):
            dates.append(str(review["date"]))

    keyword_hits: dict[str, int] = {}
    keyword_low: dict[str, int] = {}
    low_reviews = [r for r in reviews if int(r["rating"]) <= 2]
    for name, pattern in THEME_KEYWORDS.items():
        rx = re.compile(pattern, re.I)
        keyword_hits[name] = sum(1 for r in reviews if rx.search(review_text(r)))
        keyword_low[name] = sum(1 for r in low_reviews if rx.search(review_text(r)))

    return {
        "rating_distribution": {str(k): ratings[k] for k in sorted(ratings)},
        "source_split": dict(sources),
        "avg_rating": round(avg_rating, 2),
        "low_pct": round(100 * low / total, 1),
        "high_pct": round(100 * high / total, 1),
        "low_count": low,
        "high_count": high,
        "date_range": [min(dates), max(dates)] if dates else [],
        "monthly_volume": dict(sorted(monthly.items())[-8:]),
        "keyword_hits": keyword_hits,
        "keyword_low_rated": keyword_low,
    }


def build_dashboard_payload(raw: dict) -> dict:
    upstream = raw.get("upstream_report", {})
    ingest = upstream.get("upstream_report", upstream if "final_count" in upstream else {})
    redaction = upstream.get("redaction_report", {})

    payload = {
        "themed_corpus": raw.get("themed_corpus", {}),
        "groq_report": raw.get("groq_report", {}),
        "pulse": raw.get("pulse", raw),
        "pipeline": {
            "ingest": ingest,
            "redaction": redaction,
        },
    }

    reviews = upstream.get("reviews")
    if isinstance(reviews, list) and reviews:
        payload["analytics"] = compute_analytics(reviews)

    return payload


def load_payload(pulse_path: Path) -> dict:
    slim_path = pulse_path.with_name("pulse_dashboard.json")

    if pulse_path.name == "pulse_dashboard.json" and pulse_path.is_file():
        return json.loads(pulse_path.read_text(encoding="utf-8"))

    if slim_path.is_file() and slim_path.stat().st_mtime >= pulse_path.stat().st_mtime:
        data = json.loads(slim_path.read_text(encoding="utf-8"))
        if data.get("analytics"):
            return data

    raw = json.loads(pulse_path.read_text(encoding="utf-8"))
    payload = build_dashboard_payload(raw)
    slim_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def bar_rows(items: list[tuple[str, float, str]], max_value: float) -> str:
    rows = ""
    for label, value, detail in items:
        width = 0 if max_value <= 0 else min(100, round(100 * value / max_value))
        rows += f"""
        <div class="bar-row">
          <div class="bar-label"><span>{esc(label)}</span><span class="bar-val">{esc(detail)}</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
        </div>"""
    return rows


def cluster_lookup(clusters: list[dict]) -> dict[int, dict]:
    return {int(c["cluster_id"]): c for c in clusters}


def derive_recommendations(
    pulse: dict,
    clusters: list[dict],
    analytics: dict,
    groq: dict,
) -> list[dict]:
    recs: list[dict] = []
    priority = 1

    for action in pulse.get("action_ideas", []):
        recs.append({
            "priority": priority,
            "type": "groq",
            "title": "Action from pulse",
            "body": action,
        })
        priority += 1

    by_rank = sorted(clusters, key=lambda c: c.get("rank", 99))
    for cluster in by_rank[:3]:
        severity = float(cluster.get("severity", 0))
        if severity >= 0.5:
            recs.append({
                "priority": priority,
                "type": "urgent",
                "title": f"High-severity cluster #{cluster.get('cluster_id')}",
                "body": (
                    f"{cluster.get('size', 0):,} reviews · avg {cluster.get('avg_rating', 0):.1f}★ · "
                    f"{severity * 100:.0f}% are 1–2★. Prioritize engineering + support playbooks for this bucket."
                ),
            })
            priority += 1

    if analytics.get("keyword_low_rated"):
        top_kw = max(analytics["keyword_low_rated"].items(), key=lambda x: x[1])
        if top_kw[1] > 0:
            recs.append({
                "priority": priority,
                "type": "signal",
                "title": "Strongest keyword signal (1–2★ reviews)",
                "body": f"“{top_kw[0]}” appears in {top_kw[1]:,} low-rated reviews — align sprint goals with this pain area.",
            })
            priority += 1

    if analytics.get("low_pct", 0) >= 35:
        recs.append({
            "priority": priority,
            "type": "signal",
            "title": "Negative sentiment volume",
            "body": (
                f"{analytics.get('low_pct', 0)}% of reviews are 1–2★ ({analytics.get('low_count', 0):,} reviews). "
                "Consider a dedicated reliability/support OKR this quarter."
            ),
        })
        priority += 1

    tokens = groq.get("tokens_estimated", pulse.get("meta", {}).get("groq_tokens_estimated", 0))
    max_tokens = groq.get("max_tokens", 6000)
    if tokens and max_tokens:
        recs.append({
            "priority": priority,
            "type": "ops",
            "title": "Groq budget headroom",
            "body": f"Last run used ~{tokens:,} / {max_tokens:,} estimated tokens ({round(100 * tokens / max_tokens)}%). Safe for weekly runs on free tier.",
        })

    return recs[:8]


def render_html(payload: dict) -> str:
    pulse = payload.get("pulse", payload)
    corpus = payload.get("themed_corpus", {})
    groq = payload.get("groq_report", {})
    analytics = payload.get("analytics", {})
    pipeline = payload.get("pipeline", {})
    meta = pulse.get("meta", {})
    themes = pulse.get("top_themes", [])
    quotes = pulse.get("quotes", [])
    actions = pulse.get("action_ideas", [])
    clusters = corpus.get("themes", [])
    lookup = cluster_lookup(clusters)
    top_ids = set(corpus.get("top_theme_ids", []))

    recommendations = derive_recommendations(pulse, clusters, analytics, groq)

    # Map pulse themes to cluster stats (by rank order vs top_theme_ids)
    theme_cards = ""
    for index, theme in enumerate(themes, start=1):
        quote = quotes[index - 1] if index - 1 < len(quotes) else {}
        action = actions[index - 1] if index - 1 < len(actions) else ""
        cluster_id = corpus.get("top_theme_ids", [None] * 3)[index - 1] if index - 1 < len(corpus.get("top_theme_ids", [])) else None
        cluster = lookup.get(int(cluster_id)) if cluster_id is not None else {}
        size = cluster.get("size", 0)
        avg = cluster.get("avg_rating", 0)
        sev = float(cluster.get("severity", 0)) * 100
        share = round(100 * size / corpus.get("total_reviews", 1), 1) if size else 0

        theme_cards += f"""
        <article class="card theme-card" data-cluster="{esc(cluster_id)}">
          <div class="theme-head">
            <span class="badge">Theme {index}</span>
            <h2>{esc(theme.get("name", ""))}</h2>
          </div>
          <div class="chips">
            <span class="chip">{size:,} reviews ({share}%)</span>
            <span class="chip">avg {avg:.1f}★</span>
            <span class="chip {'chip-warn' if sev >= 50 else ''}">{sev:.0f}% severity</span>
            <span class="chip">cluster {esc(cluster_id)}</span>
          </div>
          <p class="summary">{esc(theme.get("one_line_summary", ""))}</p>
          <blockquote id="quote-{index}">{esc(quote.get("text", ""))}</blockquote>
          <div class="quote-actions">
            <button type="button" class="btn" onclick="copyText('quote-{index}')">Copy quote</button>
            <span class="meta-line">ID: <code>{esc(quote.get("review_id", ""))}</code></span>
          </div>
          <div class="action">
            <strong>Recommended action</strong>
            <p>{esc(action)}</p>
          </div>
        </article>"""

    cluster_rows = ""
    max_cluster_size = max((c.get("size", 0) for c in clusters), default=1)
    for cluster in sorted(clusters, key=lambda item: item.get("rank", 99)):
        cid = cluster.get("cluster_id")
        in_pulse = "yes" if cid in top_ids else "—"
        size = cluster.get("size", 0)
        cluster_rows += f"""
        <tr class="cluster-row" data-cluster="{esc(cid)}" onclick="highlightCluster({esc(cid)})">
          <td>{esc(cluster.get("rank", ""))}</td>
          <td><strong>{esc(cid)}</strong></td>
          <td>
            <div class="inline-bar"><div style="width:{round(100 * size / max_cluster_size)}%"></div></div>
            {size:,}
          </td>
          <td>{esc(cluster.get("avg_rating", ""))}</td>
          <td><span class="sev-pill" data-sev="{float(cluster.get('severity', 0))}">{round(float(cluster.get("severity", 0)) * 100, 1)}%</span></td>
          <td>{esc(round(cluster.get("rank_score", 0), 0))}</td>
          <td>{in_pulse}</td>
        </tr>"""

    # Rating bars
    rating_bars = ""
    rating_dist = analytics.get("rating_distribution", {})
    if rating_dist:
        max_r = max(int(v) for v in rating_dist.values())
        items = [(f"{star}★", int(rating_dist[str(star)]), f"{int(rating_dist[str(star)]):,}") for star in range(1, 6) if str(star) in rating_dist]
        rating_bars = bar_rows(items, max_r)

    keyword_bars = ""
    kw_low = analytics.get("keyword_low_rated", {})
    if kw_low:
        top_kw = sorted(kw_low.items(), key=lambda x: x[1], reverse=True)[:7]
        max_kw = max(v for _, v in top_kw) if top_kw else 1
        keyword_bars = bar_rows([(k, v, f"{v:,} hits") for k, v in top_kw], max_kw)

    cluster_size_bars = ""
    if clusters:
        sorted_c = sorted(clusters, key=lambda c: c.get("size", 0), reverse=True)
        max_s = sorted_c[0].get("size", 1)
        cluster_size_bars = bar_rows(
            [(f"Cluster {c['cluster_id']}", c["size"], f"{c['size']:,} · {c.get('avg_rating', 0):.1f}★") for c in sorted_c],
            max_s,
        )

    monthly_bars = ""
    monthly = analytics.get("monthly_volume", {})
    if monthly:
        max_m = max(monthly.values())
        monthly_bars = bar_rows([(k, v, f"{v:,}") for k, v in monthly.items()], max_m)

    rec_cards = ""
    for rec in recommendations:
        rec_cards += f"""
        <div class="rec-card rec-{esc(rec['type'])}">
          <span class="rec-priority">#{rec['priority']}</span>
          <h3>{esc(rec['title'])}</h3>
          <p>{esc(rec['body'])}</p>
        </div>"""

    ingest = pipeline.get("ingest", {})
    redaction = pipeline.get("redaction", {})
    source_split = meta.get("source_split", analytics.get("source_split", {}))
    play_n = source_split.get("play_store", 0)
    app_n = source_split.get("app_store", 0)
    total_reviews = meta.get("review_count", corpus.get("total_reviews", 0))
    groq_calls = groq.get("calls_made", meta.get("groq_calls", 0))
    groq_tokens = groq.get("tokens_estimated", meta.get("groq_tokens_estimated", 0))
    groq_max = groq.get("max_tokens", 6000)
    token_pct = min(100, round(100 * groq_tokens / groq_max)) if groq_max else 0

    funnel = ""
    if ingest:
        funnel_items = [
            ("Fetched (raw)", ingest.get("total_rows", 0)),
            ("After filters", ingest.get("final_count", total_reviews)),
            ("PII scrubbed", redaction.get("reviews_processed", total_reviews)),
            ("Clustered", corpus.get("total_reviews", total_reviews)),
        ]
        max_f = max(v for _, v in funnel_items if v)
        funnel = bar_rows([(label, val, f"{val:,}") for label, val in funnel_items], max_f)

    # Accumulation banner: corpus total + reviews added by this weekly run.
    accum_banner = ""
    if "added_this_week" in ingest:
        corpus_total = ingest.get("corpus_total", ingest.get("final_count", 0))
        added = ingest.get("added_this_week", 0)
        weeks = ingest.get("weeks_accumulated", 1)
        last_updated = str(ingest.get("last_updated", ""))[:10]
        prev_total = ingest.get("previous_total", 0)
        pill = "background:#1f2937;border:1px solid #334155;border-radius:999px;padding:4px 12px;font-size:0.85rem"
        new_pill = "background:#4ade8022;color:#4ade80;border:1px solid #4ade8055;border-radius:999px;padding:4px 12px;font-size:0.85rem;font-weight:600"
        accum_banner = f"""
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;align-items:center">
        <span style="{pill}">Corpus total: <strong>{corpus_total:,}</strong> reviews</span>
        <span style="{new_pill}">+{added:,} new this run</span>
        <span style="{pill}">Run #{weeks} · {prev_total:,} &rarr; {corpus_total:,}</span>
        <span style="{pill}">Updated {esc(last_updated)}</span>
      </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Groww Weekly Review Pulse</title>
  <style>
    :root {{
      --bg: #0f1419;
      --panel: #1a2332;
      --panel-2: #243044;
      --text: #f1f5f9;
      --muted: #94a3b8;
      --line: #334155;
      --accent: #2dd4bf;
      --accent-dim: #0d9488;
      --warn: #fbbf24;
      --danger: #f87171;
      --ok: #4ade80;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 24px 20px 56px; }}
    header {{
      background: linear-gradient(135deg, #1a2332 0%, #0f766e22 100%);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 28px 32px;
      margin-bottom: 20px;
    }}
    header h1 {{ margin: 0 0 6px; font-size: 1.85rem; letter-spacing: -0.02em; }}
    header p {{ margin: 0; color: var(--muted); font-size: 0.95rem; }}
    .tabs {{
      display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px;
    }}
    .tab {{
      background: var(--panel);
      border: 1px solid var(--line);
      color: var(--muted);
      padding: 10px 18px;
      border-radius: 999px;
      cursor: pointer;
      font-size: 0.88rem;
      font-weight: 600;
      transition: all 0.15s;
    }}
    .tab:hover {{ border-color: var(--accent); color: var(--text); }}
    .tab.active {{ background: var(--accent-dim); border-color: var(--accent); color: #fff; }}
    .panel {{ display: none; }}
    .panel.active {{ display: block; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 16px;
    }}
    .stat label {{
      display: block; font-size: 0.72rem; text-transform: uppercase;
      letter-spacing: 0.06em; color: var(--muted); margin-bottom: 4px;
    }}
    .stat strong {{ font-size: 1.4rem; }}
    .stat small {{ display: block; color: var(--muted); font-size: 0.8rem; margin-top: 2px; }}
    .grid-2 {{ display: grid; gap: 16px; }}
    @media (min-width: 900px) {{ .grid-2 {{ grid-template-columns: 1fr 1fr; }} }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 20px 22px;
      margin-bottom: 16px;
    }}
    .card h2 {{ margin: 0 0 14px; font-size: 1.1rem; }}
    .theme-card {{ transition: border-color 0.2s, box-shadow 0.2s; }}
    .theme-card.highlight {{ border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }}
    .theme-head {{ display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }}
    .badge {{
      background: #0d948833; color: var(--accent);
      font-size: 0.7rem; font-weight: 700; padding: 4px 10px;
      border-radius: 999px; text-transform: uppercase;
    }}
    .theme-card h2 {{ margin: 0; font-size: 1.25rem; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }}
    .chip {{
      font-size: 0.78rem; padding: 4px 10px; border-radius: 6px;
      background: var(--panel-2); color: var(--muted);
    }}
    .chip-warn {{ background: #fbbf2422; color: var(--warn); }}
    .summary {{ margin: 0 0 12px; color: #cbd5e1; }}
    blockquote {{
      margin: 0 0 10px; padding: 14px 16px;
      border-left: 3px solid var(--accent);
      background: var(--panel-2);
      border-radius: 0 8px 8px 0;
      font-style: italic; color: #e2e8f0; font-size: 0.95rem;
    }}
    .quote-actions {{ display: flex; align-items: center; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }}
    .meta-line {{ font-size: 0.82rem; color: var(--muted); }}
    code {{ font-family: ui-monospace, monospace; font-size: 0.8rem; }}
    .btn {{
      background: var(--panel-2); border: 1px solid var(--line);
      color: var(--text); padding: 6px 12px; border-radius: 8px;
      cursor: pointer; font-size: 0.8rem;
    }}
    .btn:hover {{ border-color: var(--accent); }}
    .action {{ border-top: 1px solid var(--line); padding-top: 12px; }}
    .action strong {{ color: var(--accent); font-size: 0.85rem; }}
    .bar-row {{ margin-bottom: 10px; }}
    .bar-label {{ display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 4px; }}
    .bar-val {{ color: var(--muted); }}
    .bar-track {{ height: 8px; background: var(--panel-2); border-radius: 4px; overflow: hidden; }}
    .bar-fill {{ height: 100%; background: linear-gradient(90deg, var(--accent-dim), var(--accent)); border-radius: 4px; transition: width 0.4s; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); }}
    th {{ color: var(--muted); font-size: 0.72rem; text-transform: uppercase; }}
    .cluster-row {{ cursor: pointer; transition: background 0.15s; }}
    .cluster-row:hover {{ background: var(--panel-2); }}
    .cluster-row.active {{ background: #0d948822; }}
    .inline-bar {{ height: 4px; background: var(--panel-2); border-radius: 2px; margin-bottom: 4px; max-width: 80px; }}
    .inline-bar div {{ height: 100%; background: var(--accent); border-radius: 2px; }}
    .sev-pill {{ padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }}
    .gauge {{ height: 10px; background: var(--panel-2); border-radius: 5px; overflow: hidden; margin-top: 8px; }}
    .gauge-fill {{ height: 100%; background: var(--ok); border-radius: 5px; }}
    .rec-grid {{ display: grid; gap: 12px; }}
    @media (min-width: 768px) {{ .rec-grid {{ grid-template-columns: 1fr 1fr; }} }}
    .rec-card {{
      background: var(--panel-2); border: 1px solid var(--line);
      border-radius: 12px; padding: 16px; position: relative;
    }}
    .rec-groq {{ border-left: 3px solid var(--accent); }}
    .rec-urgent {{ border-left: 3px solid var(--danger); }}
    .rec-signal {{ border-left: 3px solid var(--warn); }}
    .rec-ops {{ border-left: 3px solid var(--ok); }}
    .rec-priority {{ position: absolute; top: 12px; right: 12px; font-size: 0.75rem; color: var(--muted); }}
    .rec-card h3 {{ margin: 0 0 8px; font-size: 0.95rem; }}
    .rec-card p {{ margin: 0; font-size: 0.88rem; color: #cbd5e1; }}
    .footer {{ margin-top: 24px; color: var(--muted); font-size: 0.85rem; }}
    .split-bar {{ display: flex; height: 12px; border-radius: 6px; overflow: hidden; margin: 10px 0; }}
    .split-play {{ background: var(--accent); }}
    .split-app {{ background: #6366f1; }}
    .legend {{ display: flex; gap: 16px; font-size: 0.82rem; color: var(--muted); }}
    .legend span::before {{
      content: ''; display: inline-block; width: 10px; height: 10px;
      border-radius: 2px; margin-right: 6px; vertical-align: middle;
    }}
    .legend .lp::before {{ background: var(--accent); }}
    .legend .la::before {{ background: #6366f1; }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Groww Weekly Review Pulse</h1>
      <p>Week of {esc(pulse.get("week_of", ""))} · {total_reviews:,} reviews · {esc(corpus.get("embedding_model", ""))}</p>{accum_banner}
    </header>

    <nav class="tabs" role="tablist">
      <button class="tab active" data-tab="overview" type="button">Overview</button>
      <button class="tab" data-tab="themes" type="button">Themes &amp; quotes</button>
      <button class="tab" data-tab="clusters" type="button">Clusters</button>
      <button class="tab" data-tab="analytics" type="button">Analytics</button>
      <button class="tab" data-tab="recommendations" type="button">Recommendations</button>
      <button class="tab" data-tab="pipeline" type="button">Pipeline</button>
    </nav>

    <section id="overview" class="panel active">
      <div class="stats">
        <div class="stat"><label>Reviews</label><strong>{total_reviews:,}</strong><small>scrubbed corpus</small></div>
        <div class="stat"><label>Avg rating</label><strong>{analytics.get("avg_rating", "—")}</strong><small>all reviews</small></div>
        <div class="stat"><label>Low 1–2★</label><strong>{analytics.get("low_pct", "—")}%</strong><small>{analytics.get("low_count", 0):,} reviews</small></div>
        <div class="stat"><label>High 4–5★</label><strong>{analytics.get("high_pct", "—")}%</strong><small>{analytics.get("high_count", 0):,} reviews</small></div>
        <div class="stat"><label>Pulse words</label><strong>{pulse.get("word_count", 0)}</strong><small>of 250 max</small></div>
        <div class="stat"><label>Groq</label><strong>{groq_calls} call(s)</strong><small>{groq_tokens:,} tokens est.</small></div>
      </div>

      <div class="grid-2">
        <div class="card">
          <h2>Store split</h2>
          <div class="split-bar">
            <div class="split-play" style="width:{round(100 * play_n / total_reviews) if total_reviews else 0}%"></div>
            <div class="split-app" style="width:{round(100 * app_n / total_reviews) if total_reviews else 0}%"></div>
          </div>
          <div class="legend">
            <span class="lp">Play Store {play_n:,} ({round(100 * play_n / total_reviews, 1) if total_reviews else 0}%)</span>
            <span class="la">App Store {app_n:,} ({round(100 * app_n / total_reviews, 1) if total_reviews else 0}%)</span>
          </div>
        </div>
        <div class="card">
          <h2>Groq token budget</h2>
          <p style="margin:0;color:var(--muted);font-size:0.88rem">{groq_tokens:,} / {groq_max:,} tokens · {esc(groq.get("model", "n/a"))}</p>
          <div class="gauge"><div class="gauge-fill" style="width:{token_pct}%"></div></div>
          <p style="margin:8px 0 0;font-size:0.82rem;color:var(--muted)">Validation: {"pass" if groq.get("validation_ok", True) else "check logs"} · Dry run: {esc(groq.get("dry_run", meta.get("dry_run", False)))}</p>
        </div>
      </div>

      <div class="card">
        <h2>Cluster volume (all {len(clusters)} themes)</h2>
        {cluster_size_bars or "<p style='color:var(--muted)'>No cluster data.</p>"}
      </div>
    </section>

    <section id="themes" class="panel">
      <div class="grid" style="display:grid;gap:16px">{theme_cards}</div>
    </section>

    <section id="clusters" class="panel">
      <div class="card">
        <h2>Cluster ranking · click a row to highlight matching theme</h2>
        <p style="margin:-8px 0 14px;color:var(--muted);font-size:0.88rem">Ranked by size × (1 + severity). Top 3 feed the weekly pulse.</p>
        <table>
          <thead>
            <tr><th>Rank</th><th>ID</th><th>Size</th><th>Avg ★</th><th>Severity</th><th>Score</th><th>In pulse</th></tr>
          </thead>
          <tbody>{cluster_rows}</tbody>
        </table>
      </div>
    </section>

    <section id="analytics" class="panel">
      <div class="grid-2">
        <div class="card">
          <h2>Rating distribution</h2>
          {rating_bars or "<p style='color:var(--muted)'>Re-run with full pulse.json to compute analytics.</p>"}
        </div>
        <div class="card">
          <h2>Keyword signals (1–2★ reviews)</h2>
          {keyword_bars or "<p style='color:var(--muted)'>No keyword analytics.</p>"}
        </div>
      </div>
      <div class="card">
        <h2>Monthly review volume (recent)</h2>
        {monthly_bars or "<p style='color:var(--muted)'>No date data.</p>"}
        {"<p style='margin:12px 0 0;font-size:0.85rem;color:var(--muted)'>Date range: " + esc(" → ".join(analytics.get("date_range", []))) + "</p>" if analytics.get("date_range") else ""}
      </div>
    </section>

    <section id="recommendations" class="panel">
      <div class="card">
        <h2>Prioritized recommendations</h2>
        <p style="margin:-8px 0 16px;color:var(--muted);font-size:0.88rem">Combines Groq action ideas with data-driven signals from clusters and low-rated keyword analysis.</p>
        <div class="rec-grid">{rec_cards}</div>
      </div>
    </section>

    <section id="pipeline" class="panel">
      <div class="grid-2">
        <div class="card">
          <h2>Ingestion funnel</h2>
          {funnel or "<p style='color:var(--muted)'>Pipeline stats unavailable in slim export.</p>"}
        </div>
        <div class="card">
          <h2>PII redaction (Phase 2)</h2>
          <div class="stats" style="margin:0">
            <div class="stat"><label>Reviews</label><strong>{redaction.get("reviews_processed", "—")}</strong></div>
            <div class="stat"><label>Fields scrubbed</label><strong>{redaction.get("fields_scrubbed", "—")}</strong></div>
            <div class="stat"><label>Redactions</label><strong>{redaction.get("total_redactions", "—")}</strong></div>
          </div>
          {"<p style='margin-top:12px;font-size:0.85rem;color:var(--muted)'>Filtered out: " + f"{ingest.get('skipped_too_short', 0):,} too short · {ingest.get('skipped_has_emoji', 0):,} emoji · {ingest.get('skipped_non_english', 0):,} non-English</p>" if ingest else ""}
        </div>
      </div>
    </section>

    <p class="footer">Generated {esc(meta.get("generated_at", ""))} · Cluster k={corpus.get("cluster_k", 5)} · Top theme IDs {esc(corpus.get("top_theme_ids", []))}</p>
  </div>

  <script>
    document.querySelectorAll('.tab').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
      }});
    }});

    function highlightCluster(id) {{
      document.querySelectorAll('.cluster-row').forEach(r => r.classList.remove('active'));
      document.querySelectorAll('.theme-card').forEach(c => c.classList.remove('highlight'));
      const row = document.querySelector('.cluster-row[data-cluster="' + id + '"]');
      if (row) row.classList.add('active');
      const card = document.querySelector('.theme-card[data-cluster="' + id + '"]');
      if (card) {{
        card.classList.add('highlight');
        document.querySelector('[data-tab="themes"]').click();
        card.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      }}
    }}

    function copyText(id) {{
      const el = document.getElementById(id);
      if (!el) return;
      navigator.clipboard.writeText(el.innerText).then(() => {{
        const btn = event.target;
        const orig = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = orig, 1500);
      }});
    }}

    document.querySelectorAll('.sev-pill').forEach(pill => {{
      const sev = parseFloat(pill.dataset.sev);
      if (sev >= 0.6) pill.style.background = '#f8717122', pill.style.color = '#f87171';
      else if (sev >= 0.35) pill.style.background = '#fbbf2422', pill.style.color = '#fbbf24';
      else pill.style.background = '#4ade8022', pill.style.color = '#4ade80';
    }});
  </script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="View Phase 3 pulse output on localhost.")
    parser.add_argument("--pulse", type=Path, default=Path("data/output/pulse.json"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Rebuild dashboard JSON from pulse.json")
    parser.add_argument(
        "--export",
        type=Path,
        help="Write a static dashboard HTML file and exit (for Vercel / GitHub Pages).",
    )
    args = parser.parse_args()

    if not args.pulse.is_file():
        raise SystemExit(f"Pulse file not found: {args.pulse}. Run Phase 3 first.")

    slim_path = args.pulse.with_name("pulse_dashboard.json")
    if args.refresh and slim_path.is_file():
        slim_path.unlink()

    source = args.pulse
    if args.pulse.name == "pulse_dashboard.json":
        source = args.pulse.parent / "pulse.json"
        if not source.is_file():
            source = args.pulse

    if args.export is not None:
        read_path = source if source.is_file() else args.pulse
        payload = load_payload(read_path)
        html = render_html(payload)
        args.export.parent.mkdir(parents=True, exist_ok=True)
        args.export.write_text(html, encoding="utf-8")
        print(f"Exported static dashboard to {args.export.resolve()}")
        return

    # Live reload: re-render whenever the pulse file changes on disk, so the
    # dashboard reflects the latest weekly run without a manual restart.
    cache: dict[str, object] = {"mtime": None, "html": b""}

    def current_html() -> bytes:
        read_path = source if source.is_file() else args.pulse
        try:
            mtime = read_path.stat().st_mtime
        except OSError:
            mtime = None
        if mtime != cache["mtime"] or not cache["html"]:
            payload = load_payload(read_path)
            cache["html"] = render_html(payload).encode("utf-8")
            cache["mtime"] = mtime
        return cache["html"]  # type: ignore[return-value]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path not in ("/", "/index.html"):
                self.send_response(404)
                self.end_headers()
                return
            html = current_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Serving pulse dashboard at {url}")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
