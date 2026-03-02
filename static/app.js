const form = document.getElementById('search-form');
const queryInput = document.getElementById('query-input');
const languageSelect = document.getElementById('language-select');
const searchBtn = document.getElementById('search-btn');
const progress = document.getElementById('progress');
const progressText = document.getElementById('progress-text');
const progressBar = document.getElementById('progress-bar');
const progressFill = document.getElementById('progress-fill');
const report = document.getElementById('report');
const reportId = document.getElementById('report-id');
const reportQuery = document.getElementById('report-query');
const reportMeta = document.getElementById('report-meta');
const resultsCount = document.getElementById('results-count');
const resultsDiv = document.getElementById('results');
const historyList = document.getElementById('history-list');
const emptyState = document.getElementById('empty-state');
const btnHistory = document.getElementById('btn-history');
const drawer = document.getElementById('drawer');
const drawerOverlay = document.getElementById('drawer-overlay');
const drawerClose = document.getElementById('drawer-close');
const btnExport = document.getElementById('btn-export');

// Patient profile elements
const patientToggle = document.getElementById('patient-toggle');
const patientBody = document.getElementById('patient-body');
const patientChevron = document.getElementById('patient-chevron');
const profileSelect = document.getElementById('profile-select');
const btnNewProfile = document.getElementById('btn-new-profile');
const newProfileForm = document.getElementById('new-profile-form');
const profileName = document.getElementById('profile-name');
const profileText = document.getElementById('profile-text');
const btnSaveProfile = document.getElementById('btn-save-profile');
const btnCancelProfile = document.getElementById('btn-cancel-profile');
const profilePreview = document.getElementById('profile-preview');
const profilePreviewText = document.getElementById('profile-preview-text');

// Synthesis elements
const synthesisCard = document.getElementById('synthesis-card');
const synthesisContent = document.getElementById('synthesis-content');
const suggestedQueries = document.getElementById('suggested-queries');
const sqChips = document.getElementById('sq-chips');

// Filter elements
const filterSource = document.getElementById('filter-source');
const filterEvidence = document.getElementById('filter-evidence');
const filterType = document.getElementById('filter-type');
const filterEligibility = document.getElementById('filter-eligibility');
const filterFulltext = document.getElementById('filter-fulltext');
const filterBookmarked = document.getElementById('filter-bookmarked');
const sortBy = document.getElementById('sort-by');
const filterTextInput = document.getElementById('filter-text');
const filterCounter = document.getElementById('filter-counter');

// Citation elements
const btnCite = document.getElementById('btn-cite');
const citeMenu = document.getElementById('cite-menu');

let chartScores = null, chartSources = null, chartEvidence = null, chartEligibility = null;
let currentSearchId = null;

// Global article data for filtering
let allArticles = [];
let articleNotes = {};
let currentQuery = '';

/* ── Chart defaults (light theme) ── */
Chart.defaults.color = '#9ca3af';
Chart.defaults.borderColor = '#f3f4f6';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.weight = 600;
Chart.defaults.font.size = 11;

/* ═══════════════════════════════════════════
   BRAND RESET
   ═══════════════════════════════════════════ */
document.getElementById('brand-link').addEventListener('click', (e) => {
    e.preventDefault();
    queryInput.value = '';
    report.classList.add('hidden');
    synthesisCard.classList.add('hidden');
    hideProgress();
    emptyState.classList.remove('hidden');
    document.getElementById('empty-default').classList.remove('hidden');
    document.getElementById('dashboard').classList.add('hidden');
    currentSearchId = null;
    allArticles = [];
    articleNotes = {};
    queryInput.focus();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    loadDashboard();
});

/* ═══════════════════════════════════════════
   PATIENT PROFILE
   ═══════════════════════════════════════════ */
patientToggle.addEventListener('click', () => {
    patientBody.classList.toggle('hidden');
    patientChevron.style.transform = patientBody.classList.contains('hidden') ? '' : 'rotate(180deg)';
});

btnNewProfile.addEventListener('click', () => {
    newProfileForm.classList.remove('hidden');
    profileName.focus();
});

btnCancelProfile.addEventListener('click', () => {
    newProfileForm.classList.add('hidden');
    profileName.value = '';
    profileText.value = '';
});

btnSaveProfile.addEventListener('click', async () => {
    const name = profileName.value.trim();
    const text = profileText.value.trim();
    if (!name || !text) return;

    try {
        const resp = await fetch('/api/patient-profiles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, profile_text: text }),
        });
        if (!resp.ok) throw new Error('Save failed');
        const profile = await resp.json();
        newProfileForm.classList.add('hidden');
        profileName.value = '';
        profileText.value = '';
        await loadProfiles();
        profileSelect.value = profile.id;
        updateProfilePreview();
    } catch (err) {
        alert('Failed to save profile: ' + err.message);
    }
});

const btnDeleteProfile = document.getElementById('btn-delete-profile');

btnDeleteProfile.addEventListener('click', async () => {
    const id = profileSelect.value;
    if (!id) return;
    const name = profileSelect.selectedOptions[0].textContent;
    if (!confirm(`Delete profile "${name}"?`)) return;
    try {
        await fetch(`/api/patient-profiles/${id}`, { method: 'DELETE' });
        await loadProfiles();
        updateProfilePreview();
    } catch (err) {
        alert('Failed to delete: ' + err.message);
    }
});

