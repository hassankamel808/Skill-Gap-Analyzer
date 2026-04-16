"""
dashboard/streamlit_app.py
──────────────────────────
5-page interactive Streamlit dashboard for the Wuzzuf Skill Gap Analyzer.

Pages
─────
1. 📊 Overview          – KPI cards + dataset summary
2. 🔥 Demand Heatmap    – Top-N skills ranked by demand score
3. 🎯 Gap Analysis      – Seniority-level skill skew heatmap
4. 🕸  Co-occurrence     – Skill co-occurrence bubble / network chart
5. 🔍 Job Explorer      – Searchable raw job posting table

Run
───
    streamlit run dashboard/streamlit_app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Wuzzuf Skill Gap Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("output")
RAW_JSON = OUTPUT_DIR / "raw_jobs.json"
RAW_CSV = OUTPUT_DIR / "raw_jobs.csv"
DEMAND_CSV = OUTPUT_DIR / "demand_scores.csv"
GAP_CSV = OUTPUT_DIR / "gap_analysis.csv"
COOC_CSV = OUTPUT_DIR / "cooccurrence_top_pairs.csv"


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Loading job data…")
def load_raw_jobs() -> pd.DataFrame:
    if RAW_JSON.exists():
        records = json.loads(RAW_JSON.read_text(encoding="utf-8"))
        df = pd.DataFrame(records)
    elif RAW_CSV.exists():
        df = pd.read_csv(RAW_CSV)
    else:
        return pd.DataFrame()
    if "skills" in df.columns and df["skills"].dtype == object:
        df["skills"] = df["skills"].apply(
            lambda x: json.loads(x) if isinstance(x, str) else x
        )
    return df


@st.cache_data(show_spinner="Loading demand scores…")
def load_demand() -> pd.DataFrame:
    return pd.read_csv(DEMAND_CSV) if DEMAND_CSV.exists() else pd.DataFrame()


@st.cache_data(show_spinner="Loading gap analysis…")
def load_gap() -> pd.DataFrame:
    return pd.read_csv(GAP_CSV) if GAP_CSV.exists() else pd.DataFrame()


@st.cache_data(show_spinner="Loading co-occurrence data…")
def load_cooc() -> pd.DataFrame:
    return pd.read_csv(COOC_CSV) if COOC_CSV.exists() else pd.DataFrame()


# ── Sidebar navigation ────────────────────────────────────────────────────────

PAGES = [
    "📊 Overview",
    "🔥 Demand Heatmap",
    "🎯 Gap Analysis",
    "🕸 Co-occurrence",
    "🔍 Job Explorer",
]

with st.sidebar:
    st.title("Wuzzuf Skill Gap Analyzer")
    st.caption("End-to-end data pipeline · Streamlit dashboard")
    selected_page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.divider()
    st.markdown("**Data location:** `output/`")
    if st.button("🔄 Refresh data cache"):
        st.cache_data.clear()
        st.rerun()


# ── Page 1: Overview ──────────────────────────────────────────────────────────

def page_overview() -> None:
    st.header("📊 Overview")
    df = load_raw_jobs()

    if df.empty:
        st.warning(
            "No data found.  Run the pipeline first:\n\n"
            "```bash\npython main.py --scrape\n```"
        )
        return

    total_jobs = len(df)
    total_skills = df["skills"].explode().nunique() if "skills" in df.columns else 0
    companies = df["company"].nunique() if "company" in df.columns else 0
    locations = df["location"].nunique() if "location" in df.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Job Postings", f"{total_jobs:,}")
    col2.metric("Unique Skills Detected", f"{total_skills:,}")
    col3.metric("Unique Companies", f"{companies:,}")
    col4.metric("Unique Locations", f"{locations:,}")

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        if "seniority" in df.columns:
            seniority_counts = df["seniority"].value_counts().reset_index()
            seniority_counts.columns = ["seniority", "count"]
            fig = px.pie(
                seniority_counts,
                names="seniority",
                values="count",
                title="Seniority Distribution",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        if "location" in df.columns:
            top_locations = df["location"].value_counts().head(10).reset_index()
            top_locations.columns = ["location", "count"]
            fig = px.bar(
                top_locations,
                x="count",
                y="location",
                orientation="h",
                title="Top 10 Locations",
                color="count",
                color_continuous_scale="Blues",
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)


# ── Page 2: Demand Heatmap ────────────────────────────────────────────────────

def page_demand_heatmap() -> None:
    st.header("🔥 Skill Demand Heatmap")
    demand_df = load_demand()

    if demand_df.empty:
        st.warning("No demand data found. Run `python main.py --analyze` first.")
        return

    top_n = st.slider("Top N skills", min_value=10, max_value=100, value=30, step=5)
    df_top = demand_df.head(top_n)

    fig = px.bar(
        df_top,
        x="demand_score",
        y="skill",
        orientation="h",
        color="demand_score",
        color_continuous_scale="Viridis",
        title=f"Top {top_n} Skills by Demand Score",
        labels={"demand_score": "Demand Score", "skill": "Skill"},
    )
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        height=max(400, top_n * 18),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Raw demand data"):
        st.dataframe(demand_df, use_container_width=True)


# ── Page 3: Gap Analysis ──────────────────────────────────────────────────────

def page_gap_analysis() -> None:
    st.header("🎯 Seniority Skill Gap Analysis")
    gap_df = load_gap()

    if gap_df.empty:
        st.warning("No gap data found. Run `python main.py --analyze` first.")
        return

    seniority_order = ["entry", "mid", "senior", "lead"]
    available_seniorities = [s for s in seniority_order if s in gap_df["seniority"].unique()]

    pivot = gap_df.pivot_table(
        index="skill",
        columns="seniority",
        values="skew",
        aggfunc="max",
    ).reindex(columns=available_seniorities).fillna(0)

    top_skills = (
        gap_df.groupby("skill")["count"].sum().nlargest(40).index.tolist()
    )
    pivot_top = pivot.loc[pivot.index.isin(top_skills)]

    fig = px.imshow(
        pivot_top,
        color_continuous_scale="RdYlGn_r",
        title="Skill Demand Skew by Seniority Level (top 40 skills)",
        labels={"color": "Skew", "x": "Seniority", "y": "Skill"},
        aspect="auto",
    )
    fig.update_layout(height=max(500, len(pivot_top) * 16))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Flagged Gaps")
    flagged = gap_df[gap_df["gap_flag"] == True][["skill", "seniority", "skew", "count"]]
    st.dataframe(flagged.sort_values("skew", ascending=False), use_container_width=True)


# ── Page 4: Co-occurrence ─────────────────────────────────────────────────────

def page_cooccurrence() -> None:
    st.header("🕸 Skill Co-occurrence")
    cooc_df = load_cooc()

    if cooc_df.empty:
        st.warning("No co-occurrence data found. Run `python main.py --analyze` first.")
        return

    top_n = st.slider("Top N pairs", min_value=10, max_value=50, value=20, step=5)
    df_top = cooc_df.head(top_n)

    fig = px.scatter(
        df_top,
        x="skill_a",
        y="skill_b",
        size="count",
        color="count",
        color_continuous_scale="Oranges",
        title=f"Top {top_n} Co-occurring Skill Pairs",
        labels={"skill_a": "Skill A", "skill_b": "Skill B", "count": "Co-occurrence Count"},
    )
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Raw co-occurrence table"):
        st.dataframe(cooc_df, use_container_width=True)


# ── Page 5: Job Explorer ──────────────────────────────────────────────────────

def page_job_explorer() -> None:
    st.header("🔍 Job Explorer")
    df = load_raw_jobs()

    if df.empty:
        st.warning("No job data found. Run the pipeline first.")
        return

    with st.expander("Filters", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            seniority_filter = st.multiselect(
                "Seniority",
                options=df["seniority"].unique().tolist() if "seniority" in df.columns else [],
                default=[],
            )
        with col2:
            search_term = st.text_input("Search title / company", "")

    filtered = df.copy()
    if seniority_filter:
        filtered = filtered[filtered["seniority"].isin(seniority_filter)]
    if search_term:
        mask = (
            filtered["title"].str.contains(search_term, case=False, na=False)
            | filtered["company"].str.contains(search_term, case=False, na=False)
        )
        filtered = filtered[mask]

    st.caption(f"Showing {len(filtered):,} of {len(df):,} records")
    display_cols = [c for c in ["title", "company", "location", "seniority", "posted_date"] if c in filtered.columns]
    st.dataframe(filtered[display_cols], use_container_width=True, height=500)


# ── Router ────────────────────────────────────────────────────────────────────

_PAGE_MAP = {
    "📊 Overview": page_overview,
    "🔥 Demand Heatmap": page_demand_heatmap,
    "🎯 Gap Analysis": page_gap_analysis,
    "🕸 Co-occurrence": page_cooccurrence,
    "🔍 Job Explorer": page_job_explorer,
}

_PAGE_MAP[selected_page]()
