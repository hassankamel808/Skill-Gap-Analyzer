"""
Verification script for Phase A.
Run from the project root: python verify_phase_a.py
"""
import sys
sys.path.insert(0, r"C:\Users\hdbor\.gemini\antigravity\scratch\wuzzuf-skill-gap")

from config.skill_taxonomy import (
    SKILL_TAXONOMY, SKILL_ALIAS_MAP, ROLE_CATEGORY_KEYWORDS,
    ROLE_CATEGORY_PRIORITY, get_all_skills, get_canonical, classify_role,
    get_skill_category,
)

# ── Skill counts ────────────────────────────────────────────────────────────
all_skills = get_all_skills()
print(f"Total canonical skills : {len(all_skills)}")
print(f"Total alias mappings   : {len(SKILL_ALIAS_MAP)}")
print(f"Taxonomy categories    : {list(SKILL_TAXONOMY.keys())}")
print()

for cat, skills in SKILL_TAXONOMY.items():
    print(f"  {cat:<30} {len(skills):>3} skills")
print()

# ── Alias resolution tests ───────────────────────────────────────────────────
alias_tests = [
    ("reactjs",             "React"),
    ("  React.JS ",         "React"),
    ("k8s",                 "Kubernetes"),
    ("amazon web services", "AWS"),
    ("pyspark",             "Apache Spark"),
    ("sklearn",             "scikit-learn"),
    ("llm",                 "Large Language Models"),
    ("cicd",                "CI/CD"),
    ("mssql",               "SQL Server"),
    ("golang",              "Go"),
    ("dotnet",              ".NET"),
    ("ml",                  "Machine Learning"),
]

all_ok = True
print("Alias resolution tests:")
sep = "-" * 75
print(sep)
for raw, expected in alias_tests:
    result = get_canonical(raw)
    status = "OK" if result == expected else f"FAIL (got {result!r})"
    if result != expected:
        all_ok = False
    print(f"  get_canonical({raw!r:<30}) -> {result!r:<32} [{status}]")
print()

# ── Role classification tests ────────────────────────────────────────────────
role_tests = [
    ("Senior Data Engineer",            "Data Engineering"),
    ("Machine Learning Engineer",       "Data Science / ML"),
    ("iOS Developer",                   "Mobile"),
    ("Senior DevOps Engineer",          "DevOps / Cloud"),
    ("Cybersecurity Analyst",           "Cybersecurity"),
    ("QA Automation Engineer",          "QA / Testing"),
    ("React Frontend Developer",        "Frontend"),
    ("Senior Backend Java Developer",   "Backend"),
    ("Full Stack Developer",            "Full Stack"),
    ("UX Designer",                     "UI/UX"),
    ("Sales Manager",                   "Other Tech"),
]

print("Role classification tests:")
print(sep)
for title, expected in role_tests:
    result = classify_role(title)
    status = "OK" if result == expected else f"FAIL (got {result!r})"
    if result != expected:
        all_ok = False
    print(f"  classify_role({title!r:<42}) -> {result!r:<25} [{status}]")
print()

# ── Skill category lookup tests ──────────────────────────────────────────────
cat_tests = [
    ("Python", "programming_languages"),
    ("Docker", "devops_cloud"),
    ("React",  "frameworks_libraries"),
]
print("Skill category lookup tests:")
print(sep)
for skill, expected in cat_tests:
    result = get_skill_category(skill)
    status = "OK" if result == expected else f"FAIL (got {result!r})"
    if result != expected:
        all_ok = False
    print(f"  get_skill_category({skill!r:<15}) -> {result!r:<30} [{status}]")
print()

# ── Settings check ───────────────────────────────────────────────────────────
from config.settings import DEV_MODE_LIMIT, DEV_MODE_LIMIT_COUNT, TARGET_CATEGORIES
print(f"DEV_MODE_LIMIT       = {DEV_MODE_LIMIT}")
print(f"DEV_MODE_LIMIT_COUNT = {DEV_MODE_LIMIT_COUNT}")
labels = [c["label"] for c in TARGET_CATEGORIES]
print(f"Target categories    = {labels}")
print()

# ── User-Agent pool ──────────────────────────────────────────────────────────
from config.user_agents import USER_AGENT_POOL, get_random_ua
print(f"User-Agent pool size = {len(USER_AGENT_POOL)}")
sample_ua = get_random_ua()
print(f"Sample UA (80 chars) = {sample_ua[:80]}...")
print()

# ── ROLE_CATEGORY_PRIORITY completeness ──────────────────────────────────────
print("ROLE_CATEGORY_PRIORITY order:")
for i, cat in enumerate(ROLE_CATEGORY_PRIORITY, 1):
    print(f"  {i:>2}. {cat}")
print()

# ── Final verdict ─────────────────────────────────────────────────────────────
print("=" * 75)
print("PHASE A VERIFICATION: ALL TESTS PASSED" if all_ok else
      "PHASE A VERIFICATION: SOME TESTS FAILED — see details above")
print("=" * 75)