profileSelect.addEventListener('change', updateProfilePreview);

function updateProfilePreview() {
    const opt = profileSelect.selectedOptions[0];
    if (opt && opt.dataset.text) {
        profilePreview.classList.remove('hidden');
        profilePreviewText.textContent = opt.dataset.text;
    } else {
        profilePreview.classList.add('hidden');
        profilePreviewText.textContent = '';
    }
}

async function loadProfiles() {
    try {
        const resp = await fetch('/api/patient-profiles');
        if (!resp.ok) return;
        const profiles = await resp.json();
        const current = profileSelect.value;
        profileSelect.innerHTML = '<option value="">No patient profile</option>';
        for (const p of profiles) {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            opt.dataset.text = p.profile_text;
            profileSelect.appendChild(opt);
        }
        if (current) profileSelect.value = current;
    } catch {}
}

loadProfiles();

/* ═══════════════════════════════════════════
   DRAWER
   ═══════════════════════════════════════════ */
btnHistory.addEventListener('click', () => {
    drawer.classList.remove('hidden');
    drawerOverlay.classList.remove('hidden');
    loadHistory();
});

function closeDrawer() {
    drawer.classList.add('hidden');
    drawerOverlay.classList.add('hidden');
}

drawerClose.addEventListener('click', closeDrawer);
drawerOverlay.addEventListener('click', closeDrawer);

/* ═══════════════════════════════════════════
   EXPORT + CITATIONS
   ═══════════════════════════════════════════ */
btnExport.addEventListener('click', () => {
    if (currentSearchId) {
        window.open(`/api/search/${currentSearchId}/export`, '_blank');
    }
});

btnCite.addEventListener('click', (e) => {
    e.stopPropagation();
    citeMenu.classList.toggle('hidden');
});

document.addEventListener('click', () => citeMenu.classList.add('hidden'));

document.querySelectorAll('.cite-option').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const format = btn.dataset.format;
        if (currentSearchId) {
            window.open(`/api/search/${currentSearchId}/citations?format=${format}`, '_blank');
        }
        citeMenu.classList.add('hidden');
    });
});

/* ═══════════════════════════════════════════
   FILTERS
   ═══════════════════════════════════════════ */
[filterSource, filterEvidence, filterType, filterEligibility, sortBy].forEach(el => {
    el.addEventListener('change', applyFilters);
});
[filterFulltext, filterBookmarked].forEach(el => {
    el.addEventListener('change', applyFilters);
});
filterTextInput.addEventListener('input', applyFilters);

function applyFilters() {
    const srcVal = filterSource.value;
    const evVal = filterEvidence.value;
    const typeVal = filterType.value;
    const eligVal = filterEligibility.value;
    const ftOnly = filterFulltext.checked;
    const bookOnly = filterBookmarked.checked;
    const textSearch = filterTextInput.value.trim().toLowerCase();
    const sortVal = sortBy.value;

    let filtered = allArticles.filter(a => {
        if ((a.relevance_score || 0) < 40) return false;
        if (srcVal && a.source !== srcVal) return false;
        if (evVal && a.evidence_level != evVal) return false;
        if (typeVal && a.article_type !== typeVal) return false;
        if (eligVal && a.eligibility_status !== eligVal) return false;
        if (ftOnly && !a.full_text) return false;
        if (bookOnly) {
            const note = articleNotes[a.id];
            if (!note || note.status === 'none') return false;
        }
        if (textSearch) {
            const haystack = [a.title, a.ai_summary, a.authors, a.journal, a.relevance_explanation].join(' ').toLowerCase();
            if (!haystack.includes(textSearch)) return false;
        }
        return true;
    });

    // Sort
    if (sortVal === 'date') {
        filtered.sort((a, b) => (b.pub_date || '').localeCompare(a.pub_date || ''));
    } else if (sortVal === 'evidence') {
        filtered.sort((a, b) => (a.evidence_level || 5) - (b.evidence_level || 5));
    } else {
        filtered.sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0));
    }

    const totalRelevant = allArticles.filter(a => (a.relevance_score || 0) >= 40).length;
    filterCounter.textContent = `Showing ${filtered.length} of ${totalRelevant}`;
    resultsCount.textContent = filtered.length ? `${filtered.length} relevant results` : '';

    renderArticleCards(filtered);
}

/* ═══════════════════════════════════════════
   SEARCH
   ═══════════════════════════════════════════ */
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;

    currentQuery = query;
    searchBtn.disabled = true;
    emptyState.classList.add('hidden');
    report.classList.add('hidden');
    resultsDiv.innerHTML = '';
    synthesisCard.classList.add('hidden');
    showProgress('Generating optimized search queries...', -1);

    const profileId = profileSelect.value ? parseInt(profileSelect.value) : null;

    try {
        showProgress('Searching PubMed, ClinicalTrials.gov & Europe PMC...', -1);
        const resp = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, language: languageSelect.value, patient_profile_id: profileId, max_results: parseInt(document.getElementById('max-results-select').value) || null }),
        });

        if (!resp.ok) {
            let msg = 'Search failed';
            try { msg = (await resp.json()).detail || msg; } catch {}
            throw new Error(msg);
        }

        const data = await resp.json();

        if (data.article_count === 0) {
            hideProgress();
            currentSearchId = data.search_id;
            report.classList.remove('hidden');
            setReportHeader({ id: data.search_id, original_query: query, created_at: new Date().toISOString(), articles: [] });
            resultsDiv.innerHTML = '<div class="no-results">No articles found.</div>';
            searchBtn.disabled = false;
            return;
        }

        showProgress(`Found ${data.article_count} articles. Analyzing 0/${data.article_count}...`, 0);
        await analyzeSSE(data.search_id, data.article_count);
    } catch (err) {
        hideProgress();
        report.classList.remove('hidden');
        resultsDiv.innerHTML = `<div class="no-results">${esc(err.message)}</div>`;
    } finally {
        searchBtn.disabled = false;
    }
});

