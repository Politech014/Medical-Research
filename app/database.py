import sqlite3
import json
from datetime import datetime
from app.config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patient_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            profile_text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_query TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'en',
            patient_profile_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_profile_id) REFERENCES patient_profiles(id)
        );

        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            title TEXT,
            abstract TEXT,
            authors TEXT,
            journal TEXT,
            pub_date TEXT,
            url TEXT,
            full_text TEXT,
            raw_data TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (search_id) REFERENCES searches(id)
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            relevance_score INTEGER NOT NULL DEFAULT 0,
            relevance_explanation TEXT,
            article_type TEXT,
            evidence_level INTEGER,
            summary TEXT,
            eligibility_status TEXT,
            eligibility_notes TEXT,
            language TEXT NOT NULL DEFAULT 'en',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (article_id) REFERENCES articles(id)
        );

        CREATE INDEX IF NOT EXISTS idx_articles_search_id ON articles(search_id);
        CREATE INDEX IF NOT EXISTS idx_analyses_article_id ON analyses(article_id);
    """)

    # Settings KV table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Migrations for existing databases
    _migrate(conn)

    # Seed settings from .env on first run
    _seed_settings(conn)

    conn.close()


def _migrate(conn: sqlite3.Connection):
    """Add columns if they don't exist (for existing databases)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
    if "full_text" not in existing:
        conn.execute("ALTER TABLE articles ADD COLUMN full_text TEXT")

    existing = {row[1] for row in conn.execute("PRAGMA table_info(analyses)").fetchall()}
    if "eligibility_status" not in existing:
        conn.execute("ALTER TABLE analyses ADD COLUMN eligibility_status TEXT")
    if "eligibility_notes" not in existing:
        conn.execute("ALTER TABLE analyses ADD COLUMN eligibility_notes TEXT")

    existing = {row[1] for row in conn.execute("PRAGMA table_info(searches)").fetchall()}
    if "patient_profile_id" not in existing:
        conn.execute("ALTER TABLE searches ADD COLUMN patient_profile_id INTEGER REFERENCES patient_profiles(id)")
    if "clinical_synthesis" not in existing:
        conn.execute("ALTER TABLE searches ADD COLUMN clinical_synthesis TEXT")
    if "suggested_queries" not in existing:
        conn.execute("ALTER TABLE searches ADD COLUMN suggested_queries TEXT")

    # Create article_notes table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS article_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL UNIQUE,
            note_text TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'none',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (article_id) REFERENCES articles(id)
        )
    """)

    conn.commit()


def create_search(query: str, language: str, patient_profile_id: int | None = None) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO searches (original_query, language, patient_profile_id) VALUES (?, ?, ?)",
        (query, language, patient_profile_id),
    )
    search_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return search_id


def save_articles(search_id: int, articles: list[dict]) -> list[int]:
    conn = get_connection()
    ids = []
    for a in articles:
        cursor = conn.execute(
            """INSERT INTO articles
               (search_id, source, external_id, title, abstract, authors, journal, pub_date, url, full_text, raw_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                search_id,
                a.get("source", ""),
                a.get("external_id", ""),
                a.get("title", ""),
                a.get("abstract", ""),
                a.get("authors", ""),
                a.get("journal", ""),
                a.get("pub_date", ""),
                a.get("url", ""),
                a.get("full_text") or None,
                json.dumps(a.get("raw_data", {})),
            ),
        )
        ids.append(cursor.lastrowid)
    conn.commit()
    conn.close()
    return ids


def save_analysis(article_id: int, analysis: dict) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO analyses
           (article_id, relevance_score, relevance_explanation, article_type, evidence_level, summary, eligibility_status, eligibility_notes, language)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            article_id,
            analysis.get("relevance_score", 0),
            analysis.get("relevance_explanation", ""),
            analysis.get("article_type", ""),
            analysis.get("evidence_level"),
            analysis.get("summary", ""),
            analysis.get("eligibility_status"),
            analysis.get("eligibility_notes"),
            analysis.get("language", "en"),
        ),
    )
    analysis_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return analysis_id


def get_search_results(search_id: int) -> dict | None:
    conn = get_connection()
    search = conn.execute(
        "SELECT * FROM searches WHERE id = ?", (search_id,)
    ).fetchone()
    if not search:
        conn.close()
        return None

    rows = conn.execute(
        """SELECT a.*, an.relevance_score, an.relevance_explanation,
                  an.article_type, an.evidence_level, an.summary as ai_summary,
                  an.eligibility_status, an.eligibility_notes,
                  an.language as analysis_language
           FROM articles a
           LEFT JOIN analyses an ON an.article_id = a.id
           WHERE a.search_id = ?
           ORDER BY an.relevance_score DESC""",
        (search_id,),
    ).fetchall()
    conn.close()

    articles = []
    for r in rows:
        articles.append({
            "id": r["id"],
            "source": r["source"],
            "external_id": r["external_id"],
            "title": r["title"],
            "abstract": r["abstract"],
            "authors": r["authors"],
            "journal": r["journal"],
            "pub_date": r["pub_date"],
            "url": r["url"],
            "full_text": bool(r["full_text"]),
            "relevance_score": r["relevance_score"],
            "relevance_explanation": r["relevance_explanation"],
            "article_type": r["article_type"],
            "evidence_level": r["evidence_level"],
            "ai_summary": r["ai_summary"],
            "eligibility_status": r["eligibility_status"],
            "eligibility_notes": r["eligibility_notes"],
        })

    suggested = []
    try:
        raw = search["suggested_queries"]
        if raw:
            suggested = json.loads(raw)
    except Exception:
        pass

    return {
        "id": search["id"],
        "original_query": search["original_query"],
        "language": search["language"],
        "patient_profile_id": search["patient_profile_id"],
        "created_at": search["created_at"],
        "clinical_synthesis": search["clinical_synthesis"] or None,
        "suggested_queries": suggested,
        "articles": articles,
    }


