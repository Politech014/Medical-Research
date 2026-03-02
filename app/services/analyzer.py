import json
import logging
from datetime import date
from app.services.ai_client import get_ai_response

logger = logging.getLogger("medical")

LANGUAGE_NAMES = {
    "it": "Italian",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}

SYSTEM_PROMPT = """You are a medical research analyst. Evaluate the relevance of a scientific article/trial to the user's query.

Today's date is {today}. Use this to assess:
- For clinical trials: is it still recruiting? expired? completed? Note the status in your summary.
- For articles: how recent is the evidence?

Provide:
- relevance_score (0-100): how relevant to the user's query
- article_type: one of "trial", "review", "meta-analysis", "case_study", "guideline", "observational", "other"
- evidence_level (1-5): 1=systematic review/meta-analysis, 2=RCT, 3=cohort/case-control, 4=case series, 5=expert opinion/case report
- relevance_explanation: brief explanation of the score (in the requested language)
- summary: concise 2-3 sentence summary of key findings (in the requested language). For trials, include recruiting status and any expiry/completion info.

Respond with valid JSON ONLY:
{{"relevance_score": 85, "article_type": "review", "evidence_level": 1, "relevance_explanation": "...", "summary": "..."}}"""

SYSTEM_PROMPT_WITH_ELIGIBILITY = """You are a medical research analyst. Evaluate the relevance of a scientific article/trial to the user's query AND assess patient eligibility.

Today's date is {today}. Use this to assess:
- For clinical trials: is it still recruiting? expired? completed? Note the status in your summary.
- For articles: how recent is the evidence?

PATIENT PROFILE:
{patient_profile}

Provide:
- relevance_score (0-100): how relevant to the user's query
- article_type: one of "trial", "review", "meta-analysis", "case_study", "guideline", "observational", "other"
- evidence_level (1-5): 1=systematic review/meta-analysis, 2=RCT, 3=cohort/case-control, 4=case series, 5=expert opinion/case report
- relevance_explanation: brief explanation of the score (in the requested language)
- summary: concise 2-3 sentence summary of key findings (in the requested language). For trials, include recruiting status and any expiry/completion info.
- eligibility_status: one of "eligible", "potentially_eligible", "not_eligible", "unknown". For clinical trials, assess if the patient matches the inclusion/exclusion criteria. For articles, use "unknown" unless the study population clearly matches or doesn't match the patient.
- eligibility_notes: brief explanation of the eligibility assessment (in the requested language). For trials: mention specific criteria matched or not matched.

Respond with valid JSON ONLY:
{{"relevance_score": 85, "article_type": "review", "evidence_level": 1, "relevance_explanation": "...", "summary": "...", "eligibility_status": "potentially_eligible", "eligibility_notes": "..."}}"""


async def analyze_single_article(article: dict, user_query: str, language: str, patient_profile: str | None = None) -> dict:
    lang_name = LANGUAGE_NAMES.get(language, "English")

    # Build article text - use full_text if available for richer analysis
    full_text = article.get("full_text") or ""
    if full_text:
        article_text = (
            f"Source: {article.get('source', 'unknown')}\n"
            f"Title: {article.get('title', 'N/A')}\n"
            f"Journal: {article.get('journal', 'N/A')}\n"
            f"Date: {article.get('pub_date', 'N/A')}\n"
            f"Abstract: {(article.get('abstract') or 'N/A')[:1500]}\n\n"
            f"Full Text (excerpt):\n{full_text[:6000]}"
        )
    else:
        article_text = (
            f"Source: {article.get('source', 'unknown')}\n"
            f"Title: {article.get('title', 'N/A')}\n"
            f"Abstract: {(article.get('abstract') or 'N/A')[:2000]}\n"
            f"Journal: {article.get('journal', 'N/A')}\n"
            f"Date: {article.get('pub_date', 'N/A')}"
        )

    user_message = (
        f"User query: {user_query}\n"
        f"Language for output: {lang_name}\n\n"
        f"Article:\n{article_text}"
    )

    if patient_profile:
        system_prompt = SYSTEM_PROMPT_WITH_ELIGIBILITY.format(
            today=date.today().isoformat(),
            patient_profile=patient_profile,
        )
    else:
        system_prompt = SYSTEM_PROMPT.format(today=date.today().isoformat())

    response_text = await get_ai_response(system=system_prompt, user_message=user_message, max_tokens=1024)

    # Extract JSON
    if "```" in response_text:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        response_text = response_text[start:end]

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        result = {
            "relevance_score": 50,
            "article_type": "other",
            "evidence_level": 5,
            "relevance_explanation": "Analysis unavailable",
            "summary": article.get("title", ""),
        }

    return {
        "relevance_score": result.get("relevance_score", 0),
        "article_type": result.get("article_type", "other"),
        "evidence_level": result.get("evidence_level", 5),
        "relevance_explanation": result.get("relevance_explanation", ""),
        "summary": result.get("summary", ""),
        "eligibility_status": result.get("eligibility_status"),
        "eligibility_notes": result.get("eligibility_notes"),
    }