function analyzeSSE(searchId, total) {
    return new Promise((resolve) => {
        const es = new EventSource(`/api/search/${searchId}/analyze`);

        es.onmessage = (ev) => {
            const d = JSON.parse(ev.data);
            if (d.type === 'start') showProgress(`Analyzing 0/${d.total}...`, 0);
            if (d.type === 'progress') {
                const pct = Math.round((d.current / d.total) * 100);
                showProgress(`Analyzing ${d.current}/${d.total} — ${(d.title || '').substring(0, 40)}...`, pct);
            }
            if (d.type === 'synthesis_start') {
                showProgress('Generating clinical synthesis...', 100);
            }
            if (d.type === 'synthesis') {
                showSynthesis(d.text, d.suggested_queries || []);
            }
            if (d.type === 'done') {
                es.close();
                hideProgress();
                showReport(d.results);
                resolve();
            }
        };

        es.onerror = () => {
            es.close();
            hideProgress();
            fetch(`/api/search/${searchId}`).then(r => r.json()).then(showReport).catch(() => {
                report.classList.remove('hidden');
                resultsDiv.innerHTML = '<div class="no-results">Analysis interrupted.</div>';
            });
            resolve();
        };
    });
}

/* ═══════════════════════════════════════════
   SYNTHESIS
   ═══════════════════════════════════════════ */
