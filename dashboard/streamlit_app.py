"""
dashboard/streamlit_app.py
===========================
Streamlit dashboard for the Egyptian Tech Job Market Skill-Gap Analyzer.

Reads from output CSVs (read-only). No data modification.

Run:
    streamlit run dashboard/streamlit_app.py

Navigation
----------
Sidebar radio controls which page renders. Only one page renders at a time.

Pages
-----
1. Overview         — KPI cards + category breakdown
2. Top Skills       — Bar chart, filterable by role
3. Skill Gap        — Emerging gap table + seniority skew chart
4. Co-occurrence    — Skill pair heatmap
5. Raw Data         — Filterable jobs explorer
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Project root paths — resolved relative to this file, not CWD
# ---------------------------------------------------------------------------

_DASHBOARD_DIR = Path(__file__).resolve().parent
_OUTPUT_DIR    = _DASHBOARD_DIR.parent / "output"

_ANALYTICS_CSV     = _OUTPUT_DIR / "analytics_summary.csv"
_COOCCURRENCE_CSV  = _OUTPUT_DIR / "cooccurrence_matrix.csv"
_RAW_JOBS_CSV      = _OUTPUT_DIR / "raw_jobs.csv"
_SKILLS_CSV        = _OUTPUT_DIR / "extracted_skills.csv"

# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------

# Consistent color per skill_category (Plotly-compatible)
CAT_COLORS: dict[str, str] = {
    "programming_languages": "#2563EB",
    "frameworks_libraries":  "#D97706",
    "databases":             "#16A34A",
    "devops_cloud":          "#DC2626",
    "data_ml_ai":            "#7C3AED",
    "tools_practices":       "#0891B2",
    "cybersecurity":         "#EA580C",
    "mobile":                "#15803D",
    "unknown":               "#6B7280",
}

CAT_LABELS: dict[str, str] = {
    "programming_languages": "Languages",
    "frameworks_libraries":  "Frameworks",
    "databases":             "Databases",
    "devops_cloud":          "DevOps / Cloud",
    "data_ml_ai":            "Data / ML / AI",
    "tools_practices":       "Tools & Practices",
    "cybersecurity":         "Cybersecurity",
    "mobile":                "Mobile",
    "unknown":               "Other",
}

# Valid work_mode values (filter out CSS-bleed noise from raw scraping)
_VALID_WORK_MODES = {"Hybrid", "Remote", "On-site"}

# Valid job_type values
_VALID_JOB_TYPES = {"Full Time", "Part Time", "Internship", "Contract", "Freelance"}


# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------

@st.cache_data
def load_analytics() -> pd.DataFrame:
    """Load analytics_summary.csv with correct numeric dtypes."""
    if not _ANALYTICS_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(_ANALYTICS_CSV, dtype=str)
    for col in ("demand_score", "job_count", "rank", "demand_rank",
                "senior_mentions", "mid_mentions", "entry_mentions",
                "seniority_skew", "gap_signal_score"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "is_emerging_gap" in df.columns:
        df["is_emerging_gap"] = df["is_emerging_gap"].map(
            lambda v: str(v).strip().lower() == "true"
        )
    return df


@st.cache_data
def load_cooccurrence() -> pd.DataFrame:
    """Load cooccurrence_matrix.csv as a numeric square DataFrame."""
    if not _COOCCURRENCE_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(_COOCCURRENCE_CSV, index_col=0)
    return df.apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)


@st.cache_data
def load_raw_jobs() -> pd.DataFrame:
    """Load raw_jobs.csv with cleaned filter columns."""
    if not _RAW_JOBS_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(_RAW_JOBS_CSV, dtype=str)

    # Clean work_mode: keep only known values, mark rest as "Other"
    if "work_mode" in df.columns:
        df["work_mode_clean"] = df["work_mode"].apply(
            lambda v: v.strip() if str(v).strip() in _VALID_WORK_MODES else "Other"
        )
    else:
        df["work_mode_clean"] = "Other"

    # Clean job_type
    if "job_type" in df.columns:
        df["job_type_clean"] = df["job_type"].apply(
            lambda v: v.strip() if str(v).strip() in _VALID_JOB_TYPES else "Other"
        )
    else:
        df["job_type_clean"] = "Other"

    return df


@st.cache_data
def load_skills() -> pd.DataFrame:
    """Load extracted_skills.csv."""
    if not _SKILLS_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(_SKILLS_CSV, dtype=str)
    if "confidence" in df.columns:
        df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Helper: check data availability
# ---------------------------------------------------------------------------

def _data_missing_warning(label: str) -> None:
    st.warning(
        f"**{label}** data not found. "
        f"Run `python main.py --analysis-only` from the project root to generate outputs.",
        icon="⚠️",
    )


def _color_for(skill_category: str) -> str:
    return CAT_COLORS.get(str(skill_category), CAT_COLORS["unknown"])


def _label_for(skill_category: str) -> str:
    return CAT_LABELS.get(str(skill_category), "Other")


# ---------------------------------------------------------------------------
# Page 1 — Overview
# ---------------------------------------------------------------------------

def page_overview():
    st.header("Egyptian Tech Job Market — Overview")
    st.caption(
        "Summary statistics derived from Wuzzuf.net job postings. "
        "Run the pipeline again to refresh."
    )

    jobs_df   = load_raw_jobs()
    skills_df = load_skills()
    ana_df    = load_analytics()

    if jobs_df.empty:
        _data_missing_warning("raw_jobs.csv")
        return

    # ── KPI metric cards ──────────────────────────────────────────────────────
    total_jobs      = jobs_df["job_id"].nunique() if "job_id" in jobs_df.columns else len(jobs_df)
    total_companies = jobs_df["company_name"].nunique() if "company_name" in jobs_df.columns else 0
    total_skills    = skills_df["skill_canonical"].nunique() if not skills_df.empty else 0

    # Date range from scraped_at
    date_label = "N/A"
    if "scraped_at" in jobs_df.columns:
        try:
            dates = pd.to_datetime(jobs_df["scraped_at"], utc=True, errors="coerce").dropna()
            if not dates.empty:
                lo = dates.min().strftime("%b %d")
                hi = dates.max().strftime("%b %d, %Y")
                date_label = f"{lo} – {hi}" if lo != hi else hi
        except Exception:
            pass

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Jobs Scraped",   f"{total_jobs:,}")
    c2.metric("Unique Skills Found",  f"{total_skills:,}")
    c3.metric("Companies Hiring",     f"{total_companies:,}")
    c4.metric("Scrape Date Range",    date_label)

    st.divider()

    # ── Skill category breakdown (pie chart) ──────────────────────────────────
    if not skills_df.empty and "skill_category" in skills_df.columns:
        st.subheader("Skill Mentions by Category")
        cat_counts = (
            skills_df
            .groupby("skill_category")["skill_canonical"]
            .count()
            .reset_index()
            .rename(columns={"skill_canonical": "mention_count"})
        )
        cat_counts["label"] = cat_counts["skill_category"].map(_label_for)
        cat_counts["color"] = cat_counts["skill_category"].map(_color_for)

        fig = px.pie(
            cat_counts,
            names="label",
            values="mention_count",
            color="label",
            color_discrete_map={_label_for(c): _color_for(c) for c in CAT_COLORS},
            hole=0.4,
            title="Distribution of Skill Mentions Across Taxonomy Categories",
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(
            showlegend=True,
            legend_title_text="Category",
            height=400,
            margin=dict(t=50, b=20, l=20, r=20),
        )
        st.plotly_chart(fig, width="stretch")

    # ── Jobs by role category bar ─────────────────────────────────────────────
    if not skills_df.empty and "role_category" in skills_df.columns:
        st.subheader("Job Postings by Role Category")
        role_counts = (
            skills_df
            .drop_duplicates("job_id")[["job_id", "role_category"]]
            .groupby("role_category")["job_id"]
            .count()
            .reset_index()
            .rename(columns={"job_id": "job_count"})
            .sort_values("job_count", ascending=True)
        )
        fig2 = px.bar(
            role_counts,
            x="job_count",
            y="role_category",
            orientation="h",
            labels={"job_count": "Number of Jobs", "role_category": "Role Category"},
            title="Jobs Scraped per Role Category",
            color_discrete_sequence=["#2563EB"],
        )
        fig2.update_layout(height=380, margin=dict(t=50, b=20, l=20, r=20))
        st.plotly_chart(fig2, width="stretch")


# ---------------------------------------------------------------------------
# Page 2 — Top Skills
# ---------------------------------------------------------------------------

def page_top_skills():
    st.header("Top In-Demand Skills")

    ana_df = load_analytics()
    if ana_df.empty:
        _data_missing_warning("analytics_summary.csv")
        return

    # ── Role filter dropdown ──────────────────────────────────────────────────
    role_options = ["Global (All Roles)"] + sorted(
        ana_df.loc[ana_df["segment_type"] == "role", "segment_value"]
        .dropna()
        .unique()
        .tolist()
    )
    selected_role = st.selectbox(
        "Filter by Role Category",
        options=role_options,
        index=0,
        help="Show top skills globally or filtered to one role segment.",
    )

    if selected_role == "Global (All Roles)":
        seg_df = ana_df[
            (ana_df["segment_type"] == "global") &
            (ana_df["segment_value"] == "all")
        ].nsmallest(20, "rank").copy()
        chart_title = "Top 20 Skills — Global Demand"
        x_label = "% of All Job Postings"
    else:
        seg_df = ana_df[
            (ana_df["segment_type"] == "role") &
            (ana_df["segment_value"] == selected_role)
        ].nsmallest(10, "rank").copy()
        chart_title = f"Top 10 Skills — {selected_role} Roles"
        x_label = f"% of {selected_role} Job Postings"

    if seg_df.empty:
        st.info("No data available for the selected segment.")
        return

    seg_df["demand_pct"]    = (seg_df["demand_score"] * 100).round(1)
    seg_df["category_label"] = seg_df["skill_category"].map(_label_for)
    seg_df = seg_df.sort_values("demand_score", ascending=True)

    # Build trace per category for legend
    fig = go.Figure()
    for cat, group in seg_df.groupby("category_label", sort=False):
        raw_cat = group["skill_category"].iloc[0]
        color   = _color_for(raw_cat)
        fig.add_trace(go.Bar(
            name=cat,
            x=group["demand_pct"],
            y=group["skill_canonical"],
            orientation="h",
            marker_color=color,
            marker_line_color="white",
            marker_line_width=0.8,
            customdata=group[["job_count", "skill_category"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Demand: %{x:.1f}%<br>"
                "Jobs: %{customdata[0]:.0f}<br>"
                "Category: %{customdata[1]}<extra></extra>"
            ),
        ))

    fig.update_layout(
        title=chart_title,
        xaxis=dict(title=x_label, ticksuffix="%"),
        yaxis=dict(title="", automargin=True),
        barmode="stack",
        legend_title_text="Category",
        height=max(380, len(seg_df) * 32 + 100),
        margin=dict(t=60, b=40, l=10, r=10),
    )
    st.plotly_chart(fig, width="stretch")

    # ── Tabular view ──────────────────────────────────────────────────────────
    with st.expander("Show as table"):
        display = seg_df[["rank", "skill_canonical", "skill_category", "job_count", "demand_pct"]].copy()
        display.columns = ["Rank", "Skill", "Category", "Jobs", "Demand (%)"]
        st.dataframe(display.reset_index(drop=True), width="stretch")


# ---------------------------------------------------------------------------
# Page 3 — Skill Gap Analysis
# ---------------------------------------------------------------------------

def page_skill_gap():
    st.header("Skill Gap Analysis")
    st.caption(
        "Emerging gap skills have high demand AND skew heavily toward senior roles, "
        "signalling that the market lacks enough experienced practitioners."
    )

    ana_df = load_analytics()
    if ana_df.empty:
        _data_missing_warning("analytics_summary.csv")
        return

    gap_df = ana_df[ana_df["segment_type"] == "gap_analysis"].copy()

    if gap_df.empty:
        st.info("No gap analysis data found in analytics_summary.csv.")
        return

    # ── Emerging Gap Skills table ─────────────────────────────────────────────
    st.subheader("Emerging Gap Skills")
    st.caption(
        "Skills with `is_emerging_gap = True`: demand ≥ 5% AND seniority_skew ≥ 2× "
        "(senior mentions / entry mentions)."
    )

    emerging = gap_df[gap_df["is_emerging_gap"] == True].copy()
    if emerging.empty:
        st.info("No emerging gap skills detected with the current thresholds.")
    else:
        display_cols = {
            "skill_canonical":  "Skill",
            "skill_category":   "Category",
            "demand_score":     "Demand Score",
            "senior_mentions":  "Senior Jobs",
            "entry_mentions":   "Entry Jobs",
            "seniority_skew":   "Seniority Skew",
            "gap_signal_score": "Gap Signal",
        }
        tbl = emerging[list(display_cols.keys())].copy()
        tbl = tbl.rename(columns=display_cols)
        tbl["Demand Score"]  = tbl["Demand Score"].map(lambda v: f"{v:.1%}")
        tbl["Seniority Skew"] = tbl["Seniority Skew"].map(lambda v: f"{v:.1f}×")
        tbl["Gap Signal"]    = tbl["Gap Signal"].map(lambda v: f"{v:.3f}")
        tbl["Senior Jobs"]   = tbl["Senior Jobs"].map(lambda v: f"{int(v):,}" if pd.notna(v) else "—")
        tbl["Entry Jobs"]    = tbl["Entry Jobs"].map(lambda v: f"{int(v):,}" if pd.notna(v) else "—")
        st.dataframe(tbl.reset_index(drop=True), width="stretch")

    st.divider()

    # ── Seniority Skew bar chart — all skills ─────────────────────────────────
    st.subheader("Seniority Skew per Skill")
    st.caption(
        "Higher bar = skill is disproportionately demanded in senior roles. "
        "Red bars are flagged as emerging gaps."
    )

    skew_df = gap_df[gap_df["seniority_skew"].notna()].copy()
    skew_df = skew_df.sort_values("seniority_skew", ascending=False).head(25)
    skew_df["color"] = skew_df["is_emerging_gap"].map(
        lambda v: "#DC2626" if v else "#2563EB"
    )
    skew_df["gap_label"] = skew_df["is_emerging_gap"].map(
        lambda v: "Emerging Gap" if v else "Normal"
    )

    fig = go.Figure()
    for label, grp in skew_df.groupby("gap_label", sort=False):
        color = "#DC2626" if label == "Emerging Gap" else "#2563EB"
        fig.add_trace(go.Bar(
            name=label,
            x=grp["skill_canonical"],
            y=grp["seniority_skew"],
            marker_color=color,
            marker_line_color="white",
            marker_line_width=0.5,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Seniority Skew: %{y:.1f}×<br>"
                "Senior/Entry ratio<extra></extra>"
            ),
        ))

    # Add a reference line at skew = 2.0
    fig.add_hline(
        y=2.0,
        line_dash="dash",
        line_color="orange",
        annotation_text="Gap threshold (2×)",
        annotation_position="top right",
    )

    fig.update_layout(
        title="Seniority Skew — Senior / Entry Level Mentions Ratio (Top 25 Skills)",
        xaxis=dict(title="Skill", tickangle=-35),
        yaxis=dict(title="Seniority Skew (×)"),
        barmode="group",
        legend_title_text="Flag",
        height=450,
        margin=dict(t=60, b=100, l=20, r=20),
    )
    st.plotly_chart(fig, width="stretch")

    # ── Gap Signal scatter ────────────────────────────────────────────────────
    st.subheader("Demand vs. Seniority Skew — Quadrant View")
    st.caption(
        "Top-right quadrant (high demand + high skew) = most urgent skill gaps to address."
    )
    scatter_df = gap_df[
        gap_df["demand_score"].notna() & gap_df["seniority_skew"].notna()
    ].copy()
    scatter_df["demand_pct"] = (scatter_df["demand_score"] * 100).round(1)
    scatter_df["cat_label"]  = scatter_df["skill_category"].map(_label_for)

    fig2 = px.scatter(
        scatter_df,
        x="demand_pct",
        y="seniority_skew",
        text="skill_canonical",
        color="cat_label",
        color_discrete_map={_label_for(c): _color_for(c) for c in CAT_COLORS},
        size="gap_signal_score",
        size_max=30,
        labels={
            "demand_pct":    "Demand (% of jobs)",
            "seniority_skew":"Seniority Skew (×)",
            "cat_label":     "Category",
        },
        title="Demand vs. Seniority Skew  |  Bubble size = Gap Signal Score",
    )
    fig2.update_traces(textposition="top center", textfont_size=10)

    # Quadrant lines
    med_demand = scatter_df["demand_pct"].median()
    med_skew   = scatter_df["seniority_skew"].median()
    fig2.add_hline(y=med_skew,   line_dash="dot", line_color="gray", opacity=0.5)
    fig2.add_vline(x=med_demand, line_dash="dot", line_color="gray", opacity=0.5)

    fig2.update_layout(height=480, margin=dict(t=60, b=40, l=20, r=20))
    st.plotly_chart(fig2, width="stretch")


# ---------------------------------------------------------------------------
# Page 4 — Co-occurrence
# ---------------------------------------------------------------------------

def page_cooccurrence():
    st.header("Skill Co-occurrence Matrix")
    st.caption(
        "Each cell shows how many job postings mention **both** skill A and skill B together. "
        "Diagonal is always 0. Matrix is symmetric."
    )

    co_df = load_cooccurrence()
    if co_df.empty:
        _data_missing_warning("cooccurrence_matrix.csv")
        return

    # Top 20 by total co-occurrence
    n = st.slider("Number of top skills to display", min_value=10, max_value=min(50, len(co_df)), value=20, step=5)
    top_skills = co_df.sum(axis=1).nlargest(n).index.tolist()
    sub = co_df.loc[top_skills, top_skills].copy()

    # Enforce symmetry and zero diagonal
    vals = sub.values.copy()
    vals = (vals + vals.T) // 2
    for i in range(len(vals)):
        vals[i, i] = 0
    labels = list(sub.index)

    # Mask the diagonal for visual clarity (show as white)
    import numpy as np
    masked = vals.astype(float)
    for i in range(len(masked)):
        masked[i, i] = float("nan")

    fig = go.Figure(go.Heatmap(
        z=masked,
        x=labels,
        y=labels,
        colorscale="Blues",
        colorbar=dict(title="Co-occurrences"),
        hoverongaps=False,
        hovertemplate=(
            "<b>%{y}</b> + <b>%{x}</b><br>"
            "Co-occur in %{z:.0f} job(s)<extra></extra>"
        ),
        xgap=1,
        ygap=1,
    ))

    fig.update_layout(
        title=f"Skill Co-occurrence — Top {n} Skills",
        xaxis=dict(
            title="",
            tickangle=-45,
            showgrid=False,
            automargin=True,
        ),
        yaxis=dict(
            title="",
            showgrid=False,
            automargin=True,
            autorange="reversed",
        ),
        height=max(500, n * 26 + 120),
        margin=dict(t=60, b=80, l=10, r=10),
    )
    st.plotly_chart(fig, width="stretch")

    # ── Top pairs table ───────────────────────────────────────────────────────
    st.subheader("Top Co-occurring Skill Pairs")
    import numpy as np
    pairs = []
    for i, a in enumerate(labels):
        for j, b in enumerate(labels):
            if j > i and vals[i, j] > 0:
                pairs.append({"Skill A": a, "Skill B": b, "Jobs Together": int(vals[i, j])})
    pairs_df = pd.DataFrame(pairs).sort_values("Jobs Together", ascending=False).head(15)
    st.dataframe(pairs_df.reset_index(drop=True), width="stretch")


# ---------------------------------------------------------------------------
# Page 5 — Raw Data Explorer
# ---------------------------------------------------------------------------

def page_raw_data():
    st.header("Raw Jobs Explorer")
    st.caption(
        "Browse and filter all scraped job postings. "
        "Use the filters below to narrow the results."
    )

    jobs_df = load_raw_jobs()
    if jobs_df.empty:
        _data_missing_warning("raw_jobs.csv")
        return

    # ── Filter row ────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns(4)

    # City filter
    cities = sorted(jobs_df["city"].dropna().unique().tolist()) if "city" in jobs_df.columns else []
    # Filter obvious noise (only show values without digits; real cities don't have them)
    cities = [c for c in cities if c and not any(ch.isdigit() for ch in c)]
    sel_city = fc1.multiselect("City", options=cities, default=[], placeholder="All cities")

    # Work mode (cleaned)
    work_modes = sorted(jobs_df["work_mode_clean"].dropna().unique().tolist())
    sel_mode = fc2.multiselect("Work Mode", options=work_modes, default=[], placeholder="All modes")

    # Job type (cleaned)
    job_types = sorted(jobs_df["job_type_clean"].dropna().unique().tolist())
    sel_type = fc3.multiselect("Job Type", options=job_types, default=[], placeholder="All types")

    # Experience level
    exp_levels = sorted(jobs_df["experience_level"].dropna().unique().tolist()) if "experience_level" in jobs_df.columns else []
    sel_exp = fc4.multiselect("Experience Level", options=exp_levels, default=[], placeholder="All levels")

    # ── Text search ───────────────────────────────────────────────────────────
    search = st.text_input(
        "Search job titles or companies",
        placeholder="e.g. Python, Django, React...",
    )

    # ── Apply filters ─────────────────────────────────────────────────────────
    filtered = jobs_df.copy()

    if sel_city:
        filtered = filtered[filtered["city"].isin(sel_city)]
    if sel_mode:
        filtered = filtered[filtered["work_mode_clean"].isin(sel_mode)]
    if sel_type:
        filtered = filtered[filtered["job_type_clean"].isin(sel_type)]
    if sel_exp:
        filtered = filtered[filtered["experience_level"].isin(sel_exp)]
    if search.strip():
        mask = (
            filtered["job_title"].str.contains(search, case=False, na=False) |
            filtered["company_name"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.caption(f"Showing **{len(filtered):,}** of **{len(jobs_df):,}** jobs")

    # Display columns (drop internal columns)
    display_cols = [c for c in [
        "job_id", "job_title", "company_name", "city", "experience_level",
        "work_mode_clean", "job_type_clean", "category_tags",
        "source_category", "posted_date_raw",
    ] if c in filtered.columns]

    rename_map = {
        "work_mode_clean": "work_mode",
        "job_type_clean":  "job_type",
    }

    out = filtered[display_cols].rename(columns=rename_map).reset_index(drop=True)
    st.dataframe(out, width="stretch", height=500)

    # ── Download ──────────────────────────────────────────────────────────────
    csv_bytes = out.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered results as CSV",
        data=csv_bytes,
        file_name="filtered_jobs.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Main — sidebar navigation
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Egyptian Tech Job Market — Skill-Gap Analyzer",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Sidebar
    with st.sidebar:
        st.title("📊 Skill-Gap Analyzer")
        st.caption("Egyptian Tech Job Market · Wuzzuf.net")
        st.divider()

        page = st.radio(
            "Navigate to",
            options=[
                "1 · Overview",
                "2 · Top Skills",
                "3 · Skill Gap Analysis",
                "4 · Co-occurrence",
                "5 · Raw Data Explorer",
            ],
            index=0,
        )

        st.divider()
        st.caption(
            "**Data sources**\n"
            "- `output/analytics_summary.csv`\n"
            "- `output/cooccurrence_matrix.csv`\n"
            "- `output/raw_jobs.csv`\n"
            "- `output/extracted_skills.csv`\n\n"
            "Refresh data: `python main.py --analysis-only`"
        )

    # ── Render exactly ONE page ───────────────────────────────────────────────
    if page == "1 · Overview":
        page_overview()
    elif page == "2 · Top Skills":
        page_top_skills()
    elif page == "3 · Skill Gap Analysis":
        page_skill_gap()
    elif page == "4 · Co-occurrence":
        page_cooccurrence()
    elif page == "5 · Raw Data Explorer":
        page_raw_data()


if __name__ == "__main__":
    main()
