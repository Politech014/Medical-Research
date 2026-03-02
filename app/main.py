import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from starlette.responses import StreamingResponse

from app.database import (
    init_db,
    create_search,
    save_articles,
    save_analysis,
    get_search_results,
    get_all_searches,
    get_articles_for_search,
    create_patient_profile,
    get_patient_profiles,
    get_patient_profile,
    save_clinical_synthesis,
    upsert_article_note,
    get_notes_for_search,
    get_stats,
    delete_search,
    get_all_settings,
    update_settings,
)
from app.models import (
    SearchRequest,
    SearchResponse,
    SearchListItem,
    PatientProfileCreate,
    PatientProfileResponse,
    NoteRequest,
    NoteResponse,
    StatsResponse,
    SettingsUpdate,
    ValidateRequest,
)
from app.services.query_planner import plan_queries
from app.services.pubmed import search_pubmed_sequential
from app.services.clinicaltrials import search_clinicaltrials, fetch_study_by_nct_id
from app.services.europepmc import search_europepmc_sequential
from app.services.analyzer import analyze_single_article, generate_clinical_synthesis
from app.services.ai_client import validate_provider, get_current_provider
from app.services.report_export import generate_html_report
from app.services.citations import generate_ris, generate_bibtex

logger = logging.getLogger("medical")
logging.basicConfig(level=logging.INFO)

NCT_PATTERN = re.compile(r"NCT\d{8}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Medical Research App", lifespan=lifespan)


def _extract_nct_ids(text: str) -> tuple[list[str], str]:
    """Extract NCT IDs from input. Returns (nct_ids, remaining_text)."""
    nct_ids = NCT_PATTERN.findall(text)
    remaining = NCT_PATTERN.sub("", text).strip()
    # Clean up extra whitespace
    remaining = re.sub(r"\s+", " ", remaining).strip()
    return nct_ids, remaining