function showSynthesis(text, queries) {
    if (!text) {
        synthesisCard.classList.add('hidden');
        return;
    }
    synthesisCard.classList.remove('hidden');

    // Simple markdown to HTML
    let html = esc(text);
    html = html.replace(/## (.*?)(\n|$)/g, '<h4>$1</h4>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\n- /g, '\n<li>');
    html = html.replace(/<li>(.*?)(?=\n|$)/g, '<li>$1</li>');
    html = html.replace(/\n/g, '<br>');
    // Wrap consecutive <li> in <ul>
    html = html.replace(/(<li>.*?<\/li>(<br>)?)+/g, (match) => {
        return '<ul>' + match.replace(/<br>/g, '') + '</ul>';
    });
    synthesisContent.innerHTML = html;

    // Suggested queries
    if (queries && queries.length) {
        suggestedQueries.classList.remove('hidden');
        sqChips.innerHTML = '';
        for (const q of queries) {
            const chip = document.createElement('button');
            chip.className = 'sq-chip';
            chip.textContent = q;
            chip.addEventListener('click', () => {
                queryInput.value = q;
                queryInput.focus();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
            sqChips.appendChild(chip);
        }
    } else {
        suggestedQueries.classList.add('hidden');
    }
}

/* ═══════════════════════════════════════════
   REPORT
   ═══════════════════════════════════════════ */
function showReport(data) {
    report.classList.remove('hidden');
    emptyState.classList.add('hidden');
    currentSearchId = data.id;
    currentQuery = data.original_query;
    allArticles = data.articles || [];
    articleNotes = {};

    setReportHeader(data);
    buildCharts(data.articles || []);

    // Show synthesis if available
    if (data.clinical_synthesis) {
        showSynthesis(data.clinical_synthesis, data.suggested_queries || []);
    }

    // Load notes then render
    loadNotes(data.id).then(() => applyFilters());

    window.scrollTo({ top: report.offsetTop - 80, behavior: 'smooth' });
}

async function loadNotes(searchId) {
    try {
        const resp = await fetch(`/api/search/${searchId}/notes`);
        if (resp.ok) {
            articleNotes = await resp.json();
        }
    } catch {}
}

function setReportHeader(data) {
    const all = data.articles || [];
    const relevant = all.filter(a => (a.relevance_score || 0) >= 40).length;
    const avg = all.length ? Math.round(all.reduce((s, a) => s + (a.relevance_score || 0), 0) / all.length) : 0;
    const date = data.created_at ? fmtDate(data.created_at) : '';

    reportId.textContent = `SEARCH #${data.id}`;
    reportQuery.textContent = data.original_query;
    reportMeta.innerHTML = `${date} &middot; <b>${all.length}</b> articles &middot; <b>${relevant}</b> relevant &middot; avg score <b>${avg}</b>`;
}

/* ═══════════════════════════════════════════
   CHARTS
   ═══════════════════════════════════════════ */
function buildCharts(articles) {
    [chartScores, chartSources, chartEvidence, chartEligibility].forEach(c => c && c.destroy());
    chartScores = chartSources = chartEvidence = chartEligibility = null;

    const scored = articles.filter(a => a.relevance_score != null);
    if (!scored.length) return;

    // Buckets
    const bk = [0, 0, 0, 0, 0];
    for (const a of scored) {
        const s = a.relevance_score;
        bk[s < 20 ? 0 : s < 40 ? 1 : s < 60 ? 2 : s < 80 ? 3 : 4]++;
    }

    chartScores = new Chart(document.getElementById('chart-scores'), {
        type: 'bar',
        data: {
            labels: ['0–19', '20–39', '40–59', '60–79', '80–100'],
            datasets: [{
                data: bk,
                backgroundColor: ['#fee2e2', '#fef3c7', '#fef3c7', '#d1fae5', '#d1fae5'],
                borderColor: ['#ef4444', '#f59e0b', '#f59e0b', '#10b981', '#10b981'],
                borderWidth: 1.5,
                borderRadius: 6,
            }],
        },
        options: barOpts(),
    });

    // Sources
    const src = {};
    for (const a of scored) {
        const k = a.source === 'pubmed' ? 'PubMed' : a.source === 'europepmc' ? 'Europe PMC' : 'ClinicalTrials';
        src[k] = (src[k] || 0) + 1;
    }

    const srcColors = { 'PubMed': '#d1fae5', 'ClinicalTrials': '#fef3c7', 'Europe PMC': '#dbeafe' };
    const srcBorders = { 'PubMed': '#059669', 'ClinicalTrials': '#d97706', 'Europe PMC': '#2563eb' };

    chartSources = new Chart(document.getElementById('chart-sources'), {
        type: 'doughnut',
        data: {
            labels: Object.keys(src),
            datasets: [{
                data: Object.values(src),
                backgroundColor: Object.keys(src).map(k => srcColors[k] || '#f3f4f6'),
                borderColor: Object.keys(src).map(k => srcBorders[k] || '#9ca3af'),
                borderWidth: 2,
                hoverOffset: 6,
            }],
        },
        options: {
            responsive: true,
            cutout: '62%',
            plugins: { legend: { position: 'bottom', labels: { padding: 14, font: { size: 11, weight: 700 }, usePointStyle: true, pointStyleWidth: 8 } } },
        },
    });

    // Evidence
    const eLabels = ['L1 Meta/SR', 'L2 RCT', 'L3 Cohort', 'L4 Series', 'L5 Opinion'];
    const eData = [0, 0, 0, 0, 0];
    for (const a of scored) { const l = a.evidence_level; if (l >= 1 && l <= 5) eData[l - 1]++; }
    const eColors = ['#dbeafe', '#e0e7ff', '#ede9fe', '#fef3c7', '#fee2e2'];
    const eBorders = ['#2563eb', '#4f46e5', '#7c3aed', '#d97706', '#ef4444'];

    chartEvidence = new Chart(document.getElementById('chart-evidence'), {
        type: 'bar',
        data: {
            labels: eLabels,
            datasets: [{ data: eData, backgroundColor: eColors, borderColor: eBorders, borderWidth: 1.5, borderRadius: 6 }],
        },
        options: barOpts(true),
    });

    // Eligibility chart
    const eligData = {};
    for (const a of scored) {
        const st = a.eligibility_status;
        if (st && st !== 'unknown') {
            eligData[st] = (eligData[st] || 0) + 1;
        }
    }

    const eligCard = document.getElementById('chart-elig-card');
    if (Object.keys(eligData).length > 0) {
        eligCard.classList.remove('hidden');
        const eligLabels = { eligible: 'Eligible', potentially_eligible: 'Potentially', not_eligible: 'Not Eligible' };
        const eligColors = { eligible: '#d1fae5', potentially_eligible: '#fef3c7', not_eligible: '#fee2e2' };
        const eligBorders = { eligible: '#059669', potentially_eligible: '#d97706', not_eligible: '#dc2626' };

        chartEligibility = new Chart(document.getElementById('chart-eligibility'), {
            type: 'doughnut',
            data: {
                labels: Object.keys(eligData).map(k => eligLabels[k] || k),
                datasets: [{
                    data: Object.values(eligData),
                    backgroundColor: Object.keys(eligData).map(k => eligColors[k] || '#f3f4f6'),
                    borderColor: Object.keys(eligData).map(k => eligBorders[k] || '#9ca3af'),
                    borderWidth: 2,
                    hoverOffset: 6,
                }],
            },
            options: {
                responsive: true,
                cutout: '62%',
                plugins: { legend: { position: 'bottom', labels: { padding: 14, font: { size: 11, weight: 700 }, usePointStyle: true, pointStyleWidth: 8 } } },
            },
        });
    } else {
        eligCard.classList.add('hidden');
    }
}

function barOpts(horizontal = false) {
    return {
        indexAxis: horizontal ? 'y' : 'x',
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            x: { beginAtZero: true, grid: { color: '#f3f4f6' }, ticks: { stepSize: 1, precision: 0 } },
            y: { grid: { color: horizontal ? '#f3f4f6' : 'transparent' } },
        },
    };
}

/* ═══════════════════════════════════════════
   KEYWORD HIGHLIGHTING
   ═══════════════════════════════════════════ */
function highlightKeywords(text, query) {
    if (!text || !query) return esc(text);
    const escaped = esc(text);
    const words = query.split(/\s+/).filter(w => w.length > 2);
    if (!words.length) return escaped;

    const pattern = words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const regex = new RegExp(`(${pattern})`, 'gi');
    return escaped.replace(regex, '<mark>$1</mark>');
}

/* ═══════════════════════════════════════════
   ARTICLES
   ═══════════════════════════════════════════ */
function renderArticleCards(articles) {
    if (!articles.length) {
        resultsDiv.innerHTML = '<div class="no-results">No articles match the current filters.</div>';
        return;
    }

    const eLbls = { 1: 'L1 Meta-analysis', 2: 'L2 RCT', 3: 'L3 Cohort', 4: 'L4 Case series', 5: 'L5 Opinion' };
    let html = '';

    for (const a of articles) {
        const score = a.relevance_score || 0;
        const cls = score >= 75 ? 'high' : score >= 50 ? 'medium' : 'low';

        let srcBadge;
        if (a.source === 'pubmed') {
            srcBadge = '<span class="badge badge-pubmed">PubMed</span>';
        } else if (a.source === 'europepmc') {
            srcBadge = '<span class="badge badge-europepmc">Europe PMC</span>';
        } else {
            srcBadge = '<span class="badge badge-clinicaltrials">ClinicalTrials</span>';
        }

        const typeBadge = a.article_type ? `<span class="badge badge-type">${esc(a.article_type)}</span>` : '';
        const evBadge = a.evidence_level ? `<span class="badge badge-evidence">${eLbls[a.evidence_level] || 'L' + a.evidence_level}</span>` : '';
        const ftBadge = a.full_text ? '<span class="badge badge-fulltext">Full Text</span>' : '';

        // Eligibility badge
        let eligBadge = '';
        if (a.eligibility_status && a.eligibility_status !== 'unknown') {
            const eligCls = {
                eligible: 'badge-eligible',
                potentially_eligible: 'badge-potentially-eligible',
                not_eligible: 'badge-not-eligible',
            }[a.eligibility_status] || '';
            const eligLabel = a.eligibility_status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            eligBadge = `<span class="badge ${eligCls}">${esc(eligLabel)}</span>`;
        }

        const meta = [a.authors, a.journal, a.pub_date].filter(Boolean);

        // Notes
        const note = articleNotes[a.id] || { status: 'none', note_text: '' };
        const noteStatus = note.status || 'none';
        const noteText = note.note_text || '';

        const statusBtns = `
            <div class="note-actions" data-article-id="${a.id}">
                <button class="note-btn ${noteStatus === 'important' ? 'active' : ''}" data-status="important" title="Important">&#9733;</button>
                <button class="note-btn ${noteStatus === 'reviewed' ? 'active' : ''}" data-status="reviewed" title="Reviewed">&#10003;</button>
                <button class="note-btn ${noteStatus === 'dismissed' ? 'active' : ''}" data-status="dismissed" title="Dismiss">&#10005;</button>
                <button class="note-btn note-toggle-btn" data-toggle-note title="Add note">&#9998;</button>
            </div>`;

        const noteArea = `
            <div class="note-area hidden" data-note-area="${a.id}">
                <textarea class="note-textarea" data-note-input="${a.id}" placeholder="Add a note...">${esc(noteText)}</textarea>
            </div>`;

        // Abstract toggle
        const abstractHtml = a.abstract ? `
            <div class="abstract-toggle">
                <button class="btn-abstract" data-abstract-toggle="${a.id}">Show Abstract</button>
                <div class="abstract-content hidden" data-abstract="${a.id}">${highlightKeywords(a.abstract, currentQuery)}</div>
            </div>` : '';

        html += `
        <div class="article-card" data-article-id="${a.id}">
            <div class="card-layout">
                <div class="card-score">
                    <div class="score-ring ${cls}">${score}</div>
                    <span class="score-tag">score</span>
                </div>
                <div class="card-body">
                    <div class="card-top-row">
                        <div class="badges">${srcBadge}${typeBadge}${evBadge}${ftBadge}${eligBadge}</div>
                        ${statusBtns}
                    </div>
                    <div class="card-title"><a href="${esc(a.url || '#')}" target="_blank" rel="noopener">${highlightKeywords(a.title || 'Untitled', currentQuery)}</a></div>
                    ${meta.length ? `<div class="card-meta">${esc(meta.join(' · '))}</div>` : ''}
                    ${a.ai_summary ? `<div class="card-summary">${highlightKeywords(a.ai_summary, currentQuery)}</div>` : ''}
                    ${a.relevance_explanation ? `<div class="card-rationale"><span class="rationale-label">Rationale</span>${highlightKeywords(a.relevance_explanation, currentQuery)}</div>` : ''}
                    ${a.eligibility_notes ? `<div class="card-eligibility"><span class="eligibility-label">Eligibility</span>${esc(a.eligibility_notes)}</div>` : ''}
                    ${abstractHtml}
                    ${noteArea}
                </div>
            </div>
        </div>`;
    }

    resultsDiv.innerHTML = html;

    // Bind events
    bindNoteEvents();
    bindAbstractToggles();
}

/* ═══════════════════════════════════════════
   NOTE EVENTS
   ═══════════════════════════════════════════ */
let noteDebounceTimers = {};

function bindNoteEvents() {
    // Status buttons
    document.querySelectorAll('.note-actions .note-btn[data-status]').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const articleId = btn.closest('.note-actions').dataset.articleId;
            const status = btn.dataset.status;
            const currentNote = articleNotes[articleId] || { status: 'none', note_text: '' };
            const newStatus = currentNote.status === status ? 'none' : status;

            // Update UI immediately
            const actions = btn.closest('.note-actions');
            actions.querySelectorAll('.note-btn[data-status]').forEach(b => b.classList.remove('active'));
            if (newStatus !== 'none') btn.classList.add('active');

            articleNotes[articleId] = { ...currentNote, status: newStatus, article_id: parseInt(articleId) };

            await saveNote(articleId, currentNote.note_text || '', newStatus);
        });
    });

    // Note toggle buttons
    document.querySelectorAll('.note-toggle-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const articleId = btn.closest('.note-actions').dataset.articleId;
            const area = document.querySelector(`[data-note-area="${articleId}"]`);
            area.classList.toggle('hidden');
            if (!area.classList.contains('hidden')) {
                area.querySelector('textarea').focus();
            }
        });
    });

    // Note textareas with debounce
    document.querySelectorAll('.note-textarea').forEach(textarea => {
        const articleId = textarea.dataset.noteInput;
        textarea.addEventListener('input', () => {
            clearTimeout(noteDebounceTimers[articleId]);
            noteDebounceTimers[articleId] = setTimeout(() => {
                const currentNote = articleNotes[articleId] || { status: 'none', note_text: '' };
                articleNotes[articleId] = { ...currentNote, note_text: textarea.value, article_id: parseInt(articleId) };
                saveNote(articleId, textarea.value, currentNote.status || 'none');
            }, 500);
        });
    });
}

