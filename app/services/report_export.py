from datetime import datetime


def generate_html_report(search_data: dict, notes: dict | None = None) -> str:
    """Generate a self-contained HTML report for printing/PDF export."""
    notes = notes or {}
    articles = search_data.get("articles", [])
    query = search_data.get("original_query", "")
    created = search_data.get("created_at", "")
    search_id = search_data.get("id", "")
    synthesis = search_data.get("clinical_synthesis", "")

    relevant = [a for a in articles if (a.get("relevance_score") or 0) >= 40]
    relevant.sort(key=lambda a: a.get("relevance_score") or 0, reverse=True)

    total = len(articles)
    rel_count = len(relevant)
    avg_score = round(sum(a.get("relevance_score") or 0 for a in articles) / total) if total else 0

    # Source counts
    sources = {}
    for a in articles:
        s = a.get("source", "unknown")
        sources[s] = sources.get(s, 0) + 1

    # Eligibility counts
    elig_counts = {}
    for a in relevant:
        status = a.get("eligibility_status") or "unknown"
        elig_counts[status] = elig_counts.get(status, 0) + 1

    source_summary = ", ".join(f"{_source_label(k)}: {v}" for k, v in sources.items())

    # Clinical synthesis section
    synthesis_html = ""
    if synthesis:
        # Convert markdown headers to HTML
        synth_formatted = _esc(synthesis)
        synth_formatted = synth_formatted.replace("## ", "<h4>").replace("\n", "<br>")
        # Simple markdown-to-html for headers
        import re
        synth_formatted = re.sub(r"<h4>(.*?)<br>", r"<h4>\1</h4>", synth_formatted)
        synthesis_html = f"""
        <div class="synthesis">
            <h3>Clinical Synthesis</h3>
            <div class="synthesis-body">{synth_formatted}</div>
        </div>"""

    rows_html = ""
    for i, a in enumerate(relevant, 1):
        score = a.get("relevance_score") or 0
        score_class = "high" if score >= 75 else "mid" if score >= 50 else "low"
        elig = a.get("eligibility_status") or ""
        elig_badge = f'<span class="elig elig-{elig}">{elig.replace("_", " ").title()}</span>' if elig and elig != "unknown" else ""

        # Note for this article
        note_data = notes.get(a.get("id"))
        note_html = ""
        if note_data:
            status = note_data.get("status", "none")
            note_text = note_data.get("note_text", "")
            status_labels = {"important": "Important", "reviewed": "Reviewed", "dismissed": "Dismissed"}
            if status != "none":
                note_html += f'<span class="note-badge note-{status}">{status_labels.get(status, status)}</span>'
            if note_text:
                note_html += f'<div class="note-text"><strong>Note:</strong> {_esc(note_text)}</div>'

        rows_html += f"""
        <div class="article">
            <div class="article-head">
                <span class="score {score_class}">{score}</span>
                <div class="article-info">
                    <span class="src-badge src-{a.get('source','')}">{_source_label(a.get('source',''))}</span>
                    {f'<span class="type-badge">{_esc(a.get("article_type",""))}</span>' if a.get('article_type') else ''}
                    {f'<span class="ev-badge">L{a.get("evidence_level")}</span>' if a.get('evidence_level') else ''}
                    {f'<span class="ft-badge">Full Text</span>' if a.get('full_text') else ''}
                    {elig_badge}
                </div>
            </div>
            <h3 class="article-title">{_esc(a.get('title','Untitled'))}</h3>
            <p class="meta">{_esc(' · '.join(filter(None, [a.get('authors',''), a.get('journal',''), a.get('pub_date','')])))}</p>
            {f'<div class="summary">{_esc(a.get("ai_summary",""))}</div>' if a.get('ai_summary') else ''}
            {f'<div class="rationale"><strong>Rationale:</strong> {_esc(a.get("relevance_explanation",""))}</div>' if a.get('relevance_explanation') else ''}
            {f'<div class="elig-notes"><strong>Eligibility:</strong> {_esc(a.get("eligibility_notes",""))}</div>' if a.get('eligibility_notes') else ''}
            {note_html}
            {f'<p class="url">{_esc(a.get("url",""))}</p>' if a.get('url') else ''}
        </div>"""

    elig_section = ""
    if any(v for v in elig_counts.values()):
        elig_items = ", ".join(f"{k.replace('_',' ').title()}: {v}" for k, v in elig_counts.items() if k != "unknown")
        if elig_items:
            elig_section = f'<p><strong>Eligibility Summary:</strong> {elig_items}</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Medical Research Report — {_esc(query)}</title>
