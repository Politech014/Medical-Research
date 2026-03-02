import httpx
import logging

logger = logging.getLogger("medical")

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


async def fetch_study_by_nct_id(nct_id: str) -> dict | None:
    """Fetch a single study by its NCT ID."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(f"{BASE_URL}/{nct_id}", params={"format": "json"})
            if resp.status_code == 404:
                logger.warning(f"NCT ID not found: {nct_id}")
                return None
            resp.raise_for_status()
            study = resp.json()
            return _parse_study(study)
        except Exception as e:
            logger.error(f"Failed to fetch NCT ID {nct_id}: {e}")
            return None


async def search_clinicaltrials(query: str, max_results: int = 20) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        # Use query.term for full-text search across all fields
        resp = await client.get(
            BASE_URL,
            params={
                "query.term": query,
                "pageSize": max_results,
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    studies = data.get("studies", [])
    return [_parse_study(s) for s in studies]


def _parse_study(study: dict) -> dict:
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    desc = proto.get("descriptionModule", {})
    status = proto.get("statusModule", {})
    design = proto.get("designModule", {})
    cond_module = proto.get("conditionsModule", {})
    arms_module = proto.get("armsInterventionsModule", {})

    nct_id = ident.get("nctId", "")
    title = ident.get("officialTitle") or ident.get("briefTitle", "")
    brief_summary = desc.get("briefSummary", "")

    overall_status = status.get("overallStatus", "")
    phases = design.get("phases", [])
    phase_str = ", ".join(phases) if phases else ""

    conditions = cond_module.get("conditions", [])

    interventions = []
    for arm in arms_module.get("interventions", []):
        name = arm.get("name", "")
        itype = arm.get("type", "")
        if name:
            interventions.append(f"{itype}: {name}" if itype else name)

    # Build a structured abstract from the available fields
    abstract_parts = []
    if brief_summary:
        abstract_parts.append(brief_summary)
    if conditions:
        abstract_parts.append(f"Conditions: {', '.join(conditions)}")
    if interventions:
        abstract_parts.append(f"Interventions: {'; '.join(interventions)}")
    if overall_status:
        abstract_parts.append(f"Status: {overall_status}")
    if phase_str:
        abstract_parts.append(f"Phase: {phase_str}")

    return {
        "source": "clinicaltrials",
        "external_id": nct_id,
        "title": title,
        "abstract": " | ".join(abstract_parts),
        "authors": "",
        "journal": "",
        "pub_date": "",
        "url": f"https://clinicaltrials.gov/study/{nct_id}",
        "raw_data": {
            "nct_id": nct_id,
            "status": overall_status,
            "phase": phase_str,
            "conditions": conditions,
            "interventions": interventions,
        },
    }
