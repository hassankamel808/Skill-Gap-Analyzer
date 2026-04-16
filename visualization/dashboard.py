"""
visualization/dashboard.py
===========================
Generates 5 Plotly charts from the analytics pipeline outputs.

Each chart is exported as:
  - Interactive HTML  -> output/charts/<name>.html
  - Static PNG        -> output/charts/<name>.png  (requires kaleido)

PUBLIC API
----------
generate_all(analytics_df, cooccurrence_df, output_dir=None)
    -> dict[str, dict]
    Keys per chart: {"fig", "html_path", "png_path"}

CHARTS
------
1. top20_bar          -- Top 20 skills, horizontal bar, color by category
2. role_heatmap       -- Top 30 skills x role category demand heatmap
3. seniority_lines    -- Top 15 skills demand across Entry/Mid/Senior
4. cooccurrence_heat  -- Top 20 most co-occurring skills heatmap
5. gap_treemap        -- Gap signal treemap (demand size, skew color)

DESIGN PRINCIPLES
-----------------
- Dark theme with #0F172A background for maximum visual impact.
- Consistent skill-category color palette across all charts.
- Chart titles include the data context (DEV sample size).
- All axes labeled, legends present.
- PNG at 1600x900 (16:9), suitable for reports.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------

# Background and text colors
BG_COLOR       = "#0F172A"   # Dark navy
PAPER_COLOR    = "#1E293B"   # Slightly lighter panel
TEXT_COLOR     = "#E2E8F0"   # Light slate
GRID_COLOR     = "#334155"   # Subtle grid lines
ACCENT_COLOR   = "#38BDF8"   # Sky blue — highlights

FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

# Consistent color per skill_category (used across charts 1, 2, 5)
CATEGORY_PALETTE: dict[str, str] = {
    "programming_languages": "#38BDF8",  # Sky blue
    "frameworks_libraries":  "#F59E0B",  # Amber
    "databases":             "#34D399",  # Emerald
    "devops_cloud":          "#F87171",  # Rose
    "data_ml_ai":            "#A78BFA",  # Violet
    "tools_practices":       "#22D3EE",  # Cyan
    "cybersecurity":         "#FB923C",  # Orange
    "mobile":                "#4ADE80",  # Green
    "unknown":               "#94A3B8",  # Slate gray
}

# Category display labels for legends/hover
CATEGORY_LABELS: dict[str, str] = {
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

# Common Plotly layout template (applied to every chart)
_BASE_LAYOUT = dict(
    paper_bgcolor=BG_COLOR,
    plot_bgcolor=PAPER_COLOR,
    font=dict(family=FONT_FAMILY, color=TEXT_COLOR, size=12),
    title_font=dict(family=FONT_FAMILY, color=TEXT_COLOR, size=18, weight="bold"),
    legend=dict(
        bgcolor=PAPER_COLOR,
        bordercolor=GRID_COLOR,
        borderwidth=1,
        font=dict(color=TEXT_COLOR, size=11),
    ),
    margin=dict(l=60, r=40, t=80, b=60),
)

# Static PNG dimensions
PNG_WIDTH  = 1600
PNG_HEIGHT = 900
PNG_SCALE  = 2   # 2x for retina-quality output

# Ordered seniority levels for Chart 3
SENIORITY_ORDER = ["Entry", "Mid", "Senior"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_base_layout(fig: go.Figure, title: str, **extra) -> go.Figure:
    """Apply the dark theme base layout and title to any figure."""
    layout = dict(**_BASE_LAYOUT, title=dict(text=title, x=0.02, xanchor="left"))
    layout.update(extra)
    fig.update_layout(**layout)
    return fig


def _save_chart(
    fig: go.Figure,
    name: str,
    output_dir: Path,
) -> dict[str, Path]:
    """
    Save one chart as HTML and PNG.

    Returns
    -------
    dict with "html_path" and "png_path".
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / f"{name}.html"
    png_path  = output_dir / f"{name}.png"

    # Interactive HTML
    fig.write_html(
        str(html_path),
        include_plotlyjs="cdn",
        full_html=True,
    )
    logger.info("HTML written: %s", html_path)

    # Static PNG via kaleido
    try:
        fig.write_image(
            str(png_path),
            width=PNG_WIDTH,
            height=PNG_HEIGHT,
            scale=PNG_SCALE,
        )
        logger.info("PNG  written: %s", png_path)
    except Exception as exc:      # noqa: BLE001
        logger.warning(
            "PNG export failed (%s). "
            "Ensure kaleido is installed: pip install kaleido. "
            "HTML still saved.", exc,
        )
        png_path = None   # type: ignore[assignment]

    return {"html_path": html_path, "png_path": png_path}


