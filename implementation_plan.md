# Tech Job Market Skill-Gap Analyzer — Egypt

> **Target:** wuzzuf.net · **Stack:** Python + Selenium + BeautifulSoup4 + pandas + plotly
> **Goal:** Scrape tech job postings → extract skills → quantify demand → dashboard-ready output

---

## 1. Project Structure

```
wuzzuf-skill-gap/
├── config/
│   ├── settings.py              # All constants: URLs, delays, thresholds
│   ├── skill_taxonomy.py        # Master skill dictionary + alias map
│   └── user_agents.py           # Rotating User-Agent pool
│
├── scraper/
│   ├── __init__.py
│   ├── driver_manager.py        # Selenium driver lifecycle (init, teardown, cookie handling)
│   ├── listing_scraper.py       # Scrape search results pages (card-level data)
│   └── detail_scraper.py        # Scrape individual job detail pages (full description)
│
├── parser/
│   ├── __init__.py
│   ├── card_parser.py           # BeautifulSoup: parse job cards from listing HTML
│   └── detail_parser.py         # BeautifulSoup: parse job detail page HTML
│
├── extraction/
│   ├── __init__.py
│   ├── skill_extractor.py       # Regex + fuzzy matching skill extraction engine
│   └── normalizer.py            # Skill normalization, deduplication, alias resolution
│
├── analysis/
│   ├── __init__.py
│   ├── demand_scorer.py         # Skill frequency & demand scoring
│   ├── gap_analyzer.py          # Skill-gap signal detection
│   └── cooccurrence.py          # Skill co-occurrence matrix builder
│
├── visualization/
│   ├── __init__.py
│   └── dashboard.py             # Plotly chart generators (bar, heatmap, treemap)
│
├── pipeline/
│   ├── __init__.py
│   ├── orchestrator.py          # Main pipeline: scrape → parse → extract → analyze → viz
│   └── state_manager.py         # Checkpoint/resume logic (JSON state file)
│
├── output/
│   ├── raw_jobs.csv             # Raw scraped data
│   ├── extracted_skills.csv     # Normalized skill rows
│   ├── analytics_summary.csv   # Aggregated metrics for dashboard
│   ├── charts/                  # Exported HTML/PNG charts
│   └── state.json               # Scraper checkpoint state
│
├── tests/
│   ├── test_card_parser.py
│   ├── test_detail_parser.py
│   ├── test_skill_extractor.py
│   └── test_normalizer.py
│
├── requirements.txt
├── main.py                      # Entry point
└── README.md
```

### Design Rationale:
- **Separation of concerns** — scraping (Selenium), parsing (BS4), extraction (regex/NLP), and analysis (pandas) are fully decoupled.
- **Testability** — parsers and extractors can be unit-tested with saved HTML fixtures without hitting the network.
- **Resumability** — `state_manager.py` persists progress; a crash at page 47 resumes at page 47.

---

## 2. Dependencies & Setup

### `requirements.txt`

```
# === Browser Automation ===
selenium==4.27.1
undetected-chromedriver==3.5.5       # Cloudflare/WAF bypass (patches navigator.webdriver)

# === HTML Parsing ===
beautifulsoup4==4.12.3
lxml==5.3.0                          # Fast parser backend for BS4

# === Data Processing ===
pandas==2.2.3
numpy==1.26.4

# === Skill Extraction ===
rapidfuzz==3.10.1                    # Levenshtein fuzzy matching (C-optimized)

# === Visualization ===
plotly==5.24.1
kaleido==0.2.1                       # Static image export for Plotly

# === Utilities ===
python-dateutil==2.9.0               # Relative date parsing ("3 hours ago" → datetime)
fake-useragent==1.5.1                # User-Agent rotation pool
tqdm==4.67.1                         # Progress bars for long scrapes
tenacity==9.0.0                      # Retry decorator with backoff

# === Testing ===
pytest==8.3.4
```

