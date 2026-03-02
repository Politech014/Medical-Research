"""Generate RIS and BibTeX citation files from article data."""

import re


def generate_ris(articles: list[dict]) -> str:
    """Generate RIS format citations."""
    lines = []
    for a in articles:
        score = a.get("relevance_score") or 0
        if score < 40:
            continue

        source = a.get("source", "")
        if source == "clinicaltrials":
            lines.append("TY  - CTRIAL")
        elif a.get("article_type") == "review":
            lines.append("TY  - JOUR")
        else:
            lines.append("TY  - JOUR")

        if a.get("title"):
            lines.append(f"TI  - {a['title']}")

        if a.get("authors"):
            for author in a["authors"].split(","):
                author = author.strip()
                if author:
                    lines.append(f"AU  - {author}")

        if a.get("journal"):
            lines.append(f"JO  - {a['journal']}")

        if a.get("pub_date"):
            year = _extract_year(a["pub_date"])
            if year:
                lines.append(f"PY  - {year}")
            lines.append(f"DA  - {a['pub_date']}")

        if a.get("abstract"):
            lines.append(f"AB  - {a['abstract'][:3000]}")

        if a.get("url"):
            lines.append(f"UR  - {a['url']}")

        if a.get("external_id"):
            lines.append(f"ID  - {a['external_id']}")

        if a.get("ai_summary"):
            lines.append(f"N1  - AI Summary: {a['ai_summary']}")

        lines.append("ER  - ")
        lines.append("")

    return "\n".join(lines)


def generate_bibtex(articles: list[dict]) -> str:
    """Generate BibTeX format citations."""
    entries = []
    for i, a in enumerate(articles, 1):
        score = a.get("relevance_score") or 0
        if score < 40:
            continue

        key = _make_bibtex_key(a, i)
        entry_type = "article"
        if a.get("source") == "clinicaltrials":
            entry_type = "misc"

        fields = []

        if a.get("title"):
            fields.append(f"  title = {{{a['title']}}}")

        if a.get("authors"):
            fields.append(f"  author = {{{a['authors']}}}")

        if a.get("journal"):
            fields.append(f"  journal = {{{a['journal']}}}")

        if a.get("pub_date"):
            year = _extract_year(a["pub_date"])
            if year:
                fields.append(f"  year = {{{year}}}")

        if a.get("abstract"):
            clean = a["abstract"][:2000].replace("{", "\\{").replace("}", "\\}")
            fields.append(f"  abstract = {{{clean}}}")

        if a.get("url"):
            fields.append(f"  url = {{{a['url']}}}")

        if a.get("external_id"):
            fields.append(f"  note = {{ID: {a['external_id']}}}")

        entry = f"@{entry_type}{{{key},\n" + ",\n".join(fields) + "\n}"
        entries.append(entry)

    return "\n\n".join(entries) + "\n"


def _extract_year(date_str: str) -> str:
    match = re.search(r"(\d{4})", date_str or "")
    return match.group(1) if match else ""


def _make_bibtex_key(article: dict, index: int) -> str:
    authors = article.get("authors", "")
    first_author = authors.split(",")[0].strip().split()[-1] if authors else "unknown"
    first_author = re.sub(r"[^a-zA-Z]", "", first_author).lower()
    year = _extract_year(article.get("pub_date", ""))
    return f"{first_author}{year}_{index}" if year else f"{first_author}_{index}"
