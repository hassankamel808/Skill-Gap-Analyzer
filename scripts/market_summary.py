import sys, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")

ana = pd.read_csv("output/analytics_summary.csv")
co  = pd.read_csv("output/cooccurrence_matrix.csv", index_col=0)

for col in ["demand_score","job_count","gap_signal_score","seniority_skew","senior_mentions","entry_mentions","rank"]:
    if col in ana.columns:
        ana[col] = pd.to_numeric(ana[col], errors="coerce")

g = ana[(ana.segment_type=="global") & (ana.segment_value=="all")].nsmallest(20,"rank")
print("=== TOP 20 (Core Data fix verified) ===")
print(g[["rank","skill_canonical","skill_category","job_count","demand_score"]].to_string(index=False))

print()
print("=== EMERGING GAP SKILLS (is_emerging_gap=True) ===")
gaps = ana[ana.segment_type=="gap_analysis"].copy()
gaps["is_emerging_gap"] = gaps["is_emerging_gap"].map(lambda x: str(x).lower()=="true")
top_gaps = gaps[gaps.is_emerging_gap].sort_values("gap_signal_score", ascending=False).head(10)
print(top_gaps[["skill_canonical","demand_score","senior_mentions","entry_mentions","seniority_skew","gap_signal_score"]].to_string(index=False))

print()
print("=== TOP 10 CO-OCCURRING SKILL PAIRS ===")
co_num = co.apply(pd.to_numeric, errors="coerce").fillna(0)
pairs = []
for i in co_num.index:
    for j in co_num.columns:
        if i < j and co_num.loc[i, j] > 0:
            pairs.append((i, j, int(co_num.loc[i, j])))
pairs.sort(key=lambda x: -x[2])
for a, b, n in pairs[:10]:
    print(f"  {a} + {b}: {n} jobs")

print()
print("=== TOP 3 SKILLS BY SENIORITY SEGMENT ===")
for lvl in ["Entry","Mid","Senior"]:
    s = ana[(ana.segment_type=="seniority") & (ana.segment_value==lvl)].nsmallest(3, "rank")
    tops = ", ".join(s["skill_canonical"].tolist())
    print(f"  {lvl}: {tops}")

print()
print("=== #1 SKILL PER ROLE CATEGORY ===")
for role in sorted(ana[ana.segment_type=="role"]["segment_value"].unique()):
    r = ana[(ana.segment_type=="role") & (ana.segment_value==role)].nsmallest(1, "rank")
    if not r.empty:
        skill = r.iloc[0]["skill_canonical"]
        score = r.iloc[0]["demand_score"]
        print(f"  {role}: {skill} ({score:.0%})")