> [!IMPORTANT]
> **Why `undetected-chromedriver`?** Wuzzuf is behind Cloudflare (confirmed via `robots.txt` — lines 30-63 show Cloudflare-managed content, blocking GPTBot, ClaudeBot, etc.). Standard Selenium is fingerprinted instantly. `undetected-chromedriver` patches the `navigator.webdriver` flag and randomizes the Chrome DevTools Protocol signature.

### Environment Setup

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

Chrome browser must be installed (undetected-chromedriver auto-downloads the matching chromedriver binary).

---

## 3. Scraping Strategy

### 3.1 Filtering for Tech Roles — URL-Based Category Approach

> [!NOTE]
> **Critical `robots.txt` finding:** The site explicitly `Disallow`s `/*?q=` and `/*filters` paths. However, the **pre-built category pages** under `/a/` are **fully allowed**. This is our primary access pattern.

**Target category URLs (verified live):**

| Category | URL | Est. Listings |
|---|---|---|
| IT/Software Development | `/a/IT-Software-Development-Jobs-in-Egypt` | ~3,400 |
| Engineering - Telecom/Technology | `/a/Engineering-Telecom-Technology-Jobs-in-Egypt` | ~800 |
| Analyst/Research (Data roles) | `/a/Analyst-Research-Jobs-in-Egypt` | ~400 |
| Creative/Design/Art (UI/UX subset) | `/a/Creative-Design-Art-Jobs-in-Egypt` | ~300 |

**Strategy:**
1. Iterate through each category URL above.
2. Within each category, paginate using the `?start=N` parameter.
3. After collecting card-level data from all listing pages, visit each **job detail URL** to get the full description, education, and salary fields.
4. Apply a **secondary title-based filter** in code to remove non-tech roles that leak into broad categories (e.g., "ICT Teacher" appearing under IT/Software Development).

### 3.2 Pagination Mechanics (Verified from Live DOM)

```
Base:   https://wuzzuf.net/a/IT-Software-Development-Jobs-in-Egypt
Page 1: https://wuzzuf.net/a/IT-Software-Development-Jobs-in-Egypt?start=0
Page 2: https://wuzzuf.net/a/IT-Software-Development-Jobs-in-Egypt?start=1
Page 3: https://wuzzuf.net/a/IT-Software-Development-Jobs-in-Egypt?start=2
...
Page N: https://wuzzuf.net/a/IT-Software-Development-Jobs-in-Egypt?start={N-1}
```

- **Results per page:** 20 jobs
- **Pagination indicator text:** `"Showing 1 - 20 of 3405"` — parse this to calculate `total_pages = ceil(total_results / 20)`
- **End-of-pagination signal:** When the page returns fewer than 20 job cards, or when the "Showing X - Y of Z" indicator shows Y == Z.

### 3.3 Selenium Driver Lifecycle

```
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 1: Driver Init (driver_manager.py)                       │
│  ─────────────────────────────────────────                       │
│  1. Launch undetected_chromedriver.Chrome()                      │
│     - headless=False for initial runs (detection evasion)        │
│     - Set window size to 1920×1080 (avoid mobile-viewport flag)  │
│  2. Set implicit wait = 10s                                      │
│  3. Inject randomized User-Agent from pool                       │
│  4. Navigate to first category URL                               │
│  5. Wait for Cloudflare challenge to auto-resolve (up to 15s)    │
│  6. Verify page loaded: check for job card container presence    │
└──────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 2: Listing Scrape Loop (listing_scraper.py)              │
│  ──────────────────────────────────────────────                  │
│  FOR each category_url IN target_categories:                     │
│    FOR page_num IN range(0, total_pages):                        │
│      1. Navigate to category_url?start={page_num}                │
│      2. WebDriverWait: presence_of_element_located(job card CSS) │
│         → Timeout: 15s, retry up to 3 times                     │
│      3. Random delay: uniform(2.0, 5.0) seconds                 │
│      4. ── HANDOFF ──                                            │
│         html = driver.page_source                                │
│         cards = card_parser.parse(html)  ← BeautifulSoup        │
│      5. Append cards to raw_jobs list                            │
│      6. Save checkpoint to state.json                            │
└──────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 3: Detail Scrape Loop (detail_scraper.py)                │
│  ──────────────────────────────────────────────                  │
│  FOR each job IN raw_jobs (where detail_scraped == False):       │
│    1. Navigate to job.detail_url                                 │
│    2. WebDriverWait: presence of description section             │
│    3. Random delay: uniform(3.0, 7.0) seconds  ← SLOWER         │
│    4. ── HANDOFF ──                                              │
│       html = driver.page_source                                  │
│       detail = detail_parser.parse(html)  ← BeautifulSoup       │
│    5. Merge detail fields into job record                        │
│    6. Save checkpoint every 10 jobs                              │
└──────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 4: Driver Teardown                                        │
│  ──────────────────────                                          │
│  1. driver.quit()                                                │
│  2. Final state.json update with completion timestamp            │
└──────────────────────────────────────────────────────────────────┘
```