async function saveNote(articleId, noteText, status) {
    try {
        await fetch(`/api/articles/${articleId}/note`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note_text: noteText, status }),
        });
    } catch {}
}

/* ═══════════════════════════════════════════
   ABSTRACT TOGGLE
   ═══════════════════════════════════════════ */
function bindAbstractToggles() {
    document.querySelectorAll('[data-abstract-toggle]').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.dataset.abstractToggle;
            const content = document.querySelector(`[data-abstract="${id}"]`);
            const isHidden = content.classList.contains('hidden');
            content.classList.toggle('hidden');
            btn.textContent = isHidden ? 'Hide Abstract' : 'Show Abstract';
        });
    });
}

/* ═══════════════════════════════════════════
   HISTORY
   ═══════════════════════════════════════════ */
async function loadHistory() {
    try {
        const resp = await fetch('/api/searches');
        if (!resp.ok) return;
        const list = await resp.json();
        historyList.innerHTML = '';
        for (const s of list) {
            const li = document.createElement('li');
            li.innerHTML = `
                <div class="history-item-row">
                    <div class="history-item-info">
                        <span class="search-id">#${s.id}</span>
                        <span class="query-text">${esc(s.original_query)}</span>
                        <span class="meta">${s.article_count} articles · ${fmtDate(s.created_at)}</span>
                    </div>
                    <button class="btn-delete-search" data-id="${s.id}" title="Delete search">&times;</button>
                </div>
            `;
            li.querySelector('.history-item-info').addEventListener('click', () => { closeDrawer(); loadSearch(s.id); });
            li.querySelector('.btn-delete-search').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (!confirm(`Delete search #${s.id}?`)) return;
                await deleteSearch(s.id);
                loadHistory();
                loadDashboard();
            });
            historyList.appendChild(li);
        }
    } catch {}
}