def _get_global_top(analytics_df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Return the top-N global skills from analytics_df, sorted by demand_score."""
    global_df = analytics_df[
        (analytics_df["segment_type"] == "global") &
        (analytics_df["segment_value"] == "all")
    ].copy()
    global_df["demand_score"] = pd.to_numeric(global_df["demand_score"], errors="coerce")
    global_df["rank"] = pd.to_numeric(global_df["rank"], errors="coerce")
    return global_df.nsmallest(n, "rank").reset_index(drop=True)


def _map_category_color(skill_category: str) -> str:
    return CATEGORY_PALETTE.get(skill_category, CATEGORY_PALETTE["unknown"])


# ---------------------------------------------------------------------------
# Chart 1 — Top 20 Skills Horizontal Bar Chart
# ---------------------------------------------------------------------------

def chart1_top20_bar(analytics_df: pd.DataFrame, output_dir: Path) -> dict[str, Any]:
    """
    Horizontal bar chart of the top 20 skills by global demand score.

    - X axis : demand_score as percentage (0–100%)
    - Y axis : skill names, sorted descending (highest at top)
    - Color  : skill_category with consistent palette
    - Hover  : skill name, category, job count, demand %
    """
    top = _get_global_top(analytics_df, 20)
    if top.empty:
        logger.warning("Chart 1: no global data available.")
        return {}

    top["demand_pct"] = (top["demand_score"].astype(float) * 100).round(1)
    top["job_count"]  = pd.to_numeric(top["job_count"], errors="coerce").fillna(0).astype(int)
    top["color"]      = top["skill_category"].map(_map_category_color)
    top["label"]      = top["skill_category"].map(
        lambda c: CATEGORY_LABELS.get(c, "Other")
    )

    # Sort ascending so the highest bar is at the top after horizontal flip
    top_sorted = top.sort_values("demand_score", ascending=True)

    traces = []
    for cat, group in top_sorted.groupby("label", sort=False):
        color = _map_category_color(
            group["skill_category"].iloc[0]
        )
        traces.append(go.Bar(
            name=cat,
            x=group["demand_pct"],
            y=group["skill_canonical"],
            orientation="h",
            marker_color=color,
            marker_line_color="rgba(0,0,0,0.3)",
            marker_line_width=0.5,
            customdata=group[["skill_category", "job_count"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Demand: %{x:.1f}%<br>"
                "Jobs: %{customdata[1]}<br>"
                "Category: %{customdata[0]}"
                "<extra></extra>"
            ),
        ))

    fig = go.Figure(data=traces)
    _apply_base_layout(
        fig,
        title="Top 20 In-Demand Tech Skills — Egyptian Job Market",
        xaxis=dict(
            title="% of Job Postings Mentioning Skill",
            ticksuffix="%",
            gridcolor=GRID_COLOR,
            showgrid=True,
        ),
        yaxis=dict(
            title="",
            gridcolor=GRID_COLOR,
            automargin=True,
        ),
        barmode="stack",
        legend_title_text="Skill Category",
        height=620,
    )
    fig.update_layout(paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR)

    paths = _save_chart(fig, "chart1_top20_bar", output_dir)
    return {"fig": fig, **paths}


# ---------------------------------------------------------------------------
# Chart 2 — Skill Demand by Role Category Heatmap
# ---------------------------------------------------------------------------

def chart2_role_heatmap(analytics_df: pd.DataFrame, output_dir: Path) -> dict[str, Any]:
    """
    Heatmap: rows = top 30 skills, columns = role_category segments.

    Color intensity = demand_score within that role segment.
    Skills without any postings in a role show as 0 (not NaN).
    """
    role_df = analytics_df[analytics_df["segment_type"] == "role"].copy()
    if role_df.empty:
        logger.warning("Chart 2: no role-segmented data available.")
        return {}

    role_df["demand_score"] = pd.to_numeric(role_df["demand_score"], errors="coerce")

    # Get top 30 skills by global demand for the y-axis order
    top30 = _get_global_top(analytics_df, 30)["skill_canonical"].tolist()

    # Pivot: rows=skill, columns=role
    pivot = role_df.pivot_table(
        index="skill_canonical",
        columns="segment_value",
        values="demand_score",
        aggfunc="max",
    ).reindex(index=top30).fillna(0)

    # Sort roles by total demand (most demanding role first)
    role_order = pivot.sum(axis=0).sort_values(ascending=False).index.tolist()
    pivot = pivot[role_order]

    # Convert to percentage for readability
    z = (pivot.values * 100).round(1)
    x_labels = list(pivot.columns)
    y_labels = list(pivot.index)

    fig = go.Figure(go.Heatmap(
        z=z,
        x=x_labels,
        y=y_labels,
        colorscale=[
            [0.0,  "#0F172A"],   # empty = dark background
            [0.05, "#1E3A5F"],
            [0.3,  "#1D4ED8"],
            [0.6,  "#3B82F6"],
            [0.85, "#60A5FA"],
            [1.0,  "#BAE6FD"],   # high demand = bright sky blue
        ],
        colorbar=dict(
            title=dict(text="Demand (%)", font=dict(color=TEXT_COLOR)),
            ticksuffix="%",
            tickfont=dict(color=TEXT_COLOR),
            bgcolor=PAPER_COLOR,
        ),
        hoverongaps=False,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Role: %{x}<br>"
            "Demand: %{z:.1f}%"
            "<extra></extra>"
        ),
        xgap=2,
        ygap=2,
    ))

    _apply_base_layout(
        fig,
        title="Skill Demand by Role Category — Top 30 Skills",
        xaxis=dict(
            title="Role Category",
            tickangle=-30,
            showgrid=False,
            automargin=True,
        ),
        yaxis=dict(
            title="Skill",
            showgrid=False,
            automargin=True,
            autorange="reversed",   # keep top skill at top
        ),
        height=900,
    )

    paths = _save_chart(fig, "chart2_role_heatmap", output_dir)
    return {"fig": fig, **paths}


# ---------------------------------------------------------------------------
# Chart 3 — Seniority Progression Line Chart
# ---------------------------------------------------------------------------

def chart3_seniority_lines(analytics_df: pd.DataFrame, output_dir: Path) -> dict[str, Any]:
    """
    Line chart: top 15 skills demand score across seniority levels.

    X axis  : Entry → Mid → Senior (ordered)
    Y axis  : demand_score (0-100%)
    Lines   : one per skill, colored by skill_category
    Shows how skill demand shifts from junior to senior roles.
    """
    sen_df = analytics_df[analytics_df["segment_type"] == "seniority"].copy()
    if sen_df.empty:
        logger.warning("Chart 3: no seniority-segmented data available.")
        return {}

    sen_df["demand_score"] = pd.to_numeric(sen_df["demand_score"], errors="coerce")
    sen_df["demand_pct"]   = (sen_df["demand_score"] * 100).round(1)

    # Keep only top 15 skills (by global demand)
    top15 = _get_global_top(analytics_df, 15)["skill_canonical"].tolist()
    sen_df = sen_df[sen_df["skill_canonical"].isin(top15)]

    # Filter to known seniority buckets and apply ordering
    sen_df = sen_df[sen_df["segment_value"].isin(SENIORITY_ORDER)]
    sen_df["seniority_order"] = sen_df["segment_value"].map(
        {s: i for i, s in enumerate(SENIORITY_ORDER)}
    )
    sen_df = sen_df.sort_values("seniority_order")

    fig = go.Figure()

    for skill in top15:
        skill_data = sen_df[sen_df["skill_canonical"] == skill].copy()
        if skill_data.empty:
            continue

        cat   = skill_data["skill_category"].iloc[0] if "skill_category" in skill_data.columns else "unknown"
        color = _map_category_color(cat)

        fig.add_trace(go.Scatter(
            name=skill,
            x=skill_data["segment_value"].tolist(),
            y=skill_data["demand_pct"].tolist(),
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(color=color, size=8, line=dict(color=BG_COLOR, width=1.5)),
            hovertemplate=(
                f"<b>{skill}</b><br>"
                "Level: %{x}<br>"
                "Demand: %{y:.1f}%"
                "<extra></extra>"
            ),
        ))

    _apply_base_layout(
        fig,
        title="Skill Demand Across Seniority Levels — Top 15 Skills",
        xaxis=dict(
            title="Seniority Level",
            categoryorder="array",
            categoryarray=SENIORITY_ORDER,
            gridcolor=GRID_COLOR,
        ),
        yaxis=dict(
            title="% of Jobs in Seniority Segment",
            ticksuffix="%",
            gridcolor=GRID_COLOR,
            rangemode="tozero",
        ),
        legend=dict(
            **_BASE_LAYOUT["legend"],
            title_text="Skill",
            orientation="v",
        ),
        height=600,
    )

    paths = _save_chart(fig, "chart3_seniority_lines", output_dir)
    return {"fig": fig, **paths}


# ---------------------------------------------------------------------------
# Chart 4 — Co-occurrence Heatmap (Top 20)
# ---------------------------------------------------------------------------

def chart4_cooccurrence_heat(cooccurrence_df: pd.DataFrame, output_dir: Path) -> dict[str, Any]:
    """
    Symmetric heatmap of the top 20 most co-occurring skills.

    Skills selected by total co-occurrence count (row sum).
    Diagonal is always 0 (a skill doesn't co-occur with itself).
    """
    if cooccurrence_df.empty:
        logger.warning("Chart 4: co-occurrence matrix is empty.")
        return {}

    # Ensure numeric
    co = cooccurrence_df.apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)

    # Select top 20 by total co-occurrence (sum of each row)
    n = min(20, len(co))
    top_skills = co.sum(axis=1).nlargest(n).index.tolist()
    sub = co.loc[top_skills, top_skills]

    # Enforce symmetry (should already be symmetric, but guards against CSV rounding)
    sub_vals = sub.values
    sub_vals = (sub_vals + sub_vals.T) // 2
    # Zero diagonal
    for i in range(len(sub_vals)):
        sub_vals[i, i] = 0

    labels = list(sub.index)

    fig = go.Figure(go.Heatmap(
        z=sub_vals,
        x=labels,
        y=labels,
        colorscale=[
            [0.0,  "#0F172A"],
            [0.1,  "#1e3a5f"],
            [0.4,  "#1D4ED8"],
            [0.7,  "#7C3AED"],
            [0.9,  "#C084FC"],
            [1.0,  "#F0ABFC"],
        ],
        colorbar=dict(
            title=dict(text="Co-occurrences", font=dict(color=TEXT_COLOR)),
            tickfont=dict(color=TEXT_COLOR),
            bgcolor=PAPER_COLOR,
        ),
        hoverongaps=False,
        hovertemplate=(
            "<b>%{y}</b> + <b>%{x}</b><br>"
            "Co-occur in %{z} job(s)"
            "<extra></extra>"
        ),
        xgap=1,
        ygap=1,
    ))

    _apply_base_layout(
        fig,
        title="Skill Co-occurrence Matrix — Top 20 Skills",
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
        height=720,
        width=820,
    )

    paths = _save_chart(fig, "chart4_cooccurrence", output_dir)
    return {"fig": fig, **paths}


# ---------------------------------------------------------------------------
# Chart 5 — Gap Signal Treemap
# ---------------------------------------------------------------------------

def chart5_gap_treemap(analytics_df: pd.DataFrame, output_dir: Path) -> dict[str, Any]:
    """
    Treemap of skills with gap_signal_score > 0.5.

    Tile size  : demand_score  (bigger = more in-demand)
    Tile color : gap_signal_score  (darker = greater skill gap)
    Grouping   : skill_category (parent tiles)

    Skills with gap_signal_score <= 0.5 are filtered out (low urgency).
    """
    gap_df = analytics_df[analytics_df["segment_type"] == "gap_analysis"].copy()
    if gap_df.empty:
        logger.warning("Chart 5: no gap analysis data available.")
        return {}

    # Coerce numerics
    for col in ("demand_score", "gap_signal_score", "seniority_skew"):
        gap_df[col] = pd.to_numeric(gap_df[col], errors="coerce").fillna(0)

    # Filter to meaningful gap skills only
    gap_df = gap_df[gap_df["gap_signal_score"] > 0.5].copy()
    if gap_df.empty:
        logger.warning("Chart 5: no skills with gap_signal_score > 0.5.")
        # Lower threshold to show something useful
        gap_df = analytics_df[analytics_df["segment_type"] == "gap_analysis"].copy()
        for col in ("demand_score", "gap_signal_score", "seniority_skew"):
            gap_df[col] = pd.to_numeric(gap_df[col], errors="coerce").fillna(0)
        gap_df = gap_df[gap_df["gap_signal_score"] > 0].copy()

    gap_df["demand_pct"]     = (gap_df["demand_score"] * 100).round(1)
    gap_df["category_label"] = gap_df["skill_category"].map(
        lambda c: CATEGORY_LABELS.get(c, "Other")
    )
    gap_df["skew_rounded"]   = gap_df["seniority_skew"].round(2)
    gap_df["is_gap"]         = gap_df.get("is_emerging_gap", False).astype(str)

    fig = px.treemap(
        gap_df,
        path=["category_label", "skill_canonical"],
        values="demand_pct",
        color="gap_signal_score",
        color_continuous_scale=[
            [0.0, "#1E3A5F"],
            [0.3, "#1D4ED8"],
            [0.6, "#7C3AED"],
            [0.8, "#C084FC"],
            [1.0, "#F472B6"],
        ],
        custom_data=["skill_canonical", "demand_pct", "gap_signal_score", "skew_rounded", "is_gap"],
        title="Skill Gap Signal Treemap — Size: Demand, Color: Gap Urgency",
        color_continuous_midpoint=gap_df["gap_signal_score"].median(),
    )

    fig.update_traces(
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Demand: %{customdata[1]:.1f}%<br>"
            "Gap Score: %{customdata[2]:.3f}<br>"
            "Seniority Skew: %{customdata[3]:.2f}x<br>"
            "Emerging Gap: %{customdata[4]}"
            "<extra></extra>"
        ),
        marker_line_color=BG_COLOR,
        marker_line_width=1.5,
        textfont=dict(color=TEXT_COLOR, size=12),
        textinfo="label+value",
    )

    fig.update_layout(
        paper_bgcolor=BG_COLOR,
        font=dict(family=FONT_FAMILY, color=TEXT_COLOR, size=12),
        title_font=dict(family=FONT_FAMILY, color=TEXT_COLOR, size=18, weight="bold"),
        coloraxis_colorbar=dict(
            title=dict(text="Gap Score", font=dict(color=TEXT_COLOR)),
            tickfont=dict(color=TEXT_COLOR),
            bgcolor=PAPER_COLOR,
        ),
        margin=dict(l=20, r=20, t=80, b=20),
        height=680,
    )

    paths = _save_chart(fig, "chart5_gap_treemap", output_dir)
    return {"fig": fig, **paths}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_all(
    analytics_df: pd.DataFrame,
    cooccurrence_df: pd.DataFrame,
    output_dir: Path | None = None,
) -> dict[str, dict]:
    """
    Generate all 5 charts and write HTML + PNG to output_dir.

    Parameters
    ----------
    analytics_df    : Combined analytics DataFrame (from analytics_summary.csv).
                      Must contain columns: segment_type, segment_value, rank,
                      skill_canonical, skill_category, job_count, demand_score,
                      and (for gap rows) gap_signal_score, seniority_skew.
    cooccurrence_df : Square co-occurrence matrix (from cooccurrence_matrix.csv).
    output_dir      : Directory to write chart files. Defaults to
                      settings.CHARTS_DIR.

    Returns
    -------
    dict[str, dict]
        Keys: "top20_bar", "role_heatmap", "seniority_lines",
               "cooccurrence_heat", "gap_treemap".
        Each value: {"fig": go.Figure, "html_path": Path, "png_path": Path}.
    """
    if output_dir is None:
        output_dir = settings.CHARTS_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Generating 5 dashboard charts -> %s", output_dir)

    results: dict[str, dict] = {}

    # Chart 1
    logger.info("Chart 1: Top 20 skills bar chart ...")
    results["top20_bar"] = chart1_top20_bar(analytics_df, output_dir)

    # Chart 2
    logger.info("Chart 2: Role heatmap ...")
    results["role_heatmap"] = chart2_role_heatmap(analytics_df, output_dir)

    # Chart 3
    logger.info("Chart 3: Seniority progression ...")
    results["seniority_lines"] = chart3_seniority_lines(analytics_df, output_dir)

    # Chart 4
    logger.info("Chart 4: Co-occurrence heatmap ...")
    results["cooccurrence_heat"] = chart4_cooccurrence_heat(cooccurrence_df, output_dir)

    # Chart 5
    logger.info("Chart 5: Gap signal treemap ...")
    results["gap_treemap"] = chart5_gap_treemap(analytics_df, output_dir)

    # Summary
    generated_html = [
        v["html_path"].name for v in results.values()
        if v and v.get("html_path")
    ]
    generated_png = [
        v["png_path"].name for v in results.values()
        if v and v.get("png_path")
    ]
    logger.info(
        "Dashboard complete. HTML: %d files, PNG: %d files.",
        len(generated_html), len(generated_png),
    )

    return results
