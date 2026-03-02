import json
from app.services.ai_client import get_ai_response

SYSTEM_PROMPT = """You are a medical literature search expert. Given a user's medical query (in any language), generate optimized English search queries for PubMed, ClinicalTrials.gov, and Europe PMC.

CRITICAL RULES:
- Always generate queries in ENGLISH regardless of the input language
- Generate a MIX of specific and broad queries to maximize recall:
  - 1 broad query with just the key concept (2-3 terms max)
  - 1-2 moderately specific queries (combining 2 main concepts)
  - Avoid overly narrow queries that combine 3+ rare terms with AND
- For PubMed: use MeSH terms when appropriate. Use OR to broaden, AND sparingly.
  Example: "SETD2 AND ATR inhibitor" is good. "SETD2 AND ATR inhibitor AND thyroid neoplasms" is too narrow.
- For ClinicalTrials: use short, simple terms (1-3 words). These search across ALL fields.
  Example: "camonsertib" or "ATR inhibitor" — NOT "ATR inhibitor thyroid cancer SETD2"
- For Europe PMC: similar to PubMed but can use free-text search. Include open-access oriented queries.
  Example: "SETD2 thyroid cancer" or "SETD2 mutation oncocytic"

You MUST respond with valid JSON only, no other text. Use this exact format:
{
  "pubmed_queries": ["broad query", "moderate query 1", "moderate query 2"],
  "clinicaltrials_queries": ["simple term 1", "simple term 2"],
  "europepmc_queries": ["query 1", "query 2"]
}

Generate 2-3 PubMed queries, 1-2 ClinicalTrials queries, and 1-2 Europe PMC queries."""


async def plan_queries(user_query: str) -> dict:
    response_text = await get_ai_response(
        system=SYSTEM_PROMPT,
        user_message=f"Generate search queries for: {user_query}",
        max_tokens=1024,
    )

    # Extract JSON from response (handle markdown code blocks)
    if "```" in response_text:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        response_text = response_text[start:end]

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        # Fallback: use the original query directly
        result = {
            "pubmed_queries": [user_query],
            "clinicaltrials_queries": [user_query],
        }

    return {
        "pubmed_queries": result.get("pubmed_queries", [user_query]),
        "clinicaltrials_queries": result.get("clinicaltrials_queries", [user_query]),
        "europepmc_queries": result.get("europepmc_queries", [user_query]),
    }