async function deleteSearch(id) {
    try {
        await fetch(`/api/search/${id}`, { method: 'DELETE' });
        if (currentSearchId === id) {
            report.classList.add('hidden');
            synthesisCard.classList.add('hidden');
            emptyState.classList.remove('hidden');
            currentSearchId = null;
        }
    } catch {}
}

async function loadSearch(id) {
    emptyState.classList.add('hidden');
    report.classList.add('hidden');
    synthesisCard.classList.add('hidden');
    showProgress('Loading...', -1);
    try {
        const r = await fetch(`/api/search/${id}`);
        if (!r.ok) throw new Error('Failed');
        hideProgress();
        showReport(await r.json());
    } catch (err) {
        hideProgress();
        report.classList.remove('hidden');
        resultsDiv.innerHTML = `<div class="no-results">${esc(err.message)}</div>`;
    }
}

/* ═══════════════════════════════════════════
   DASHBOARD
   ═══════════════════════════════════════════ */
async function loadDashboard() {
    try {
        const resp = await fetch('/api/stats');
        if (!resp.ok) return;
        const stats = await resp.json();

        if (stats.total_searches === 0) return;

        const dashboard = document.getElementById('dashboard');
        const emptyDefault = document.getElementById('empty-default');

        emptyDefault.classList.add('hidden');
        dashboard.classList.remove('hidden');

        // Sources for mini chart
        const srcLabels = [];
        const srcData = [];
        const srcColors = [];
        const srcBorderColors = [];
        const colorMap = {
            pubmed: { bg: '#d1fae5', border: '#059669', label: 'PubMed' },
            clinicaltrials: { bg: '#fef3c7', border: '#d97706', label: 'ClinicalTrials' },
            europepmc: { bg: '#dbeafe', border: '#2563eb', label: 'Europe PMC' },
        };
        for (const [key, count] of Object.entries(stats.sources)) {
            const c = colorMap[key] || { bg: '#f3f4f6', border: '#9ca3af', label: key };
            srcLabels.push(c.label);
            srcData.push(count);
            srcColors.push(c.bg);
            srcBorderColors.push(c.border);
        }

        let recentHtml = '';
        for (const s of stats.recent_searches) {
            recentHtml += `
                <li class="dash-search-item" data-id="${s.id}">
                    <div class="dash-item-info">
                        <span class="dash-search-id">#${s.id}</span>
                        <span class="dash-search-query">${esc(s.original_query)}</span>
                        <span class="dash-search-meta">${s.article_count} articles · ${fmtDate(s.created_at)}</span>
                    </div>
                    <button class="btn-delete-search btn-delete-dash" data-id="${s.id}" title="Delete search">&times;</button>
                </li>`;
        }

        dashboard.innerHTML = `
            <h2 class="dash-title">Dashboard</h2>
            <div class="dash-stats">
                <div class="dash-stat-card">
                    <div class="dash-stat-val">${stats.total_searches}</div>
                    <div class="dash-stat-label">Searches</div>
                </div>
                <div class="dash-stat-card">
                    <div class="dash-stat-val">${stats.total_articles}</div>
                    <div class="dash-stat-label">Articles</div>
                </div>
                <div class="dash-stat-card">
                    <div class="dash-stat-val">${stats.total_analyses}</div>
                    <div class="dash-stat-label">Analyses</div>
                </div>
                <div class="dash-stat-card">
                    <div class="dash-stat-val">${stats.avg_score}</div>
                    <div class="dash-stat-label">Avg Score</div>
                </div>
            </div>
            <div class="dash-bottom">
                <div class="dash-recent">
                    <h3>Recent Searches</h3>
                    <ul class="dash-search-list">${recentHtml}</ul>
                </div>
                <div class="dash-chart-wrap">
                    <h3>Articles by Source</h3>
                    <canvas id="dash-chart-sources" width="200" height="200"></canvas>
                </div>
            </div>`;

        // Bind recent search clicks
        dashboard.querySelectorAll('.dash-search-item').forEach(li => {
            li.querySelector('.dash-item-info').addEventListener('click', () => loadSearch(li.dataset.id));
            li.querySelector('.btn-delete-search').addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = parseInt(li.dataset.id);
                if (!confirm(`Delete search #${id}?`)) return;
                await deleteSearch(id);
                loadDashboard();
            });
        });

        // Mini doughnut
        if (srcData.length) {
            new Chart(document.getElementById('dash-chart-sources'), {
                type: 'doughnut',
                data: {
                    labels: srcLabels,
                    datasets: [{
                        data: srcData,
                        backgroundColor: srcColors,
                        borderColor: srcBorderColors,
                        borderWidth: 2,
                    }],
                },
                options: {
                    responsive: true,
                    cutout: '60%',
                    plugins: { legend: { position: 'bottom', labels: { padding: 10, font: { size: 11, weight: 700 }, usePointStyle: true, pointStyleWidth: 8 } } },
                },
            });
        }
    } catch {}
}