SYNTHESIS_PROMPT = """You are a senior consulting oncologist and clinical researcher. Based on the following search query and analyzed articles, generate a comprehensive clinical synthesis report.

Today's date is {today}.

{patient_context}

SEARCH QUERY: {query}

ANALYZED ARTICLES:
{articles_text}

Generate a response in valid JSON with two fields:

1. "synthesis": A structured clinical synthesis in {language} using this format:
## Key Findings
(Summarize the most important findings across all articles)

## Therapeutic Options
(List treatment options identified, with evidence levels)

## Clinical Trials to Consider
(List any active/recruiting trials with NCT IDs if available)

## Evidence Gaps
(What questions remain unanswered by current evidence?)

## Clinical Recommendation
(Brief evidence-based recommendation)

2. "suggested_queries": An array of 3-4 follow-up search queries in English that could deepen the research (e.g., specific drug names, combinations, biomarkers mentioned in the articles)

Respond with valid JSON ONLY:
{{"synthesis": "## Key Findings\\n...", "suggested_queries": ["query1", "query2", "query3"]}}"""


async def generate_clinical_synthesis(
    query: str,
    language: str,
    patient_profile: str | None,
    articles_with_analyses: list[dict],
) -> dict:
    """Generate a global clinical synthesis from all analyzed articles."""
    lang_name = LANGUAGE_NAMES.get(language, "English")

    # Build articles summary text
    articles_parts = []
    for i, a in enumerate(articles_with_analyses[:25], 1):
        score = a.get("relevance_score") or 0
        articles_parts.append(
            f"[{i}] Score: {score} | Type: {a.get('article_type', 'N/A')} | Evidence: L{a.get('evidence_level', '?')}\n"
            f"    Title: {(a.get('title') or 'N/A')[:150]}\n"
            f"    Summary: {(a.get('ai_summary') or a.get('summary') or 'N/A')[:300]}\n"
            f"    Eligibility: {a.get('eligibility_status', 'N/A')} - {(a.get('eligibility_notes') or '')[:150]}"
        )

    patient_context = ""
    if patient_profile:
        patient_context = f"PATIENT PROFILE:\n{patient_profile}\n"

    prompt = SYNTHESIS_PROMPT.format(
        today=date.today().isoformat(),
        query=query,
        language=lang_name,
        patient_context=patient_context,
        articles_text="\n\n".join(articles_parts),
    )

    try:
        response_text = await get_ai_response(system="", user_message=prompt, max_tokens=2048)

        if "```" in response_text:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            response_text = response_text[start:end]

        result = json.loads(response_text)
        return {
            "synthesis": result.get("synthesis", ""),
            "suggested_queries": result.get("suggested_queries", []),
        }
    except Exception as e:
        logger.error(f"Clinical synthesis generation failed: {e}")
        return {"synthesis": "", "suggested_queries": []}
