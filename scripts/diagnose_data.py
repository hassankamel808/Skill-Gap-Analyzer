import sys, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")

raw    = pd.read_csv("output/raw_jobs.csv")
skills = pd.read_csv("output/extracted_skills.csv")

print(f"raw_jobs rows          : {len(raw)}")
print(f"extracted_skills rows  : {len(skills)}")
print(f"unique job_ids raw     : {raw['job_id'].nunique()}")
print(f"unique job_ids skills  : {skills['job_id'].nunique()}")
print(f"unique skills          : {skills['skill_canonical'].nunique()}")
print()
print("Sample job_ids raw   (first 3):", raw["job_id"].head(3).tolist())
print("Sample job_ids skills (first 3):", skills["job_id"].head(3).tolist())
print()

# Check overlap
raw_ids    = set(raw["job_id"])
skills_ids = set(skills["job_id"])
in_both    = raw_ids & skills_ids
print(f"Jobs in raw_jobs but NOT in extracted_skills: {len(raw_ids - skills_ids)}")
print(f"Jobs in extracted_skills but NOT in raw_jobs: {len(skills_ids - raw_ids)}")
print(f"Jobs present in BOTH: {len(in_both)}")