loadDashboard();

/* ═══════════════════════════════════════════
   HELPERS
   ═══════════════════════════════════════════ */
function showProgress(text, pct) {
    progress.classList.remove('hidden');
    progressText.textContent = text;
    if (pct >= 0) { progressBar.classList.remove('hidden'); progressFill.style.width = pct + '%'; }
    else progressBar.classList.add('hidden');
}

function hideProgress() { progress.classList.add('hidden'); progressBar.classList.add('hidden'); }

function fmtDate(s) {
    try { return new Date(s.includes('Z') ? s : s + 'Z').toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
    catch { return s; }
}

function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

loadHistory();

/* ═══════════════════════════════════════════
   SETTINGS
   ═══════════════════════════════════════════ */
const btnSettings = document.getElementById('btn-settings');
const settingsDrawer = document.getElementById('settings-drawer');
const settingsOverlay = document.getElementById('settings-overlay');
const settingsClose = document.getElementById('settings-close');
const settingsStatus = document.getElementById('settings-status');
const btnTestConnection = document.getElementById('btn-test-connection');
const btnSaveSettings = document.getElementById('btn-save-settings');
const providerDot = document.getElementById('provider-dot');
const providerNameEl = document.getElementById('provider-name');

const PROVIDER_LABELS = { claude: 'Claude', openai: 'OpenAI', ollama: 'Ollama' };

function openSettingsDrawer() {
    settingsDrawer.classList.remove('hidden');
    settingsOverlay.classList.remove('hidden');
    loadSettings();
}

function closeSettingsDrawer() {
    settingsDrawer.classList.add('hidden');
    settingsOverlay.classList.add('hidden');
    settingsStatus.classList.add('hidden');
}

btnSettings.addEventListener('click', openSettingsDrawer);
settingsClose.addEventListener('click', closeSettingsDrawer);
settingsOverlay.addEventListener('click', closeSettingsDrawer);

// Provider radio change
document.querySelectorAll('input[name="ai_provider"]').forEach(radio => {
    radio.addEventListener('change', () => {
        showProviderConfig(radio.value);
    });
});

function showProviderConfig(provider) {
    document.getElementById('config-claude').classList.toggle('hidden', provider !== 'claude');
    document.getElementById('config-openai').classList.toggle('hidden', provider !== 'openai');
    document.getElementById('config-ollama').classList.toggle('hidden', provider !== 'ollama');
}

function getSelectedProvider() {
    const checked = document.querySelector('input[name="ai_provider"]:checked');
    return checked ? checked.value : 'claude';
}

function collectSettingsFromForm() {
    return {
        ai_provider: getSelectedProvider(),
        claude_api_key: document.getElementById('set-claude-key').value,
        claude_model: document.getElementById('set-claude-model').value,
        openai_api_key: document.getElementById('set-openai-key').value,
        openai_model: document.getElementById('set-openai-model').value,
        ollama_base_url: document.getElementById('set-ollama-url').value,
        ollama_model: document.getElementById('set-ollama-model').value,
    };
}

function populateSettingsForm(settings) {
    const provider = settings.ai_provider || 'claude';
    const radio = document.querySelector(`input[name="ai_provider"][value="${provider}"]`);
    if (radio) radio.checked = true;
    showProviderConfig(provider);

    document.getElementById('set-claude-key').value = settings.claude_api_key || '';
    document.getElementById('set-claude-model').value = settings.claude_model || 'claude-sonnet-4-20250514';
    document.getElementById('set-openai-key').value = settings.openai_api_key || '';
    document.getElementById('set-openai-model').value = settings.openai_model || 'gpt-4o';
    document.getElementById('set-ollama-url').value = settings.ollama_base_url || 'http://localhost:11434';

    // Load Ollama models then select the saved one
    const savedOllamaModel = settings.ollama_model || '';
    loadOllamaModels(savedOllamaModel);
}

function showSettingsStatus(msg, type) {
    settingsStatus.textContent = msg;
    settingsStatus.className = 'settings-status ' + type;
    settingsStatus.classList.remove('hidden');
}

function updateProviderIndicator(provider) {
    providerDot.className = 'provider-dot ' + (provider || 'claude');
    providerNameEl.textContent = PROVIDER_LABELS[provider] || 'Claude';
}

const ollamaModelSelect = document.getElementById('set-ollama-model');
const ollamaModelsHint = document.getElementById('ollama-models-hint');
const btnRefreshModels = document.getElementById('btn-refresh-models');

async function loadOllamaModels(selectModel) {
    const baseUrl = document.getElementById('set-ollama-url').value || 'http://localhost:11434';
    const btn = btnRefreshModels;
    btn.classList.add('loading');
    ollamaModelsHint.classList.add('hidden');

    try {
        const resp = await fetch(`/api/settings/ollama-models?base_url=${encodeURIComponent(baseUrl)}`);
        const data = await resp.json();
        const models = data.models || [];

        ollamaModelSelect.innerHTML = '';

        if (models.length === 0) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = data.error ? '-- Connection failed --' : '-- No models installed --';
            ollamaModelSelect.appendChild(opt);
            ollamaModelsHint.textContent = data.error ? 'Cannot connect to Ollama' : 'No models found. Install with: ollama pull <model>';
            ollamaModelsHint.className = 'ollama-models-hint error';
            ollamaModelsHint.classList.remove('hidden');
        } else {
            for (const m of models) {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                ollamaModelSelect.appendChild(opt);
            }
            if (selectModel && models.includes(selectModel)) {
                ollamaModelSelect.value = selectModel;
            }
            ollamaModelsHint.textContent = `${models.length} model${models.length > 1 ? 's' : ''} found`;
            ollamaModelsHint.className = 'ollama-models-hint success';
            ollamaModelsHint.classList.remove('hidden');
        }
    } catch (err) {
        ollamaModelSelect.innerHTML = '<option value="">-- Error loading models --</option>';
        ollamaModelsHint.textContent = 'Failed to fetch models';
        ollamaModelsHint.className = 'ollama-models-hint error';
        ollamaModelsHint.classList.remove('hidden');
    } finally {
        btn.classList.remove('loading');
    }
}