@app.post("/api/search")
async def do_search(req: SearchRequest):
    """Step 1: plan queries, search PubMed + ClinicalTrials + Europe PMC, save articles to DB."""
    try:
        search_id = create_search(req.query, req.language, req.patient_profile_id)

        all_articles = []
        seen_ids = set()

        # Check for NCT IDs in the query
        nct_ids, remaining_query = _extract_nct_ids(req.query)

        # Fetch specific NCT IDs directly
        if nct_ids:
            logger.info(f"Detected NCT IDs: {nct_ids}")
            nct_tasks = [fetch_study_by_nct_id(nct_id) for nct_id in nct_ids]
            nct_results = await asyncio.gather(*nct_tasks, return_exceptions=True)
            for nct_id, result in zip(nct_ids, nct_results):
                if isinstance(result, Exception):
                    logger.error(f"NCT fetch failed for {nct_id}: {result}")
                elif result:
                    ext_id = result.get("external_id", "")
                    if ext_id and ext_id not in seen_ids:
                        seen_ids.add(ext_id)
                        all_articles.append(result)

        # If only NCT IDs (no remaining text), skip query planner
        search_query = remaining_query if remaining_query else (req.query if not nct_ids else "")

        if search_query:
            # Plan queries with Claude
            logger.info(f"Planning queries for: {search_query}")
            queries = await plan_queries(search_query)
            logger.info(f"Planned queries: {queries}")

            # PubMed: sequential (rate limit), ClinicalTrials + Europe PMC: parallel
            pubmed_task = search_pubmed_sequential(queries["pubmed_queries"])
            ct_tasks = [search_clinicaltrials(q) for q in queries["clinicaltrials_queries"]]
            epmc_task = search_europepmc_sequential(queries.get("europepmc_queries", [search_query]))

            # Run all in parallel
            all_results = await asyncio.gather(pubmed_task, epmc_task, *ct_tasks, return_exceptions=True)

            # PubMed results (index 0)
            pm_results = all_results[0]
            if isinstance(pm_results, Exception):
                logger.error(f"PubMed search failed: {pm_results}")
            else:
                for i, batch in enumerate(pm_results):
                    if isinstance(batch, Exception):
                        logger.error(f"PubMed query {i} failed: {batch}")
                        continue
                    logger.info(f"PubMed query {i}: {len(batch)} results")
                    for article in batch:
                        ext_id = article.get("external_id", "")
                        if ext_id and ext_id not in seen_ids:
                            seen_ids.add(ext_id)
                            all_articles.append(article)

            # Europe PMC results (index 1) — dedup via PMID
            epmc_results = all_results[1]
            if isinstance(epmc_results, Exception):
                logger.error(f"Europe PMC search failed: {epmc_results}")
            else:
                for i, batch in enumerate(epmc_results):
                    if isinstance(batch, Exception):
                        logger.error(f"Europe PMC query {i} failed: {batch}")
                        continue
                    logger.info(f"Europe PMC query {i}: {len(batch)} results")
                    for article in batch:
                        # Dedup by both external_id and pmid
                        ext_id = article.get("external_id", "")
                        pmid = article.get("pmid", "")
                        if pmid and pmid in seen_ids:
                            continue
                        if ext_id and ext_id in seen_ids:
                            continue
                        if ext_id:
                            seen_ids.add(ext_id)
                        if pmid:
                            seen_ids.add(pmid)
                        all_articles.append(article)

            # ClinicalTrials results (index 2+)
            for i, result in enumerate(all_results[2:]):
                if isinstance(result, Exception):
                    logger.error(f"ClinicalTrials query {i} failed: {result}")
                    continue
                logger.info(f"ClinicalTrials query {i}: {len(result)} results")
                for article in result:
                    ext_id = article.get("external_id", "")
                    if ext_id and ext_id not in seen_ids:
                        seen_ids.add(ext_id)
                        all_articles.append(article)

            # Fallback with original query
            if not all_articles:
                logger.info("No results, trying fallback with original query")
                from app.services.pubmed import search_pubmed
                fb = await asyncio.gather(
                    search_pubmed(search_query),
                    search_clinicaltrials(search_query),
                    return_exceptions=True,
                )
                for result in fb:
                    if isinstance(result, Exception):
                        continue
                    for article in result:
                        ext_id = article.get("external_id", "")
                        if ext_id and ext_id not in seen_ids:
                            seen_ids.add(ext_id)
                            all_articles.append(article)

        # Cap
        cap = req.max_results
        if cap and cap > 0 and len(all_articles) > cap:
            all_articles = all_articles[:cap]

        logger.info(f"Total articles to save: {len(all_articles)}")

        if all_articles:
            save_articles(search_id, all_articles)

        return {"search_id": search_id, "article_count": len(all_articles)}

    except Exception as e:
        logger.exception(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/{search_id}/analyze")
async def analyze_search(search_id: int):
    """Step 2: SSE — analyzes articles 3 at a time, streams progress, then generates clinical synthesis."""
    search = get_search_results(search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    articles = get_articles_for_search(search_id)
    language = search["language"]
    query = search["original_query"]

    # Load patient profile if set
    patient_profile = None
    profile_id = search.get("patient_profile_id")
    if profile_id:
        profile = get_patient_profile(profile_id)
        if profile:
            patient_profile = profile["profile_text"]

    async def _analyze_with_heartbeat(article_data, q, lang, profile):
        """Run analysis as a task and yield heartbeat SSE comments while waiting."""
        task = asyncio.create_task(
            analyze_single_article(article_data, q, lang, profile)
        )
        while not task.done():
            await asyncio.sleep(5)
        return task.result()

    async def event_stream():
        total = len(articles)
        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"

        done_count = 0
        provider = get_current_provider()
        is_local = provider == "ollama"
        PARALLEL = 1 if is_local else 3

        for batch_start in range(0, total, PARALLEL):
            batch = articles[batch_start : batch_start + PARALLEL]

            if is_local:
                # Sequential for Ollama with heartbeat to keep SSE alive
                results = []
                for a in batch:
                    task = asyncio.create_task(
                        analyze_single_article(a, query, language, patient_profile)
                    )
                    while not task.done():
                        yield f": heartbeat\n\n"
                        await asyncio.sleep(5)
                    try:
                        results.append(task.result())
                    except Exception as e:
                        results.append(e)
            else:
                tasks = [analyze_single_article(a, query, language, patient_profile) for a in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            for article, result in zip(batch, results):
                done_count += 1
                if isinstance(result, Exception):
                    logger.error(f"Analysis failed for article {article['id']}: {result}")
                    analysis = {
                        "relevance_score": 0,
                        "article_type": "other",
                        "evidence_level": 5,
                        "relevance_explanation": "Analysis failed",
                        "summary": "",
                        "language": language,
                    }
                else:
                    analysis = result
                    analysis["language"] = language

                save_analysis(article["id"], analysis)

                yield f"data: {json.dumps({'type': 'progress', 'current': done_count, 'total': total, 'article_id': article['id'], 'title': (article['title'] or '')[:80], 'analysis': analysis})}\n\n"

        # Generate clinical synthesis after all articles are analyzed
        yield f"data: {json.dumps({'type': 'synthesis_start'})}\n\n"

        final = get_search_results(search_id)
        articles_for_synthesis = final.get("articles", [])

        if articles_for_synthesis:
            synth_task = asyncio.create_task(
                generate_clinical_synthesis(
                    query, language, patient_profile, articles_for_synthesis
                )
            )
            # Heartbeat while waiting for synthesis (can be slow on Ollama)
            while not synth_task.done():
                yield f": heartbeat\n\n"
                await asyncio.sleep(5)

            synth_result = synth_task.result()
            if synth_result.get("synthesis"):
                save_clinical_synthesis(
                    search_id,
                    synth_result["synthesis"],
                    synth_result.get("suggested_queries", []),
                )
                yield f"data: {json.dumps({'type': 'synthesis', 'text': synth_result['synthesis'], 'suggested_queries': synth_result.get('suggested_queries', [])})}\n\n"

        # Reload final data with synthesis
        final = get_search_results(search_id)
        yield f"data: {json.dumps({'type': 'done', 'results': final})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/search/{search_id}", response_model=SearchResponse)
async def get_search(search_id: int):
    result = get_search_results(search_id)
    if not result:
        raise HTTPException(status_code=404, detail="Search not found")
    return result


@app.get("/api/searches", response_model=list[SearchListItem])
async def list_searches():
    return get_all_searches()


@app.delete("/api/search/{search_id}")
async def remove_search(search_id: int):
    result = get_search_results(search_id)
    if not result:
        raise HTTPException(status_code=404, detail="Search not found")
    delete_search(search_id)
    return {"ok": True}


# ── Patient Profiles ──

@app.post("/api/patient-profiles", response_model=PatientProfileResponse)
async def create_profile(req: PatientProfileCreate):
    return create_patient_profile(req.name, req.profile_text)


@app.get("/api/patient-profiles", response_model=list[PatientProfileResponse])
async def list_profiles():
    return get_patient_profiles()


@app.delete("/api/patient-profiles/{profile_id}")
async def delete_profile(profile_id: int):
    from app.database import delete_patient_profile
    delete_patient_profile(profile_id)
    return {"ok": True}


# ── Article Notes ──

@app.put("/api/articles/{article_id}/note", response_model=NoteResponse)
async def update_note(article_id: int, req: NoteRequest):
    return upsert_article_note(article_id, req.note_text, req.status)


@app.get("/api/search/{search_id}/notes")
async def search_notes(search_id: int):
    return get_notes_for_search(search_id)


# ── Export ──

@app.get("/api/search/{search_id}/export")
async def export_search(search_id: int):
    result = get_search_results(search_id)
    if not result:
        raise HTTPException(status_code=404, detail="Search not found")
    notes = get_notes_for_search(search_id)
    html = generate_html_report(result, notes)
    return HTMLResponse(content=html)


# ── Citations ──

@app.get("/api/search/{search_id}/citations")
async def export_citations(search_id: int, format: str = Query("ris", pattern="^(ris|bibtex)$")):
    result = get_search_results(search_id)
    if not result:
        raise HTTPException(status_code=404, detail="Search not found")

    articles = result.get("articles", [])
    if format == "bibtex":
        content = generate_bibtex(articles)
        filename = f"search_{search_id}.bib"
        media_type = "application/x-bibtex"
    else:
        content = generate_ris(articles)
        filename = f"search_{search_id}.ris"
        media_type = "application/x-research-info-systems"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Stats ──

@app.get("/api/stats", response_model=StatsResponse)
async def dashboard_stats():
    return get_stats()


MASK = "••••••••"
SENSITIVE_KEYS = {"claude_api_key", "openai_api_key"}


@app.get("/api/settings")
async def get_settings():
    settings = get_all_settings()
    # Mask sensitive keys
    for key in SENSITIVE_KEYS:
        val = settings.get(key, "")
        if val and len(val) > 8:
            settings[key] = val[:4] + MASK + val[-4:]
        elif val:
            settings[key] = MASK
    return settings


@app.put("/api/settings")
async def put_settings(req: SettingsUpdate):
    current = get_all_settings()
    updates = {}
    for key, value in req.settings.items():
        # If the value contains the mask, keep the original value
        if MASK in value and key in SENSITIVE_KEYS:
            continue
        updates[key] = value
    if updates:
        update_settings(updates)
    return {"ok": True}


@app.post("/api/settings/validate")
async def validate_settings(req: ValidateRequest):
    # Merge with current settings for masked fields
    current = get_all_settings()
    merged = {**current}
    for key, value in req.settings.items():
        if MASK in value and key in SENSITIVE_KEYS:
            continue
        merged[key] = value
    result = await validate_provider(req.provider, merged)
    return result


@app.get("/api/settings/ollama-models")
async def list_ollama_models(base_url: str = Query("http://localhost:11434")):
    """Fetch installed models from an Ollama instance."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            models.sort()
            return {"models": models}
    except Exception as e:
        logger.error(f"Failed to fetch Ollama models: {e}")
        return {"models": [], "error": str(e)}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")