### 3.4 Selenium → BeautifulSoup Handoff Protocol

The handoff is a **one-line bridge** that maximizes the strengths of both tools:

1. **Selenium** handles: JS rendering, Cloudflare bypass, cookie/session management, waiting for dynamic content.
2. **BeautifulSoup + lxml** handles: all HTML parsing (10-100x faster than Selenium's `find_element` calls).

**Handoff point:**
```
html_source = driver.page_source          # Selenium: capture fully-rendered DOM
soup = BeautifulSoup(html_source, 'lxml') # BS4: instant parse, zero network calls
```

> [!TIP]
> **Never use Selenium's `find_element()` for data extraction.** It's absurdly slow for batch parsing. Use it only for navigation, waits, and clicks. All field extraction goes through BS4.

### 3.5 Fields to Collect

**From Listing Page (card_parser.py):**

| Field | Source Element (verified from live DOM) |
|---|---|
| `job_title` | `<h2><a>` — the job title link text |
| `job_url` | `<h2><a href>` — full URL to detail page |
| `company_name` | Company text element (sibling of title, contains ` - ` separator before location) |
| `location` | Location text following company name separator (e.g., "Mansoura, Dakahlia, Egypt") |
| `posted_date_raw` | Relative time text (e.g., "34 minutes ago", "2 hours ago") |
| `job_type` | Tag chips: "Full Time" / "Part Time" / "Internship" |
| `work_mode` | Tag chips: "On-site" / "Remote" / "Hybrid" |
| `experience_level` | Text: "Entry Level" / "Experienced" / "Manager" / "Senior Management" |
| `category_tags` | Skill/category link texts (e.g., "· IT/Software Development", "· PL/SQL") |
| `source_category` | Which category URL this card was scraped from (metadata for dedup) |

**From Job Detail Page (detail_parser.py) — additional fields:**

| Field | Source Section (verified from live DOM) |
|---|---|
| `experience_range` | "Job Details" grid → "Experience Needed: 0 to 2 years" |
| `career_level` | "Job Details" grid → "Career Level: Entry Level (Junior Level / Fresh Grad)" |
| `education_level` | "Job Details" grid → "Education Level: Bachelor's Degree" |
| `salary_raw` | "Job Details" grid → "Salary: 6500 to 7000 EGP Per Month" (often hidden/absent) |
| `job_description` | Full text from "Job Description" section (HTML paragraphs + lists) |
| `job_requirements` | Full text from "Job Requirements" section |
| `skills_and_tools` | "Skills and Tools" chip texts (Wuzzuf's own tagging) |

---

## 4. Skill Extraction Strategy

### 4.1 Three-Layer Extraction Pipeline

```
Layer 1: Wuzzuf Tags       →  Extract from "Skills and Tools" chips (structured, high-confidence)
Layer 2: Taxonomy Match     →  Regex scan of job_description + job_requirements against skill dictionary
Layer 3: Fuzzy Fallback     →  RapidFuzz matching for variations missed by exact regex
```

### 4.2 Tech Skill Taxonomy (Predefined Dictionary)

```yaml
programming_languages:
  - Python, JavaScript, TypeScript, Java, C#, C++, Go, Rust, Kotlin, Swift,
    Ruby, PHP, Scala, R, Dart, SQL, Bash, PowerShell

frameworks_libraries:
  - React, Angular, Vue.js, Next.js, Node.js, Express.js, Django, Flask,
    FastAPI, Spring Boot, .NET, ASP.NET, Laravel, Ruby on Rails, Flutter,
    React Native, SwiftUI, Jetpack Compose, TensorFlow, PyTorch, scikit-learn,
    Pandas, NumPy, Spark, Hadoop

databases:
  - PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch, Cassandra, DynamoDB,
    Oracle DB, SQL Server, Neo4j, Firebase, SQLite, MariaDB

devops_cloud:
  - AWS, Azure, GCP, Docker, Kubernetes, Terraform, Ansible, Jenkins,
    GitHub Actions, GitLab CI, CircleCI, Nginx, Linux, Prometheus, Grafana,
    ArgoCD, Helm, Vault

data_ml_ai:
  - Machine Learning, Deep Learning, NLP, Computer Vision, LLM, RAG,
    MLOps, Data Engineering, ETL, Data Warehouse, Airflow, dbt, Snowflake,
    Databricks, Tableau, Power BI, Looker, Kafka

security:
  - Cybersecurity, Penetration Testing, SIEM, SOC, OWASP, ISO 27001,
    Network Security, Firewalls, IAM, Zero Trust, Encryption, Compliance

tools_practices:
  - Git, Jira, Confluence, Agile, Scrum, CI/CD, REST API, GraphQL,
    Microservices, gRPC, WebSocket, OAuth, JWT, Design Patterns, TDD,
    Code Review, System Design
```

### 4.3 Alias Normalization Map

Handle common variations that refer to the same canonical skill:

| Variations Found in Wild | Normalized To |
|---|---|
| `React.js`, `ReactJS`, `React JS`, `react` | **React** |
| `Node.js`, `NodeJS`, `Node JS`, `node` | **Node.js** |
| `Postgres`, `PostgreSQL`, `psql` | **PostgreSQL** |
| `k8s`, `Kubernetes`, `K8S` | **Kubernetes** |
| `Amazon Web Services`, `AWS` | **AWS** |
| `Google Cloud`, `GCP`, `Google Cloud Platform` | **GCP** |
| `MS SQL`, `MSSQL`, `SQL Server` | **SQL Server** |
| `C Sharp`, `C#`, `CSharp` | **C#** |
| `.NET Core`, `.NET`, `dotnet` | **.NET** |
| `ML`, `Machine Learning` | **Machine Learning** |
| `DL`, `Deep Learning` | **Deep Learning** |
| `CI/CD`, `CICD`, `CI CD` | **CI/CD** |

### 4.4 Extraction Algorithm

```
FOR each job:
  extracted_skills = set()

  # Layer 1: Structured tags (highest confidence)
  FOR tag IN job.skills_and_tools:
    canonical = alias_map.get(normalize(tag), tag)
    IF canonical IN taxonomy:
      extracted_skills.add(canonical)

  # Layer 2: Regex scan of description text
  combined_text = job.description + " " + job.requirements
  FOR skill IN taxonomy.all_skills():
    pattern = build_word_boundary_regex(skill)   # e.g., r'\bReact\b' (case-insensitive)
    IF regex.search(pattern, combined_text):
      extracted_skills.add(skill)

  # Layer 3: Fuzzy fallback for unmatched tokens
  tokens = tokenize(combined_text)               # split on whitespace + punctuation
  FOR token IN tokens:
    best_match, score = rapidfuzz.extractOne(token, taxonomy.all_skills())
    IF score >= 85:                               # threshold: 85% similarity
      extracted_skills.add(best_match)

  job.extracted_skills = list(extracted_skills)
```

> [!WARNING]
> **False-positive mitigation:** Words like "Spring" (season vs. framework) or "Go" (verb vs. language) need contextual gating. Only match single-word ambiguous terms when they appear near programming context indicators (e.g., "Spring Boot", "Golang", "Go language").

---

## 5. Skill-Gap Analysis Logic

### 5.1 Demand Scoring

```
demand_score(skill) = count(jobs mentioning skill) / total_jobs_in_segment

Segments:
  - Global (all tech jobs)
  - By role_category: "Backend", "Frontend", "Data Science", "DevOps", "Mobile", "QA", "Security"
  - By seniority: "Entry Level", "Experienced", "Manager", "Senior Management"
  - By city: "Cairo", "Giza", "Alexandria", "Other"
```

### 5.2 Role Category Classification

Map each job into a role category using title-based keyword rules:

| Role Category | Title Keywords |
|---|---|
| Backend | backend, server-side, API, microservices, java developer, python developer, .net developer |
| Frontend | frontend, front-end, UI developer, react developer, angular developer, vue |
| Full Stack | full stack, fullstack |
| Data Science / ML | data scientist, machine learning, ML engineer, AI engineer, data analyst |
| Data Engineering | data engineer, ETL, data pipeline, big data |
| DevOps / Cloud | devops, SRE, cloud engineer, infrastructure, platform engineer |
| Mobile | iOS, android, mobile developer, flutter, react native |
| QA / Testing | QA, test engineer, SDET, quality assurance, automation tester |
| Cybersecurity | security engineer, penetration tester, SOC analyst, cybersecurity |
| UI/UX (Technical) | UI/UX, UX developer, interaction designer (with code skills) |

### 5.3 Gap Signal Detection

A "skill gap" = high demand but projected low supply. Since we don't have supply-side data (candidate profiles), we use **proxy signals**:

```
gap_signal(skill) = {
  "demand_rank":     rank position in frequency list,
  "posting_trend":   is skill appearing in recent listings more than older ones? (if date data allows),
  "seniority_skew":  ratio of senior-level mentions vs entry-level mentions,
                     → high skew = organizations can't fill senior roles = likely gap,
  "salary_premium":  if salary data available, skills associated with higher salary ranges,
  "co_occurrence":   skills that always appear together → if one is rare, it's a gap
}
```

### 5.4 Output Metrics

| Metric | Description |
|---|---|
| **Top 20 Skills (Global)** | Most demanded skills across all tech listings |
| **Top 10 Skills per Role Category** | Within each category (Backend, Data, DevOps, etc.) |
| **Skill Demand by Seniority** | How demand shifts from Entry Level → Senior |
| **Skill Demand by City** | Geographic distribution of tech skill demand |
| **Skill Co-occurrence Matrix** | `N × N` matrix showing which skills appear together |
| **Emerging Gap Skills** | High seniority-skew + high demand = likely talent shortage |
| **Salary-Skill Correlation** | Skills associated with highest salary ranges (where salary data exists) |

---

## 6. Data Schema

### 6.1 Raw Jobs Table (`raw_jobs.csv`)

| Column | Type | Example | Notes |
|---|---|---|---|
| `job_id` | `str` | `ctuqvb0s7ymw` | Extracted from URL slug |
| `job_title` | `str` | `Junior Accountant` | Stripped, title-cased |
| `company_name` | `str` | `Dokkan Tech` | Stripped, trailing ` -` removed |
| `location_raw` | `str` | `Nasr City, Cairo, Egypt` | As-is from page |
| `city` | `str` | `Cairo` | Extracted from location_raw |
| `district` | `str` | `Nasr City` | Extracted from location_raw (nullable) |
| `posted_date_raw` | `str` | `2 hours ago` | Relative time as scraped |
| `posted_date` | `datetime` | `2026-04-15T18:00:00` | Computed: scrape_time - relative_offset |
| `scraped_at` | `datetime` | `2026-04-15T20:00:00` | Timestamp of scrape |
| `job_type` | `str` | `Full Time` | Enum: Full Time / Part Time / Internship / Contract |
| `work_mode` | `str` | `On-site` | Enum: On-site / Remote / Hybrid |
| `experience_level` | `str` | `Entry Level` | From card or detail page |
| `experience_years_min` | `int` | `0` | Parsed from "0 to 2 years" |
| `experience_years_max` | `int` | `2` | Parsed from "0 to 2 years" |
| `education_level` | `str` | `Bachelor's Degree` | From detail page (nullable) |
| `salary_min` | `float` | `6500.0` | Parsed from salary string (nullable) |
| `salary_max` | `float` | `7000.0` | Parsed from salary string (nullable) |
| `salary_currency` | `str` | `EGP` | Parsed (nullable) |
| `salary_period` | `str` | `Per Month` | Parsed (nullable) |
| `job_description` | `str` | `Key Responsibilities: ...` | Full text (nullable) |
| `job_requirements` | `str` | `Bachelor's degree in ...` | Full text (nullable) |
| `wuzzuf_skills_tags` | `str` | `Python,Django,REST API` | Comma-separated from chips |
| `category_tags` | `str` | `IT/Software Development,...` | Wuzzuf's category labels |
| `source_category` | `str` | `IT-Software-Development` | Which category URL we scraped this from |
| `job_url` | `str` | `https://wuzzuf.net/jobs/p/...` | Full canonical URL |
| `role_category` | `str` | `Backend` | Classified in analysis phase |

### 6.2 Extracted Skills Table (`extracted_skills.csv`)

One row per (job, skill) pair for easy aggregation:

| Column | Type | Example |
|---|---|---|
| `job_id` | `str` | `ctuqvb0s7ymw` |
| `skill_canonical` | `str` | `Python` |
| `skill_category` | `str` | `programming_languages` |
| `extraction_source` | `str` | `wuzzuf_tag` / `regex_match` / `fuzzy_match` |
| `confidence` | `float` | `1.0` / `0.95` / `0.87` |

### 6.3 Aggregated Analytics Table (`analytics_summary.csv`)

Pre-computed metrics ready for dashboard consumption:

| Column | Type | Example |
|---|---|---|
| `skill_canonical` | `str` | `Python` |
| `skill_category` | `str` | `programming_languages` |
| `total_mentions` | `int` | `847` |
| `demand_score` | `float` | `0.342` |
| `role_category` | `str` | `Backend` |
| `seniority_segment` | `str` | `Entry Level` |
| `city_segment` | `str` | `Cairo` |
| `avg_salary_min` | `float` | `12000.0` |
| `avg_salary_max` | `float` | `18000.0` |
| `seniority_skew` | `float` | `2.3` |
| `gap_signal_score` | `float` | `0.78` |

---

## 7. Error Handling & Resilience Strategy

### 7.1 Failure Scenarios & Mitigations

| Failure Type | Detection | Mitigation |
|---|---|---|
| **Cloudflare challenge** | Page body contains "Checking your browser" or no job cards found after 15s wait | Retry with fresh driver instance; switch User-Agent; add longer initial delay (30s) |
| **JS timeout** | `WebDriverWait` raises `TimeoutException` | Retry current page up to 3 times with exponential backoff (5s, 15s, 45s) |
| **HTTP 429 (Rate limit)** | Response status or Cloudflare block page | Pause for 120-300s; reduce crawl speed; rotate User-Agent |
| **Missing fields** | BS4 selector returns `None` | Set field to `None`; log warning; never crash on missing optional field |
| **Stale element** | `StaleElementReferenceException` | Re-fetch `page_source`; re-parse with BS4 |
| **Network error** | `WebDriverException`, connection reset | Retry with backoff; after 5 consecutive failures, pause 10 min then retry |
| **Pagination end** | Cards count < 20 or "Showing X - Y of Z" where Y >= Z | Stop pagination for this category; move to next |
| **Duplicate jobs** | Same `job_id` across categories | Deduplicate by `job_id` in the merge step; keep the first occurrence but merge category tags |

### 7.2 Checkpoint / Resume System (`state_manager.py`)

```json
// output/state.json — saved after every page
{
  "run_id": "20260415_205800",
  "status": "in_progress",
  "phase": "listing_scrape",
  "categories": {
    "IT-Software-Development": {
      "total_pages": 171,
      "last_completed_page": 47,
      "jobs_collected": 940,
      "status": "in_progress"
    },
    "Engineering-Telecom-Technology": {
      "total_pages": null,
      "last_completed_page": 0,
      "jobs_collected": 0,
      "status": "pending"
    }
  },
  "detail_scrape": {
    "total_jobs": 940,
    "last_completed_index": 0,
    "status": "pending"
  },
  "last_updated": "2026-04-15T21:23:00"
}
```

**Resume logic:** On startup, load `state.json`. Skip any category/page already marked complete. Resume from `last_completed_page + 1`.

### 7.3 Anti-Bot Mitigation Checklist

| Technique | Implementation |
|---|---|
| ✅ `undetected-chromedriver` | Patches `navigator.webdriver` and Chrome DevTools fingerprint |
| ✅ Random delays | `time.sleep(uniform(2.0, 5.0))` between listing pages; `uniform(3.0, 7.0)` between detail pages |
| ✅ User-Agent rotation | Pool of 15+ real Chrome User-Agent strings; rotated per category (not per page) |
| ✅ Non-headless mode | Run with `headless=False` initially; switch to `headless=True` only after confirming bypass works |
| ✅ Realistic viewport | `1920×1080` window — avoids fingerprint mismatch |
| ✅ Category pages, not search | Use `/a/` URLs (allowed by robots.txt) instead of `/search/jobs/?q=` (disallowed) |
| ✅ Session persistence | Reuse the same browser session across pages within a category (don't restart driver per page) |
| ✅ Rate throttling | No more than 1 request per 3 seconds average; built-in cooldown after every 50 pages |

---

## 8. Step-by-Step Execution Plan

> These are ordered, modular tasks for the coding agent to execute sequentially. Each task has a clear input, output, and acceptance criteria.

### Phase A: Foundation

| Step | Task | Output | Acceptance Criteria |
|---|---|---|---|
| **1** | Create project directory structure and `requirements.txt` | All folders and empty `__init__.py` files created | `pip install -r requirements.txt` succeeds with no errors |
| **2** | Implement `config/settings.py` with all constants (URLs, CSS selectors, delays, timeouts) and `config/user_agents.py` with User-Agent pool | Config files | All category URLs and timing constants are centralized; no magic numbers elsewhere |
| **3** | Implement `config/skill_taxonomy.py` with the full skill dictionary, alias map, and category groupings | Taxonomy module | `skill_taxonomy.get_all_skills()` returns 150+ unique skills; alias map covers 50+ variations |

---

### Phase B: Scraping Layer

| Step | Task | Output | Acceptance Criteria |
|---|---|---|---|
| **4** | Implement `scraper/driver_manager.py` — Selenium driver lifecycle (init with undetected-chromedriver, window sizing, teardown) | Working driver manager | Can open `wuzzuf.net/a/IT-Software-Development-Jobs-in-Egypt`, pass Cloudflare, and return `page_source` containing job card HTML |
| **5** | Implement `scraper/listing_scraper.py` — iterate categories, paginate with `?start=N`, hand off `page_source` to parser, save checkpoints | Raw listing HTML captured per page | Successfully paginates through at least 5 pages of IT/Software Development category; checkpoints saved to `state.json` |
| **6** | Implement `parser/card_parser.py` — BS4 parser that extracts all card-level fields from listing page HTML | List of job dicts per page | Unit test: given a saved HTML fixture, parser extracts correct title, company, location, posted_date, skills, and URL for all 20 cards |

---

### Phase C: Detail Scraping Layer

| Step | Task | Output | Acceptance Criteria |
|---|---|---|---|
| **7** | Implement `scraper/detail_scraper.py` — visit each job URL, wait for detail page load, hand off to detail parser | Detail HTML captured per job | Successfully loads 10 job detail pages with proper random delays; checkpoints updated |
| **8** | Implement `parser/detail_parser.py` — BS4 parser for detail page (description, requirements, salary, education, experience range, skills chips) | Enriched job dicts | Unit test: given a saved detail HTML fixture, parser extracts all "Job Details" grid fields + full description text + skills chips |

---

### Phase D: Skill Extraction & Normalization

| Step | Task | Output | Acceptance Criteria |
|---|---|---|---|
| **9** | Implement `extraction/normalizer.py` — text cleaning (strip whitespace, lowercase, alias resolution) and date normalization ("2 hours ago" → datetime) | Clean text + datetime | Unit test: `normalize("  React.JS ")` → `"React"`; `parse_relative_date("3 hours ago", now)` → correct datetime |
| **10** | Implement `extraction/skill_extractor.py` — three-layer extraction pipeline (Wuzzuf tags → regex → fuzzy) | `extracted_skills.csv` | Unit test: given a job description containing "Experience with React.js and Node", extractor returns `{"React", "Node.js"}`; ambiguous terms like "Go" only match with context |

---

### Phase E: Analysis & Visualization

| Step | Task | Output | Acceptance Criteria |
|---|---|---|---|
| **11** | Implement `analysis/demand_scorer.py`, `gap_analyzer.py`, and `cooccurrence.py` — aggregate skills by frequency, role, seniority, city; compute gap signals and co-occurrence matrix | `analytics_summary.csv` | Top 20 skills list is sensible (Python, JavaScript, SQL near top); co-occurrence matrix is symmetric and non-negative |
| **12** | Implement `visualization/dashboard.py` — generate Plotly charts (Top Skills bar chart, Skill-Category heatmap, Seniority progression, Co-occurrence heatmap, Gap signal treemap) | HTML charts in `output/charts/` | All 5 chart types render correctly; charts are interactive and export to HTML |

---

### Phase F: Integration & Pipeline

| Step | Task | Output | Acceptance Criteria |
|---|---|---|---|
| **13** | Implement `pipeline/orchestrator.py` — wire all modules together in the correct order: scrape listings → scrape details → merge & deduplicate → extract skills → analyze → visualize | `main.py` runs end-to-end | Full pipeline completes for at least one category (100+ jobs); all 3 CSV outputs generated; all charts rendered |
| **14** | Implement `pipeline/state_manager.py` — checkpoint save/load, resume logic, deduplication across categories | Crash-resistant pipeline | Test: kill pipeline mid-run, restart → resumes from last checkpoint without re-scraping completed pages |
| **15** | Write integration tests and run full pipeline on the IT/Software Development category | Test results + final output | All tests pass; `raw_jobs.csv` contains 1000+ rows; `extracted_skills.csv` contains 5000+ skill-job pairs; analytics are coherent |

---

## Open Questions

> [!IMPORTANT]
> **Depth vs. Speed tradeoff:** Scraping all ~4,900 tech jobs with detail pages at conservative delays (~5s per page + ~5s per detail page) will take approximately **10-14 hours**. Options:
> 1. **Full scrape:** All categories, all pages, all detail pages → most complete dataset
> 2. **Listing-only mode:** Skip detail pages, rely only on card-level data (title, skills tags, experience level) → **~2 hours**, but no description text, no salary, no education
> 3. **Sampled detail scrape:** Get all listing data, but only visit detail pages for a random 20% sample → **~4 hours**
>
> Which approach do you prefer?

> [!WARNING]
> **robots.txt compliance:** The `/a/` category pages are allowed, but the site's ToS may still restrict automated access. This plan uses category pages (not search queries) and conservative rate limiting to be as respectful as possible. Confirm you accept this approach before execution.