btnRefreshModels.addEventListener('click', () => {
    loadOllamaModels(ollamaModelSelect.value);
});

async function loadSettings() {
    try {
        const resp = await fetch('/api/settings');
        if (!resp.ok) return;
        const settings = await resp.json();
        populateSettingsForm(settings);
        updateProviderIndicator(settings.ai_provider);
    } catch {}
}

btnSaveSettings.addEventListener('click', async () => {
    const settings = collectSettingsFromForm();
    showSettingsStatus('Saving...', 'loading');
    try {
        const resp = await fetch('/api/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ settings }),
        });
        if (!resp.ok) throw new Error('Save failed');
        showSettingsStatus('Settings saved successfully.', 'success');
        updateProviderIndicator(settings.ai_provider);
    } catch (err) {
        showSettingsStatus('Failed to save: ' + err.message, 'error');
    }
});

btnTestConnection.addEventListener('click', async () => {
    const settings = collectSettingsFromForm();
    const provider = settings.ai_provider;
    showSettingsStatus('Testing connection...', 'loading');
    try {
        const resp = await fetch('/api/settings/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, settings }),
        });
        const result = await resp.json();
        if (result.ok) {
            showSettingsStatus('Connection successful!', 'success');
        } else {
            showSettingsStatus('Connection failed: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (err) {
        showSettingsStatus('Test failed: ' + err.message, 'error');
    }
});

// Load provider indicator on page load
(async () => {
    try {
        const resp = await fetch('/api/settings');
        if (resp.ok) {
            const s = await resp.json();
            updateProviderIndicator(s.ai_provider);
        }
    } catch {}
})();
