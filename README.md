📊 Egyptian Tech Job Market Skill-Gap Analyzer  

Short description...

🌐 Live Dashboard  
Access the deployed interactive dashboard here:  
👉 [View Dashboard](https://skill-gap-analyzer-o7bhtsbwkmabwsxc54kczt.streamlit.app/)


🏛 Architecture Diagram
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
📁 Directory Structure
wuzzuf-skill-gap/
├── analysis/            # Pure functions: demand scoring, gap analysis, co-occurrence
├── config/              # Centralized configuration and skill taxonomy maps
├── dashboard/           # Streamlit app and Plotly visualizations
├── extraction/          # 3-Layer NLP extraction and token normalization
├── output/              # Cached CSVs, exported charts, state checkpoints
├── pipeline/            # Orchestration logic and resilient state manager
├── scraper/             # Selenium drivers, pagination handling, and requests
├── scripts/             # One-off scripts (e.g., threshold calibration)
├── tests/               # Pytest suite
├── main.py              # CLI Master Entry Point
└── requirements.txt     # Dependency definitions
🚀 Key Findings (Production Run)
Based on the latest production scrape, analyzing the Egyptian tech labor market yields the following insights:

Total Unique Jobs Analyzed: 4,293
Top Skill: Data Engineering stands out as a massive requirement, present in 39.9% of all unique listings.
Emerging Gap: Statistical Analysis is flashing a clear gap signal, showing 10.2% overall demand alongside a massive 2.0× seniority skew. Employers want seniors but aren't hiring juniors.
Highest Skew: GDPR Compliance is immensely heavily gated by experience, showing a 5.8× seniority skew.
🧠 Technical Highlights
Built with extreme resilience, our data extraction and analysis pipeline isn't just a basic scraper:

3-Layer NLP Extraction Pipeline
Structured Tags: Highest confidence capture (e.g., standard platform tags).
Regex Scanning: Fast parsing using word-boundary logic.
Fuzzy Fallback (RapidFuzz): Capturing typos, unique casing, and edge variances.
False-Positive Context Gating
A common issue in NLP is conflating generic terms with technical skills. To combat this, we inject a ±60-character context window boundary. For example, the system will actively suppress "Time Series Analysis" if it was triggered simply because a listing said "Full-Time" and "Analysis" somewhere nearby but lacked the explicit word "series".

Safe Math via Unique Identifiers
Demand percentage values represent critical market signals. To prevent raw pagination overlap or duplicate cross-posting bugs from inflating our datasets, calculating percentage denominator scopes strictly enforce nunique() across job_id.

🗄️ Data Flow & Outputs
The pipeline systematically translates raw scraped data into actionable intelligence:

Output Artifact	Purpose	Contains
raw_jobs.csv	Foundation data	Job titles, normalized URLs, raw post text, explicit categories
extracted_skills.csv	Normalized taxonomy	Processed job vs. canonical skill matrices and confidence levels
analytics_summary.csv	Mathematical scoring	Demand percentages, seniority multipliers, generated gap signals
cooccurrence_matrix.csv	Heatmap generation	N×N integer grid mapping skill intersections
💻 CLI Commands
Wuzzuf heavily leverages Cloudflare WAF capabilities, explicitly blocking rapid automated filtering. We adhere to these rules and utilize predefined category limits. Therefore, passing --query filters directly to the URL is disallowed.

These are the only valid execution modes:

# General CI Smoke Test to verify functionality
python main.py --test-mode

# Execute Full Production Scrape (Long running)
python main.py

# Reprocess all distinct jobs in local CSV data without scraping the web
python main.py --extract-and-analyze

# Recalculate metrics instantly based on existing extracted output
python main.py --analysis-only
(Note: Use --analysis-only instead of --analyze-only per our parser setup)