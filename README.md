🇪🇬 Egyptian Tech Job Market — Skill-Gap AnalyzerAn end-to-end data engineering pipeline and interactive analytics dashboard that scrapes, normalizes, and quantifies tech labor market trends on Wuzzuf.net. This system identifies deep market trends, high-demand skills, and emerging talent gaps in the Egyptian tech sector.📌 Project OverviewThis project answers a single question:"What technical skills does the Egyptian job market actually demand — and where are the biggest gaps?"Built as a Big Data & Analysis college project, the pipeline collects real job postings, extracts skills through a three-layer NLP engine, scores demand across role categories, and surfaces "Gap Signals" where senior talent demand outpaces junior supply.📊 Production Snapshot (April 2026)MetricValueTotal Unique Jobs Analyzed4,293Unique Companies Hiring1,488Demand Threshold1.0%Seniority Skew Min1.5xAutomated Tests Passed38 / 38 ✅📝 Key FindingsBased on our production scrape and extraction analysis, the Egyptian tech market shows clear trends:The Infrastructure Shift: Data Engineering is the dominant force in the market, appearing in 39.9% of all analyzed tech postings.The "Emerging Gap" (Highest ROI): Statistical Analysis represents the most significant talent gap. With 10.2% demand and a 2.0x seniority skew, the market is heavily demanding mid/senior data practitioners but struggling to find them.The Compliance Shortage: GDPR Compliance shows the highest overall seniority skew (5.8x). While niche (1.9% demand), companies are exclusively hiring Seniors/Consultants for data privacy, indicating a severe expertise shortage.Architectural Maturity: Cloud-native skills like Event-Driven Architecture (13.7%) and Service Mesh (13.2%) are highly demanded, proving Egyptian firms are moving rapidly beyond traditional monolithic designs.🏛 Architecture & Data FlowPlaintext
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│                 │       │                 │       │                 │
│  Wuzzuf.net     │       │  Selenium + UC  │       │  BeautifulSoup  │
│  Category Pages ├──────►│  Scraping Layer ├──────►│  HTML Parser    │
│                 │       │  (Cloudflare ok)│       │                 │
└─────────────────┘       └─────────────────┘       └────────┬────────┘
                                                             │
┌─────────────────┐       ┌─────────────────┐       ┌────────▼────────┐
│                 │       │                 │       │                 │
│  Plotly / Flow  │       │  Pandas / Math  │       │  NLP Extractor  │
│  Dashboard UI   │◄──────┤  Analytics Hub  │◄──────┤  (3-Layer)      │
│                 │       │                 │       │                 │
└─────────────────┘       └─────────────────┘       └─────────────────┘
Output ArtifactPurposeContainsraw_jobs.csvFoundation dataJob titles, normalized URLs, raw post text, explicit categoriesextracted_skills.csvNormalized taxonomyProcessed job vs. canonical skill matrices and confidence levelsanalytics_summary.csvMathematical scoringDemand percentages, seniority multipliers, generated gap signalscooccurrence_matrix.csvHeatmap generationN×N integer grid mapping skill intersections📁 Directory StructurePlaintextwuzzuf-skill-gap/
├── analysis/            # Pure functions: demand scoring, gap analysis, co-occurrence
├── config/              # Centralized configuration and skill taxonomy maps
├── dashboard/           # Streamlit app and Plotly visualizations
├── extraction/          # 3-Layer NLP extraction and token normalization
├── output/              # Cached CSVs, exported charts, state checkpoints
├── pipeline/            # Orchestration logic and resilient state manager
├── scraper/             # Selenium drivers, pagination handling, and requests
├── tests/               # Pytest suite
├── main.py              # CLI Master Entry Point
└── requirements.txt     # Dependency definitions
🧠 Technical HighlightsBuilt with extreme resilience, our data extraction and analysis pipeline isn't just a basic scraper:1. The 3-Layer NLP Extraction EngineTo balance Precision and Recall, skills are extracted using a waterfall approach:Direct Tags (Conf: 1.0): Pulls Wuzzuf's explicit metadata.Taxonomy Regex (Conf: 0.95): Word-boundary scans for canonical skills.RapidFuzz Fallback (Conf: 0.85): Catches typos and aliases using fuzzy matching.2. False-Positive Context GatingA common issue in NLP is conflating generic terms with technical skills. To combat this, we inject a ±60-character context window boundary. For example, the system will actively suppress "Time Series Analysis" if it was triggered simply because a listing said "Full-Time" and "Analysis" somewhere nearby but lacked the explicit word "series".3. Absolute Math & Crash RecoveryDemand percentages are calculated using job_id.nunique() to ensure perfect denominators, even if the Wuzzuf pagination logic duplicates a listing mid-scrape.The scraper uses atomic os.replace JSON checkpoints. If the script crashes, it resumes from the exact page it left off.⚙️ Setup & InstallationPrerequisites: Python 3.10+, Google ChromeBashgit clone https://github.com/YOUR_USERNAME/wuzzuf-skill-gap.git
cd wuzzuf-skill-gap
python -m venv .venv

# Activate Virtual Environment
source .venv/bin/activate  # macOS / Linux
.venv\Scripts\activate     # Windows

pip install -r requirements.txt
cp .env.example .env
🚀 Running the PipelineWuzzuf heavily leverages Cloudflare WAF capabilities, explicitly blocking rapid automated filtering. We adhere to these rules and utilize predefined category limits. Therefore, passing --query filters directly to the URL is disallowed.Step 1 — CI Smoke Test (2 minutes)Validates the entire pipeline end-to-end on a 50-job limit.Bashpython main.py --test-mode
Step 2 — Full Production Scrape (3–5 hours)Collects raw HTML data and saves to output/raw_jobs.csv.Bashpython main.py
Step 3 — Reprocess Data (Extraction & Analysis)Bypasses the web scraper. Loads the local raw_jobs.csv and re-runs the heavy NLP extraction. Use this if you update the skill taxonomy or context-window logic.Bashpython main.py --extract-and-analyze
Step 4 — Recalculate Metrics (Instant)Bypasses scraping and extraction. Uses existing extracted_skills.csv to quickly recalculate Gap Signals.Bashpython main.py --analysis-only
📊 Streamlit Dashboard FeaturesLaunch the interactive UI with: streamlit run dashboard/streamlit_app.pyPage 1 · Overview: High-level KPIs and category distribution donut charts.Page 2 · Top Skills: Dynamic data table of the Top 20 skills by demand score.Page 3 · Skill Gap Analysis: The core analytical view featuring the "Emerging Gap Skills" table, Seniority Skew Bar Charts, and a Gap Signal Treemap.Page 4 · Co-occurrence: Interactive heatmap showing which technologies are frequently requested together.Page 5 · Raw Data Explorer: Searchable, filterable table of all scraped jobs for transparent data auditing.👥 The TeamThis college project was built collaboratively across three architectural groups:Group A (Data Collection): Scraping infra, Cloudflare bypass, and checkpointing.Group B (Intelligence): NLP extraction, Pandas scoring, and taxonomy mapping.Group C (Storytellers): Pipeline orchestration, Streamlit dashboard, and UI.📄 License: For academic purposes. Data scraped from Wuzzuf.net is used solely for non-commercial research and analysis.
