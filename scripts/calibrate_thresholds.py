import sys, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")

ana = pd.read_csv("output/analytics_summary.csv")
for col in ["demand_score","seniority_skew","gap_signal_score","senior_mentions","entry_mentions"]:
    if col in ana.columns:
        ana[col] = pd.to_numeric(ana[col], errors="coerce")
ana["is_emerging_gap"] = ana["is_emerging_gap"].map(lambda v: str(v).lower() == "true")

gap = ana[ana.segment_type == "gap_analysis"].copy()
print(f"Total skills scored: {len(gap)}")

print("\n--- seniority_skew distribution ---")
for pct in [25, 50, 75, 90, 95]:
    print(f"  p{pct}: {gap['seniority_skew'].quantile(pct/100):.2f}")
print(f"  max: {gap['seniority_skew'].max():.2f}")

print("\n--- demand_score distribution ---")
for pct in [25, 50, 75, 90, 95]:
    print(f"  p{pct}: {gap['demand_score'].quantile(pct/100):.4f}")

print("\n--- gap_signal_score distribution ---")
for pct in [50, 75, 85, 90, 95]:
    print(f"  p{pct}: {gap['gap_signal_score'].quantile(pct/100):.4f}")

print("\n--- Threshold combos (target 10-15% of skills) ---")
for sk_thresh in [1.3, 1.5, 1.7, 2.0]:
    for dem_thresh in [0.01, 0.02, 0.03]:
        n = len(gap[(gap.seniority_skew >= sk_thresh) & (gap.demand_score >= dem_thresh)])
        pct = n / len(gap) * 100
        print(f"  skew>={sk_thresh} & demand>={dem_thresh:.0%}: {n} skills ({pct:.1f}%)")

print("\n--- Currently flagged (is_emerging_gap=True) ---")
print(f"  {gap['is_emerging_gap'].sum()} skills")

print("\n--- Top 20 by gap_signal_score ---")
top = gap.nlargest(20, "gap_signal_score")[
    ["skill_canonical", "demand_score", "senior_mentions", "entry_mentions", "seniority_skew", "gap_signal_score"]
]
print(top.to_string(index=False))
