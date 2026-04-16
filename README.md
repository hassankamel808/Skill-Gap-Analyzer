# Wuzzuf Skill Gap Analyzer 📈

> **End-to-end data pipeline** that scrapes tech job postings from [Wuzzuf.net](https://wuzzuf.net), extracts technical skills using NLP (Regex + Fuzzy Matching), and visualises market demand vs. seniority gaps in an interactive Streamlit dashboard.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Repository Structure](#repository-structure)
3. [Technical Stack](#technical-stack)
4. [Quick Start](#quick-start)
5. [Pipeline Modes](#pipeline-modes)
6. [Configuration](#configuration)
7. [Skill Taxonomy](#skill-taxonomy)
8. [Dashboard](#dashboard)
9. [Testing](#testing)
10. [Output Artefacts](#output-artefacts)
11. [Extending the Project](#extending-the-project)
12. [Contributing](#contributing)
13. [License](#license)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Wuzzuf Skill Gap Analyzer                         │
│                                                                          │
│  ┌────────────┐    ┌────────────┐    ┌─────────────┐    ┌────────────┐  │
│  │  Scraper   │───▶│   Parser   │───▶│ Extraction  │───▶│  Analysis  │  │
│  │            │    │            │    │             │    │            │  │
│  │ Selenium + │    │ BS4 HTML   │    │ Regex + NLP │    │ Demand /   │  │
│  │ uc-driver  │    │ card parse │    │ Fuzzy Match │    │ Gap / Cooc │  │
│  └────────────┘    └────────────┘    └─────────────┘    └─────┬──────┘  │
│         │                                                       │        │
│         ▼                                                       ▼        │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Pipeline / Orchestrator                       │    │
│  │   StateManager (atomic JSON checkpoints)  ·  CLI (Click/Rich)   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│                                    ▼                                     │
│                         ┌──────────────────┐                            │
│                         │  output/  (CSV,  │                            │
│                         │  JSON artefacts) │                            │
│                         └────────┬─────────┘                            │
│                                  │                                       │
│                                  ▼                                       │
│                    ┌─────────────────────────────┐                      │
│                    │  Streamlit Dashboard (5-page)│                      │
│                    └─────────────────────────────┘                      │
└──────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

| Stage | Module | Description |
|-------|--------|-------------|
| **Scrape** | `scraper/` | Undetected Chrome driver paginates Wuzzuf, fetches raw HTML |
| **Parse** | `parser/` | BeautifulSoup 4 extracts structured fields from each job card |
| **Extract** | `extraction/` | Regex + RapidFuzz fuzzy matching maps free text → canonical skills |
| **Analyse** | `analysis/` | Demand scoring, seniority gap detection, co-occurrence matrix |
| **Persist** | `pipeline/` | Atomic JSON checkpoints + CSV/JSON output artefacts |
| **Visualise** | `dashboard/` | 5-page interactive Streamlit dashboard with Plotly charts |

---

## Repository Structure

```
Skill-Gap-Analyzer/
│
├── config/                     # Centralised configuration
│   ├── __init__.py
│   ├── settings.py             # Pydantic-Settings env config
│   ├── skill_taxonomy.py       # 200+ skills with alias mappings
│   └── user_agents.py          # Rotating User-Agent pool
│
├── scraper/                    # Web scraping layer
│   ├── __init__.py
│   ├── driver_manager.py       # Selenium / undetected-chromedriver lifecycle
│   └── listing_scraper.py      # Pagination logic
│
├── parser/                     # HTML parsing layer
│   ├── __init__.py
│   └── card_parser.py          # BS4 job-card extractor + seniority inference
│
├── extraction/                 # NLP / skill extraction
│   ├── __init__.py
│   ├── skill_extractor.py      # Regex + fuzzy matching + context-window gating
│   └── normalizer.py           # Unicode / case / whitespace normalisation
│
├── analysis/                   # Analytics layer
│   ├── __init__.py
│   ├── demand_scorer.py        # Market demand scores (min-max normalised)
│   ├── gap_analyzer.py         # Seniority skew detection
│   └── cooccurrence.py         # Pairwise skill co-occurrence
│
├── pipeline/                   # Orchestration & state
│   ├── __init__.py
│   ├── orchestrator.py         # Master workflow (Scrape / Analysis-Only mode)
│   └── state_manager.py        # Atomic JSON checkpoint read/write
│
├── dashboard/                  # Streamlit dashboard
│   ├── __init__.py
│   └── streamlit_app.py        # 5-page interactive Plotly/Streamlit dashboard
│
├── tests/                      # pytest test suite
│   ├── __init__.py
│   ├── test_parser.py          # CardParser unit tests
│   └── test_extraction.py      # Normalizer + SkillExtractor unit tests
│
├── output/                     # Generated data artefacts (gitignored)
│   └── .gitkeep
│
├── main.py                     # CLI entry point (Click + Rich)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Technical Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Web Scraping | Selenium 4, undetected-chromedriver |
| HTML Parsing | BeautifulSoup 4, lxml |
| Data | Pandas, NumPy |
| NLP / Fuzzy | RapidFuzz |
| Config | Pydantic-Settings, python-dotenv |
| Visualisation | Plotly, Streamlit |
| CLI | Click, Rich |
| Testing | pytest, pytest-cov |

---

## Quick Start

### 1. Clone & set up virtual environment

```bash
git clone https://github.com/hassankamel808/Skill-Gap-Analyzer.git
cd Skill-Gap-Analyzer

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your preferred settings
```

### 3. Run the full pipeline (scrape + analyse)

```bash
python main.py --extract-and-analyze --query "data engineer" --max-pages 30
```

### 4. Launch the dashboard

```bash
streamlit run dashboard/streamlit_app.py
```

---

## Pipeline Modes

The pipeline supports three execution modes, selectable via CLI flags:

### Scrape Mode

Runs the full web scraping + skill extraction pipeline:

```bash
python main.py --scrape --query "machine learning engineer" --max-pages 20
```

- Launches a headless Chrome instance with randomised User-Agent rotation.
- Paginates through Wuzzuf search results up to `--max-pages`.
- Parses each job card and extracts skills using the two-stage NLP extractor.
- Saves progress to a JSON checkpoint after every page (safe to interrupt and resume).
- Outputs `output/raw_jobs.csv` and `output/raw_jobs.json`.

### Analysis-Only Mode

Runs analytics on previously scraped data (no browser required):

```bash
python main.py --analyze
```

- Reads `output/raw_jobs.json` (or `.csv` fallback).
- Computes demand scores, seniority gap flags, and co-occurrence pairs.
- Outputs `output/demand_scores.csv`, `output/gap_analysis.csv`, `output/cooccurrence_top_pairs.csv`.

### Test Mode

Caps the scraper at one page — ideal for CI/CD smoke tests:

```bash
python main.py --scrape --test-mode
```

---

## Configuration

All settings are managed via Pydantic-Settings in `config/settings.py`.
Values are read from environment variables or the `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `WUZZUF_BASE_URL` | `https://wuzzuf.net/search/jobs/` | Search endpoint |
| `SCRAPE_MAX_PAGES` | `50` | Max pages per run |
| `SCRAPE_HEADLESS` | `true` | Headless Chrome |
| `SCRAPE_REQUEST_DELAY_SECONDS` | `2.5` | Polite delay between requests |
| `OUTPUT_DIR` | `output` | Directory for CSV/JSON artefacts |
| `STATE_FILE` | `pipeline/state/checkpoint.json` | Checkpoint path |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `FUZZY_MATCH_THRESHOLD` | `85` | RapidFuzz score threshold (0–100) |
| `CONTEXT_WINDOW_TOKENS` | `6` | Token radius for negation gating |

---

## Skill Taxonomy

`config/skill_taxonomy.py` contains a curated dictionary of **200+ technical skills** organised by domain:

- Programming Languages (Python, JavaScript, TypeScript, Go, …)
- Web Frameworks (Django, FastAPI, React, Angular, …)
- Data Engineering (Spark, Kafka, Airflow, dbt, …)
- Databases (PostgreSQL, MongoDB, Snowflake, BigQuery, …)
- Cloud Platforms & Services (AWS, GCP, Azure, …)
- DevOps & Infrastructure (Docker, Kubernetes, Terraform, …)
- ML & AI (TensorFlow, PyTorch, LLMs, RAG, …)
- Data Analysis & Visualisation (Pandas, Plotly, Tableau, …)
- Streaming & Messaging (Kafka, Kinesis, Pub/Sub, …)
- Security, Testing, and Soft/Process skills

Each canonical skill maps to a list of known aliases/abbreviations used by the fuzzy-matching extractor.

---

## Dashboard

The Streamlit dashboard (`dashboard/streamlit_app.py`) provides five interactive pages:

| Page | Description |
|------|-------------|
| **📊 Overview** | KPI cards (total jobs, unique skills, companies, locations) + seniority pie chart + top locations bar chart |
| **🔥 Demand Heatmap** | Horizontal bar chart of top-N skills ranked by normalised demand score |
| **🎯 Gap Analysis** | Heatmap of seniority-skill skew; flags skills disproportionately concentrated in one seniority tier |
| **🕸 Co-occurrence** | Bubble chart of the most frequently co-occurring skill pairs |
| **🔍 Job Explorer** | Searchable, filterable table of raw job postings |

```bash
streamlit run dashboard/streamlit_app.py
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=. --cov-report=term-missing
```

The test suite covers:
- `CardParser` HTML parsing, seniority inference, and edge cases.
- `normalize_skill`, `normalize_text`, and `clean_job_text` normalisation helpers.
- `SkillExtractor` exact matching, negation gating, deduplication, and output format.

---

## Output Artefacts

| File | Content |
|------|---------|
| `output/raw_jobs.csv` | Structured job postings (title, company, location, seniority, skills) |
| `output/raw_jobs.json` | Same data in JSON format |
| `output/demand_scores.csv` | Skill → raw_count, demand_score, pct_of_postings |
| `output/gap_analysis.csv` | Skill × Seniority → count, skew, gap_flag |
| `output/cooccurrence_top_pairs.csv` | Top co-occurring skill pairs with counts |

---

## Extending the Project

- **Add new skills**: Extend `config/skill_taxonomy.py` with new canonical names and aliases.
- **Support new job boards**: Create a new scraper module following the `ListingScraper` interface.
- **Custom analysis**: Add new analyser classes to `analysis/` following the `DemandScorer` pattern.
- **New dashboard pages**: Add a new function to `dashboard/streamlit_app.py` and register it in `_PAGE_MAP`.
- **Scheduled runs**: Wrap `Orchestrator.run()` in an Airflow DAG or a cron job.

---

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`.
3. Commit your changes with a clear message.
4. Push and open a Pull Request.

Please ensure all tests pass before submitting a PR:

```bash
pytest tests/ -v
```

---

## License

[MIT](LICENSE)