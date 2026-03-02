import asyncio
import xml.etree.ElementTree as ET
import httpx
import logging

logger = logging.getLogger("medical")

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
MAX_FULL_TEXT_CHARS = 8000


async def search_europepmc(query: str, max_results: int = 20) -> list[dict]:
    """Search Europe PMC and return articles with optional full text."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/search",
            params={
                "query": query,
                "resultType": "core",
                "pageSize": max_results,
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("resultList", {}).get("result", [])
    articles = []

    for r in results:
        pmid = r.get("pmid", "")
        pmcid = r.get("pmcid", "")
        ext_id = pmid or pmcid or r.get("id", "")

        article = {
            "source": "europepmc",
            "external_id": ext_id,
            "pmid": pmid,
            "title": r.get("title", ""),
            "abstract": r.get("abstractText", ""),
            "authors": _format_authors(r.get("authorList", {}).get("author", [])),
            "journal": r.get("journalTitle", ""),
            "pub_date": r.get("firstPublicationDate", ""),
            "url": f"https://europepmc.org/article/MED/{pmid}" if pmid else f"https://europepmc.org/article/PMC/{pmcid}" if pmcid else "",
            "raw_data": {"pmid": pmid, "pmcid": pmcid},
            "has_full_text": r.get("isOpenAccess", "N") == "Y" or r.get("inEPMC", "N") == "Y",
            "full_text": None,
        }
        articles.append(article)

    # Fetch full text for open access articles (limit to first 5 to avoid slowness)
    full_text_candidates = [a for a in articles if a["has_full_text"] and a["raw_data"].get("pmcid")]
    async with httpx.AsyncClient(timeout=30) as client:
        tasks = [_fetch_full_text(client, a["raw_data"]["pmcid"]) for a in full_text_candidates[:5]]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for article, result in zip(full_text_candidates[:5], results):
                if isinstance(result, Exception):
                    logger.debug(f"Full text fetch failed for {article['raw_data']['pmcid']}: {result}")
                    continue
                if result:
                    article["full_text"] = result

    return articles


async def search_europepmc_sequential(queries: list[str], max_results: int = 20) -> list[list[dict]]:
    """Run multiple Europe PMC queries sequentially."""
    all_results = []
    for i, query in enumerate(queries):
        if i > 0:
            await asyncio.sleep(0.5)
        try:
            articles = await search_europepmc(query, max_results)
            all_results.append(articles)
        except Exception as e:
            all_results.append(e)
    return all_results


async def _fetch_full_text(client: httpx.AsyncClient, pmcid: str) -> str | None:
    """Fetch full text XML from Europe PMC and extract plain text, truncated."""
    try:
        resp = await client.get(
            f"{BASE_URL}/{pmcid}/fullTextXML",
            timeout=15,
        )
        if resp.status_code != 200:
            return None

        text = _extract_text_from_xml(resp.text)
        if text and len(text) > MAX_FULL_TEXT_CHARS:
            text = text[:MAX_FULL_TEXT_CHARS] + "... [truncated]"
        return text if text else None
    except Exception:
        return None


def _extract_text_from_xml(xml_text: str) -> str:
    """Extract readable text from Europe PMC full-text XML."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""

    sections = []

    # Try body sections
    for sec in root.findall(".//sec"):
        title_elem = sec.find("title")
        title = title_elem.text if title_elem is not None and title_elem.text else ""
        paragraphs = []
        for p in sec.findall("p"):
            text = _get_all_text(p)
            if text:
                paragraphs.append(text)
        if title or paragraphs:
            if title:
                sections.append(f"\n## {title}\n")
            sections.extend(paragraphs)

    # Fallback: just get all <p> tags
    if not sections:
        for p in root.findall(".//p"):
            text = _get_all_text(p)
            if text:
                sections.append(text)

    return "\n".join(sections)


def _get_all_text(elem) -> str:
    """Recursively get all text from an XML element."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(_get_all_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def _format_authors(authors: list[dict]) -> str:
    names = []
    for a in authors[:5]:
        full = a.get("fullName", "")
        if full:
            names.append(full)
        else:
            last = a.get("lastName", "")
            first = a.get("firstName", "")
            if last:
                names.append(f"{last} {first}".strip())
    return ", ".join(names)
