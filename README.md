# 🇪🇬 Egyptian Tech Job Market — Skill-Gap Analyzer

> An end-to-end data engineering pipeline and interactive analytics dashboard that scrapes, normalizes, and quantifies tech labor market trends from [Wuzzuf.net](https://wuzzuf.net) — identifying high-demand skills and emerging talent gaps in the Egyptian tech sector.
**🔴 [Live Dashboard: View the Interactive Data Here](https://skill-gap-analyzer-o7bhtsbwkmabwsxc54kczt.streamlit.app/)**
---

## 📌 Project Overview

This project answers a single question:

> **"What technical skills does the Egyptian job market actually demand — and where are the biggest gaps?"**

Built as a Big Data & Analysis college project, the pipeline collects real job postings, extracts skills through a three-layer NLP engine, scores demand across role categories and seniority levels, and surfaces **Gap Signals** — skills where senior talent demand significantly outpaces junior supply.

---

## 📊 Production Snapshot (April 2026)

| Metric | Value |
|---|---|
| Total Unique Jobs Analyzed | 4,293 |
| Unique Companies Hiring | 1,488 |
| Canonical Skills Tracked | 172 |
| Demand Score Threshold | 1.0% |
| Seniority Skew Minimum | 1.5× |
| Automated Tests Passed | 238 / 238 ✅ |

---

## 📝 Key Findings

> Based on production scrape of ~4,293 Egyptian tech job postings from Wuzzuf.net (April 2026).

**1. The Infrastructure Shift**
Data Engineering is the dominant force in the market, appearing in **39.9%** of all analyzed tech postings. Egyptian firms are no longer treating data as a by-product — they are actively building dedicated infrastructure for it.

**2. The Emerging Gap (Highest ROI for Job Seekers)**
Statistical Analysis represents the most significant talent gap. With **10.2% demand** and a **2.0× seniority skew**, the market is heavily demanding mid and senior-level data practitioners but struggling to find them — making it the highest-ROI skill for Egyptian CS graduates to develop.

**3. The Compliance Shortage**
GDPR Compliance shows the highest overall seniority skew at **5.8×**. While niche at 1.9% demand, companies are almost exclusively hiring senior consultants for data privacy roles, indicating a severe expertise shortage with virtually no entry-level pipeline.

**4. Architectural Maturity**
Cloud-native patterns like Event-Driven Architecture (13.7%) and Service Mesh (13.2%) rank among the most demanded skills — evidence that Egyptian firms are moving rapidly beyond traditional monolithic architectures toward distributed systems.

---

## 🏛️ Architecture & Data Flow

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│                 │       │                 │       │                 │
│  Wuzzuf.net     │       │  Selenium + UC  │       │  BeautifulSoup  │
│  Category Pages ├──────►│  Scraping Layer ├──────►│  HTML Parser    │
│                 │       │  (Cloudflare ✓) │       │                 │
└─────────────────┘       └─────────────────┘       └────────┬────────┘
                                                             │
┌─────────────────┐       ┌─────────────────┐       ┌────────▼────────┐
│                 │       │                 │       │                 │
│  Plotly /       │       │  Pandas /       │       │  NLP Extractor  │
│  Streamlit UI   │◄──────┤  Analytics Hub  │◄──────┤  (3-Layer)      │
│                 │       │                 │       │                 │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

**Design principle — strict separation of concerns:**

| Layer | Tool | Responsibility |
|---|---|---|
| Navigation & JS rendering | Selenium + undetected-chromedriver | Cloudflare bypass, pagination, session management |
| HTML parsing | BeautifulSoup4 + lxml | Pure function: HTML in → Python dicts out |
| Skill extraction | Regex + RapidFuzz | Three-layer NLP waterfall engine |
| Analysis | Pandas | Demand scoring, gap signals, co-occurrence matrix |
| Visualization | Plotly + Streamlit | Interactive dashboard |

Every module is independently testable, replaceable, and debuggable without touching any other layer.

---

## 📁 Directory Structure

```
wuzzuf-skill-gap/
├── config/
│   ├── settings.py              # All constants: URLs, delays, DEV_MODE flag
│   ├── skill_taxonomy.py        # 172 canonical skills + 175 aliases + role categories
│   └── user_agents.py           # Pool of 20 rotating Chrome User-Agent strings
│
├── scraper/
│   ├── driver_manager.py        # Selenium + undetected-chromedriver lifecycle
│   └── listing_scraper.py       # Pagination, category iteration, CSV flush, checkpoints
│
├── parser/
│   ├── card_parser.py           # Pure function: HTML → list[dict] (13 fields per job)
│   └── detail_parser.py         # Detail page parser (listing-only mode used in production)
│
├── extraction/
│   ├── skill_extractor.py       # Three-layer extraction engine + ambiguous term gating
│   └── normalizer.py            # Text cleaning, alias resolution, date normalization
│
├── analysis/
│   ├── demand_scorer.py         # Skill frequency + demand_score per segment
│   ├── gap_analyzer.py          # Seniority skew + gap_signal_score computation
│   └── cooccurrence.py          # N×N symmetric skill co-occurrence matrix
│
├── visualization/
│   └── dashboard.py             # Plotly chart generators (5 chart types → HTML + PNG)
│
├── pipeline/
│   ├── orchestrator.py          # Master pipeline: scrape → extract → analyze → viz
│   └── state_manager.py         # Atomic JSON checkpoint (temp-file swap, crash-safe)
│
├── dashboard/
│   └── streamlit_app.py         # Interactive 5-page Streamlit dashboard
│
├── output/
│   ├── raw_jobs.csv             # Raw scraped job data
│   ├── extracted_skills.csv     # One row per (job × skill) pair
│   ├── analytics_summary.csv    # Aggregated demand + gap metrics
│   ├── cooccurrence_matrix.csv  # N×N skill co-occurrence matrix
│   └── charts/                  # Exported HTML + PNG Plotly charts
│
├── tests/
│   ├── test_card_parser.py      # 53 tests
│   ├── test_extraction.py       # 107 tests
│   ├── test_analysis.py         # 60 tests
│   └── test_crash_recovery.py   # 18 tests
│
├── main.py                      # CLI master entry point
└── requirements.txt
```

---

## ⚙️ Setup & Installation

**Prerequisites:** Python 3.10+, Google Chrome (any recent version)

```bash
git clone https://github.com/YOUR_USERNAME/wuzzuf-skill-gap.git
cd wuzzuf-skill-gap

python -m venv .venv
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows

pip install -r requirements.txt
cp .env.example .env
```

> `undetected-chromedriver` automatically downloads the matching ChromeDriver binary on first run. No manual ChromeDriver installation needed.

---

## 🚀 Running the Pipeline

> **Note on robots.txt compliance:** Wuzzuf blocks automated access via search query URLs (`/*?q=`). This pipeline exclusively uses the pre-built `/a/` category pages which are fully permitted. Passing `--query` filters directly to the URL is intentionally not supported.

### Step 1 — CI Smoke Test (~2 minutes)

Validates the entire pipeline end-to-end on a 50-job limit before committing to the full run.

```bash
python main.py --test-mode
```

### Step 2 — Full Production Scrape (~3–5 hours)

Scrapes all category pages and writes raw data to `output/raw_jobs.csv`. A Chrome window will open — **do not close it.** The Cloudflare bypass requires a real browser session.

```bash
python main.py --reset   # clear previous checkpoint
python main.py           # start full scrape
```

If interrupted at any point, simply re-run `python main.py` — the pipeline resumes from the last saved checkpoint without re-scraping any completed pages.

### Step 3 — Reprocess Data (Extraction & Analysis)

Bypasses the scraper entirely. Loads the existing `raw_jobs.csv` and re-runs NLP extraction. Use this after updating the skill taxonomy or context-gating logic.

```bash
python main.py --extract-and-analyze
```

### Step 4 — Recalculate Metrics Only (Instant)

Bypasses scraping and extraction. Uses the existing `extracted_skills.csv` to instantly recalculate demand scores and gap signals.

```bash
python main.py --analysis-only
```

---

## 📊 Streamlit Dashboard

If you are developing locally and want to visualize newly generated data before pushing changes to production:
```bash
streamlit run dashboard/streamlit_app.py
```

Launch the interactive UI directly in your browser: **[Open Streamlit Dashboard](https://skill-gap-analyzer-o7bhtsbwkmabwsxc54kczt.streamlit.app/)**

| Page | What It Shows |
|---|---|
| **1 · Overview** | KPI cards (jobs, skills, companies, date range) + category donut chart + role breakdown |
| **2 · Top Skills** | Top 20 skills by demand score, filterable by role category, color-coded by skill category |
| **3 · Skill Gap Analysis** | Emerging gap skills table + seniority skew bar chart + demand vs skew scatter plot + gap treemap |
| **4 · Co-occurrence** | Interactive heatmap of skills that appear together (adjustable slider: 10–50 skills) + top pairs table |
| **5 · Raw Data Explorer** | Full searchable job table with city / work mode / job type / experience filters + CSV export |

---

## 🧠 Technical Highlights

### 1. Three-Layer NLP Extraction Engine

Skills are extracted through a waterfall pipeline that balances precision and recall:

| Layer | Method | Confidence | Description |
|---|---|---|---|
| **Layer 1** | Structured Tags | 1.0 | Pulls Wuzzuf's explicit `Skills and Tools` metadata directly |
| **Layer 2** | Taxonomy Regex | 0.95 | Word-boundary regex scan against 172 canonical skills (case-insensitive) |
| **Layer 3** | RapidFuzz Fallback | 0.85–0.99 | Catches typos and aliases; threshold: 85% weighted similarity score |

### 2. False-Positive Context Gating

A common NLP pitfall is conflating generic words with technical terms. This pipeline injects a **±60-character context window** around each candidate match. For example, "Time Series Analysis" is suppressed if triggered by "Full-Time" and "Analysis" appearing separately in a listing — the word "series" must appear within the immediate context window to confirm the match.

Ambiguous single-word terms (`Go`, `Spring`, `C`, `R`, `Rust`, `Vault`) are additionally gated by predefined programming context indicators and will not match without corroborating evidence.

### 3. Accurate Demand Denominators

Demand percentages are calculated using `job_id.nunique()` as the denominator rather than raw row counts. This guarantees mathematically correct percentages even when Wuzzuf's pagination logic surfaces a duplicate listing mid-scrape.

### 4. Atomic Crash Recovery

The state manager writes checkpoints via `os.replace()` — a complete temp file is written first, then atomically swapped in. This guarantees the checkpoint is never left in a corrupt half-written state, even if the process is killed mid-write.

---

## 🔍 Skill Gap Methodology

A **Gap Skill** = high market demand paired with low supply of qualified candidates.

Since candidate profile data is unavailable from the supply side, the pipeline uses **seniority skew** as a proxy signal:

```
seniority_skew(skill) = senior_level_mentions / entry_level_mentions
```

A skill with **high demand AND high seniority skew** signals that organizations urgently need it but cannot find junior candidates who have it — the definition of a talent gap.

```
gap_signal_score = normalize(demand_rank) × normalize(seniority_skew)
is_emerging_gap  = gap_signal_score > threshold  AND  seniority_skew ≥ 1.5×
```

---

## 🗃️ Output Data Schema

### `raw_jobs.csv` — one row per job posting

| Column | Type | Example |
|---|---|---|
| `job_id` | str | `ctuqvb0s7ymw` |
| `job_title` | str | `Senior Python Backend Developer` |
| `company_name` | str | `Breadfast` |
| `city` | str | `Cairo` |
| `work_mode` | str | `Hybrid` |
| `experience_level` | str | `Experienced` |
| `job_type` | str | `Full Time` |
| `category_tags` | str | `Python,Django,Docker` |
| `posted_date` | datetime | `2026-04-14T18:00:00` |

### `extracted_skills.csv` — one row per (job × skill) pair

| Column | Type | Example |
|---|---|---|
| `job_id` | str | `ctuqvb0s7ymw` |
| `skill_canonical` | str | `Python` |
| `skill_category` | str | `programming_languages` |
| `role_category` | str | `Backend` |
| `extraction_source` | str | `wuzzuf_tag` / `regex_match` / `fuzzy_match` |
| `confidence` | float | `1.0` |

### `analytics_summary.csv` — pre-aggregated metrics

| Column | Type | Example |
|---|---|---|
| `segment_type` | str | `global` / `role` / `seniority` / `city` |
| `skill_canonical` | str | `Docker` |
| `demand_score` | float | `0.399` |
| `seniority_skew` | float | `2.0` |
| `gap_signal_score` | float | `0.78` |
| `is_emerging_gap` | bool | `True` |

---

## 🛡️ Scraping Ethics & robots.txt Compliance

Wuzzuf's `robots.txt` explicitly disallows `/*?q=` search paths and `/*filters` URLs. This project **only accesses the pre-built `/a/` category pages** which are fully permitted:

```
/a/IT-Software-Development-Jobs-in-Egypt
/a/Engineering-Telecom-Technology-Jobs-in-Egypt
/a/Analyst-Research-Jobs-in-Egypt
/a/Creative-Design-Art-Jobs-in-Egypt
```

**Rate limiting measures:**
- Random delay `uniform(2.0, 5.0)s` between every page request
- 30-second cooldown after every 50 pages
- ~1 request per 3.5 seconds average
- Browser session reused within categories — no driver restart per page

---

## 🧪 Test Suite

```bash
pytest tests/ -v
```

| Suite | Tests | Coverage |
|---|---|---|
| `test_card_parser.py` | 53 | BS4 parsing, missing fields, malformed HTML edge cases |
| `test_extraction.py` | 107 | All 3 extraction layers, alias resolution, ambiguous term gating, context windows |
| `test_analysis.py` | 60 | Demand scoring, seniority skew, zero-division edge cases, symmetric co-occurrence |
| `test_crash_recovery.py` | 18 | Checkpoint save/load, mid-run resume, deduplication across categories |
| **Total** | **238 / 238 ✅** | |

---

## 📦 Dependencies

```
selenium==4.27.1
undetected-chromedriver==3.5.5
beautifulsoup4==4.12.3
lxml==5.3.0
pandas==2.2.3
numpy==1.26.4
rapidfuzz==3.10.1
plotly==5.24.1
kaleido==0.2.1
streamlit>=1.32.0
python-dateutil==2.9.0
fake-useragent==1.5.1
tqdm==4.67.1
tenacity==9.0.0
pytest==8.3.4
```

---

## 👥 Team

This project was built collaboratively across three architectural groups:

| Group | Role | Responsibility |
|---|---|---|
| **Group A — The Scrapers** | Data Collection | Selenium scraper, Cloudflare bypass, pagination, atomic checkpointing |
| **Group B — The AI Brains** | Intelligence | Pandas data cleaning, three-layer NLP extraction, taxonomy mapping, gap scoring |
| **Group C — The Storytellers** | Systems & Dashboard | Pipeline orchestration, Streamlit dashboard, insights and final presentation |

---

## 📄 License

For academic purposes only. Data scraped from Wuzzuf.net is used solely for non-commercial research and analysis.
