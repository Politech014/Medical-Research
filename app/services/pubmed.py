import asyncio
import xml.etree.ElementTree as ET
import httpx

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MAX_RETRIES = 3


async def search_pubmed(query: str, max_results: int = 20, client: httpx.AsyncClient | None = None) -> list[dict]:
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=30)

    try:
        # Step 1: search for PMIDs
        search_resp = await _request_with_retry(
            client, f"{BASE_URL}/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmode": "json", "retmax": max_results, "sort": "relevance"},
        )
        data = search_resp.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])

        if not pmids:
            return []

        # Rate limit pause
        await asyncio.sleep(0.5)

        # Step 2: fetch article details
        fetch_resp = await _request_with_retry(
            client, f"{BASE_URL}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
        )

        return _parse_pubmed_xml(fetch_resp.text)
    finally:
        if own_client:
            await client.aclose()


async def search_pubmed_sequential(queries: list[str], max_results: int = 20) -> list[dict]:
    """Run multiple PubMed queries sequentially with a shared client to respect rate limits."""
    all_articles = []
    async with httpx.AsyncClient(timeout=30) as client:
        for i, query in enumerate(queries):
            if i > 0:
                await asyncio.sleep(1.0)  # 1s between queries
            try:
                articles = await search_pubmed(query, max_results, client)
                all_articles.append(articles)
            except Exception as e:
                all_articles.append(e)
    return all_articles


async def _request_with_retry(client: httpx.AsyncClient, url: str, params: dict) -> httpx.Response:
    for attempt in range(MAX_RETRIES):
        resp = await client.get(url, params=params)
        if resp.status_code == 429:
            wait = 2 ** attempt  # 1s, 2s, 4s
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    # Last attempt
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    for article_elem in root.findall(".//PubmedArticle"):
        try:
            medline = article_elem.find("MedlineCitation")
            if medline is None:
                continue

            pmid_elem = medline.find("PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""

            art = medline.find("Article")
            if art is None:
                continue

            title_elem = art.find("ArticleTitle")
            title = _get_text(title_elem)

            abstract_parts = []
            abstract_elem = art.find("Abstract")
            if abstract_elem is not None:
                for at in abstract_elem.findall("AbstractText"):
                    label = at.get("Label", "")
                    text = _get_text(at)
                    if label and text:
                        abstract_parts.append(f"{label}: {text}")
                    elif text:
                        abstract_parts.append(text)
            abstract = " ".join(abstract_parts)

            author_list = []
            authors_elem = art.find("AuthorList")
            if authors_elem is not None:
                for author in authors_elem.findall("Author"):
                    last = author.findtext("LastName", "")
                    first = author.findtext("ForeName", "")
                    if last:
                        author_list.append(f"{last} {first}".strip())

            journal_elem = art.find("Journal")
            journal = ""
            if journal_elem is not None:
                journal = journal_elem.findtext("Title", "")

            pub_date = ""
            date_elem = art.find(".//PubDate")
            if date_elem is not None:
                year = date_elem.findtext("Year", "")
                month = date_elem.findtext("Month", "")
                pub_date = f"{year} {month}".strip()

            articles.append({
                "source": "pubmed",
                "external_id": pmid,
                "title": title,
                "abstract": abstract,
                "authors": ", ".join(author_list[:5]),
                "journal": journal,
                "pub_date": pub_date,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "raw_data": {"pmid": pmid},
            })
        except Exception:
            continue

    return articles


def _get_text(elem) -> str:
    if elem is None:
        return ""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        if child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()
