from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    language: str = "en"
    patient_profile_id: int | None = None
    max_results: int | None = 30


class ArticleResponse(BaseModel):
    id: int
    source: str
    external_id: str
    title: str | None
    abstract: str | None
    authors: str | None
    journal: str | None
    pub_date: str | None
    url: str | None
    full_text: bool | None = None
    relevance_score: int | None
    relevance_explanation: str | None
    article_type: str | None
    evidence_level: int | None
    ai_summary: str | None
    eligibility_status: str | None = None
    eligibility_notes: str | None = None


class SearchResponse(BaseModel):
    id: int
    original_query: str
    language: str
    patient_profile_id: int | None = None
    created_at: str
    clinical_synthesis: str | None = None
    suggested_queries: list[str] = []
    articles: list[ArticleResponse]


class SearchListItem(BaseModel):
    id: int
    original_query: str
    language: str
    created_at: str
    article_count: int


class PatientProfileCreate(BaseModel):
    name: str
    profile_text: str


class PatientProfileResponse(BaseModel):
    id: int
    name: str
    profile_text: str
    created_at: str


class NoteRequest(BaseModel):
    note_text: str = ""
    status: str = "none"


class NoteResponse(BaseModel):
    id: int
    article_id: int
    note_text: str
    status: str
    updated_at: str


class StatsResponse(BaseModel):
    total_searches: int
    total_articles: int
    total_analyses: int
    avg_score: int
    sources: dict[str, int]
    recent_searches: list[dict]


class SettingsUpdate(BaseModel):
    settings: dict[str, str]


class ValidateRequest(BaseModel):
    provider: str
    settings: dict[str, str]