<style>
    @page {{ margin: 1.5cm; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; color: #1a1a1a; line-height: 1.6; font-size: 11pt; padding: 20px; max-width: 900px; margin: 0 auto; }}
    .header {{ border-bottom: 3px solid #2563eb; padding-bottom: 16px; margin-bottom: 24px; }}
    .header h1 {{ font-size: 20pt; color: #111; margin-bottom: 4px; }}
    .header .query {{ font-size: 14pt; color: #2563eb; font-weight: 600; margin-bottom: 8px; }}
    .header .meta {{ font-size: 9pt; color: #666; }}
    .stats {{ display: flex; gap: 24px; margin-bottom: 20px; padding: 12px 16px; background: #f0f4ff; border-radius: 8px; }}
    .stats .stat {{ text-align: center; }}
    .stats .stat-val {{ font-size: 18pt; font-weight: 800; color: #2563eb; }}
    .stats .stat-lbl {{ font-size: 8pt; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }}
    .synthesis {{ background: linear-gradient(135deg, #eff6ff, #f0f9ff); border: 1px solid #bfdbfe; border-radius: 8px; padding: 20px; margin-bottom: 20px; page-break-inside: avoid; }}
    .synthesis h3 {{ font-size: 13pt; color: #1e40af; margin-bottom: 12px; }}
    .synthesis h4 {{ font-size: 11pt; color: #1e3a5f; margin: 12px 0 4px; font-weight: 700; }}
    .synthesis-body {{ font-size: 10pt; color: #333; line-height: 1.7; }}
    .article {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 14px; page-break-inside: avoid; }}
    .article-head {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
    .score {{ display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 50%; color: #fff; font-weight: 800; font-size: 12pt; flex-shrink: 0; }}
    .score.high {{ background: #059669; }}
    .score.mid {{ background: #d97706; }}
    .score.low {{ background: #dc2626; }}
    .article-info {{ display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }}
    .src-badge, .type-badge, .ev-badge, .ft-badge, .elig, .note-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 8pt; font-weight: 700; text-transform: uppercase; }}
    .src-pubmed {{ background: #d1fae5; color: #065f46; }}
    .src-clinicaltrials {{ background: #fef3c7; color: #92400e; }}
    .src-europepmc {{ background: #dbeafe; color: #1e40af; }}
    .type-badge {{ background: #eff6ff; color: #2563eb; }}
    .ev-badge {{ background: #ede9fe; color: #5b21b6; }}
    .ft-badge {{ background: #dcfce7; color: #166534; }}
    .elig {{ font-size: 8pt; }}
    .elig-eligible {{ background: #d1fae5; color: #065f46; }}
    .elig-potentially_eligible {{ background: #fef3c7; color: #92400e; }}
    .elig-not_eligible {{ background: #fee2e2; color: #991b1b; }}
    .note-badge {{ margin-left: 6px; }}
    .note-important {{ background: #fef3c7; color: #92400e; }}
    .note-reviewed {{ background: #d1fae5; color: #065f46; }}
    .note-dismissed {{ background: #f3f4f6; color: #6b7280; }}
    .note-text {{ font-size: 9pt; color: #555; padding: 6px 12px; background: #fefce8; border-left: 3px solid #eab308; border-radius: 4px; margin-top: 6px; }}
    .article-title {{ font-size: 11pt; font-weight: 700; margin-bottom: 4px; color: #111; }}
    .meta {{ font-size: 9pt; color: #888; margin-bottom: 8px; }}
    .summary {{ font-size: 10pt; color: #333; padding: 8px 12px; background: #f0f7ff; border-left: 3px solid #2563eb; border-radius: 4px; margin-bottom: 8px; }}
    .rationale {{ font-size: 9pt; color: #555; padding: 6px 12px; background: #fffbeb; border-left: 3px solid #d97706; border-radius: 4px; margin-bottom: 6px; }}
    .elig-notes {{ font-size: 9pt; color: #555; padding: 6px 12px; background: #f0fdf4; border-left: 3px solid #059669; border-radius: 4px; margin-bottom: 6px; }}
    .url {{ font-size: 8pt; color: #2563eb; word-break: break-all; }}
    .footer {{ margin-top: 30px; padding-top: 12px; border-top: 1px solid #e5e7eb; font-size: 8pt; color: #999; text-align: center; }}
    @media print {{
        body {{ padding: 0; }}
        .article {{ break-inside: avoid; }}
        .synthesis {{ break-inside: avoid; }}
    }}
</style>
</head>
<body>
    <div class="header">
        <h1>Medical Research Report</h1>
        <div class="query">{_esc(query)}</div>
        <div class="meta">Search #{search_id} · Generated {_format_date(created)} · Printed {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
    </div>

    <div class="stats">
        <div class="stat"><div class="stat-val">{total}</div><div class="stat-lbl">Total Articles</div></div>
        <div class="stat"><div class="stat-val">{rel_count}</div><div class="stat-lbl">Relevant</div></div>
        <div class="stat"><div class="stat-val">{avg_score}</div><div class="stat-lbl">Avg Score</div></div>
    </div>

    <p style="font-size:9pt;color:#666;margin-bottom:6px;"><strong>Sources:</strong> {source_summary}</p>
    {elig_section}

    {synthesis_html}

    <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">

    {rows_html}

    <div class="footer">
        Medical Research App · AI-powered literature analysis · This report was generated automatically
    </div>
</body>
</html>"""

    return html


def _source_label(source: str) -> str:
    labels = {
        "pubmed": "PubMed",
        "clinicaltrials": "ClinicalTrials",
        "europepmc": "Europe PMC",
    }
    return labels.get(source, source)


def _esc(s: str) -> str:
    if not s:
        return ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _format_date(s: str) -> str:
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s