def get_articles_for_search(search_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT a.id, a.source, a.external_id, a.title, a.abstract,
                  a.authors, a.journal, a.pub_date, a.url, a.full_text
           FROM articles a
           LEFT JOIN analyses an ON an.article_id = a.id
           WHERE a.search_id = ? AND an.id IS NULL""",
        (search_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_search(search_id: int):
    conn = get_connection()
    # Delete in order: notes → analyses → articles → search
    conn.execute(
        "DELETE FROM article_notes WHERE article_id IN (SELECT id FROM articles WHERE search_id = ?)",
        (search_id,),
    )
    conn.execute(
        "DELETE FROM analyses WHERE article_id IN (SELECT id FROM articles WHERE search_id = ?)",
        (search_id,),
    )
    conn.execute("DELETE FROM articles WHERE search_id = ?", (search_id,))
    conn.execute("DELETE FROM searches WHERE id = ?", (search_id,))
    conn.commit()
    conn.close()


def get_all_searches() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT s.*, COUNT(a.id) as article_count
           FROM searches s
           LEFT JOIN articles a ON a.search_id = s.id
           GROUP BY s.id
           ORDER BY s.created_at DESC"""
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "original_query": r["original_query"],
            "language": r["language"],
            "created_at": r["created_at"],
            "article_count": r["article_count"],
        }
        for r in rows
    ]


# ── Patient Profiles CRUD ──

def create_patient_profile(name: str, profile_text: str) -> dict:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO patient_profiles (name, profile_text) VALUES (?, ?)",
        (name, profile_text),
    )
    pid = cursor.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM patient_profiles WHERE id = ?", (pid,)).fetchone()
    conn.close()
    return dict(row)


def get_patient_profiles() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM patient_profiles ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_patient_profile(profile_id: int):
    conn = get_connection()
    # Clear reference from searches that used this profile
    conn.execute(
        "UPDATE searches SET patient_profile_id = NULL WHERE patient_profile_id = ?",
        (profile_id,),
    )
    conn.execute("DELETE FROM patient_profiles WHERE id = ?", (profile_id,))
    conn.commit()
    conn.close()


def get_patient_profile(profile_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM patient_profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Clinical Synthesis ──

def save_clinical_synthesis(search_id: int, synthesis: str, suggested_queries: list[str]):
    conn = get_connection()
    conn.execute(
        "UPDATE searches SET clinical_synthesis = ?, suggested_queries = ? WHERE id = ?",
        (synthesis, json.dumps(suggested_queries), search_id),
    )
    conn.commit()
    conn.close()


# ── Article Notes ──

def upsert_article_note(article_id: int, note_text: str, status: str) -> dict:
    conn = get_connection()
    conn.execute(
        """INSERT INTO article_notes (article_id, note_text, status, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(article_id) DO UPDATE SET
               note_text = excluded.note_text,
               status = excluded.status,
               updated_at = datetime('now')""",
        (article_id, note_text, status),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM article_notes WHERE article_id = ?", (article_id,)
    ).fetchone()
    conn.close()
    return dict(row)


def get_notes_for_search(search_id: int) -> dict:
    conn = get_connection()
    rows = conn.execute(
        """SELECT n.* FROM article_notes n
           JOIN articles a ON a.id = n.article_id
           WHERE a.search_id = ?""",
        (search_id,),
    ).fetchall()
    conn.close()
    return {r["article_id"]: dict(r) for r in rows}


# ── Dashboard Stats ──

def _seed_settings(conn: sqlite3.Connection):
    """Seed default settings from .env if no settings exist yet."""
    count = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    if count > 0:
        return

    defaults = {
        "ai_provider": "claude",
        "claude_api_key": "",
        "claude_model": "claude-sonnet-4-20250514",
        "openai_api_key": "",
        "openai_model": "gpt-4o",
        "ollama_base_url": "http://localhost:11434",
        "ollama_model": "llama3",
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()


# ── Settings CRUD ──

def get_all_settings() -> dict[str, str]:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def get_setting(key: str) -> str | None:
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def update_settings(updates: dict[str, str]):
    conn = get_connection()
    for key, value in updates.items():
        conn.execute(
            """INSERT INTO settings (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')""",
            (key, value),
        )
    conn.commit()
    conn.close()


def get_stats() -> dict:
    conn = get_connection()
    total_searches = conn.execute("SELECT COUNT(*) FROM searches").fetchone()[0]
    total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    total_analyses = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    avg_score = conn.execute("SELECT ROUND(AVG(relevance_score)) FROM analyses WHERE relevance_score > 0").fetchone()[0] or 0

    sources = {}
    for row in conn.execute("SELECT source, COUNT(*) as cnt FROM articles GROUP BY source").fetchall():
        sources[row["source"]] = row["cnt"]

    recent = conn.execute(
        """SELECT s.id, s.original_query, s.language, s.created_at, COUNT(a.id) as article_count
           FROM searches s LEFT JOIN articles a ON a.search_id = s.id
           GROUP BY s.id ORDER BY s.created_at DESC LIMIT 5"""
    ).fetchall()
    conn.close()

    return {
        "total_searches": total_searches,
        "total_articles": total_articles,
        "total_analyses": total_analyses,
        "avg_score": int(avg_score),
        "sources": sources,
        "recent_searches": [dict(r) for r in recent],
    }
