"""
scripts/generate_mock_data.py
==============================
Generates realistic mock raw_jobs.csv and extracted_skills.csv for
end-to-end pipeline testing without needing Chrome/Selenium.

50 jobs distributed across role categories, seniority levels, and cities
matching realistic Egyptian tech market proportions.

Usage:
    python scripts/generate_mock_data.py
"""

import csv
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from extraction.skill_extractor import extract_skills_for_job

# ---------------------------------------------------------------------------
# Mock job definitions
# ---------------------------------------------------------------------------
# Fields: job_id, job_title, company_name, city, experience_level,
#         work_mode, job_type, category_tags, source_category, scraped_at

NOW = datetime.now(tz=timezone.utc).isoformat()

MOCK_JOBS = [
    # ── Backend Python (12 jobs) ──────────────────────────────────────────────
    {"job_id": "bk001", "job_title": "Senior Python Backend Developer",
     "company_name": "Breadfast",         "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Python,Django,PostgreSQL,Docker,REST API,Git,Celery,Redis",
     "source_category": "IT-Software-Development"},

    {"job_id": "bk002", "job_title": "Python FastAPI Developer",
     "company_name": "Instabug",          "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "Remote",   "job_type": "Full Time",
     "category_tags": "Python,FastAPI,PostgreSQL,Docker,REST API,AWS,Redis",
     "source_category": "IT-Software-Development"},

    {"job_id": "bk003", "job_title": "Junior Python Developer",
     "company_name": "Flat6Labs",         "city": "Cairo",        "experience_level": "Entry Level",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Python,Django,MySQL,Git,REST API",
     "source_category": "IT-Software-Development"},

    {"job_id": "bk004", "job_title": "Senior Django Developer",
     "company_name": "Paymob",            "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Python,Django,PostgreSQL,REST API,Docker,Celery,Git,AWS",
     "source_category": "IT-Software-Development"},

    {"job_id": "bk005", "job_title": "Python Backend Engineer",
     "company_name": "MaxAB",             "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Python,Flask,MongoDB,Redis,Docker,REST API,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "bk006", "job_title": "Backend Engineer – Node.js",
     "company_name": "Vezeeta",           "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Node.js,JavaScript,TypeScript,PostgreSQL,Docker,REST API,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "bk007", "job_title": "PHP Laravel Developer",
     "company_name": "Noon",              "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "PHP,Laravel,MySQL,Docker,REST API,Git,Redis",
     "source_category": "IT-Software-Development"},

    {"job_id": "bk008", "job_title": "Senior Java Backend Developer",
     "company_name": "Orange Egypt",      "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Java,Spring Boot,PostgreSQL,Docker,REST API,Microservices,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "bk009", "job_title": "Java Spring Boot Developer",
     "company_name": "Vodafone Egypt",    "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Java,Spring Boot,MySQL,Docker,REST API,Git,Agile",
     "source_category": "IT-Software-Development"},

    {"job_id": "bk010", "job_title": "Backend Developer Python",
     "company_name": "Swvl",             "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Python,FastAPI,MongoDB,Redis,Docker,REST API,Microservices",
     "source_category": "IT-Software-Development"},

    {"job_id": "bk011", "job_title": "Junior Backend Developer",
     "company_name": "Halan",            "city": "Alexandria",   "experience_level": "Entry Level",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "PHP,MySQL,REST API,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "bk012", "job_title": "Senior Node.js Developer",
     "company_name": "Robusta",          "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Remote",   "job_type": "Full Time",
     "category_tags": "Node.js,TypeScript,MongoDB,Redis,Docker,microservices,REST API,AWS",
     "source_category": "IT-Software-Development"},

    # ── Frontend (10 jobs) ────────────────────────────────────────────────────
    {"job_id": "fe001", "job_title": "Senior React Frontend Developer",
     "company_name": "Breadfast",         "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "React,JavaScript,TypeScript,CSS,HTML,Git,REST API,Redux",
     "source_category": "IT-Software-Development"},

    {"job_id": "fe002", "job_title": "React Developer",
     "company_name": "Paymob",            "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "React,JavaScript,TypeScript,CSS,Git,REST API",
     "source_category": "IT-Software-Development"},

    {"job_id": "fe003", "job_title": "Angular Frontend Developer",
     "company_name": "Orange Egypt",      "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Angular,TypeScript,JavaScript,CSS,Git,REST API,RxJS",
     "source_category": "IT-Software-Development"},

    {"job_id": "fe004", "job_title": "Junior React Developer",
     "company_name": "Sarmady",           "city": "Cairo",        "experience_level": "Entry Level",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "React,JavaScript,CSS,HTML,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "fe005", "job_title": "Senior Angular Developer",
     "company_name": "Vodafone Egypt",    "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Angular,TypeScript,JavaScript,REST API,Git,Agile",
     "source_category": "IT-Software-Development"},

    {"job_id": "fe006", "job_title": "Vue.js Frontend Developer",
     "company_name": "Dsquares",          "city": "Alexandria",   "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Vue.js,JavaScript,TypeScript,CSS,REST API,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "fe007", "job_title": "Frontend Engineer React Next.js",
     "company_name": "Instabug",          "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "Remote",   "job_type": "Full Time",
     "category_tags": "React,Next.js,TypeScript,JavaScript,CSS,Git,REST API",
     "source_category": "IT-Software-Development"},

    {"job_id": "fe008", "job_title": "React Native & Web Developer",
     "company_name": "Vezeeta",           "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "React,React Native,JavaScript,TypeScript,REST API,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "fe009", "job_title": "Junior Angular Developer",
     "company_name": "Xceed",             "city": "Cairo",        "experience_level": "Entry Level",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Angular,JavaScript,TypeScript,CSS,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "fe010", "job_title": "Senior Frontend Developer Next.js",
     "company_name": "Lean",              "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Remote",   "job_type": "Full Time",
     "category_tags": "Next.js,React,TypeScript,JavaScript,Tailwind CSS,Git",
     "source_category": "IT-Software-Development"},

    # ── Data Engineering (6 jobs) ─────────────────────────────────────────────
    {"job_id": "de001", "job_title": "Senior Data Engineer",
     "company_name": "Careem",            "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Python,Apache Spark,Airflow,PostgreSQL,AWS,Docker,Kafka,dbt",
     "source_category": "IT-Software-Development"},

    {"job_id": "de002", "job_title": "Data Engineer",
     "company_name": "MaxAB",             "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Python,Apache Spark,Airflow,BigQuery,GCP,Docker,SQL",
     "source_category": "IT-Software-Development"},

    {"job_id": "de003", "job_title": "Analytics Engineer",
     "company_name": "Swvl",             "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Python,dbt,Snowflake,SQL,Airflow,Git",
     "source_category": "Analyst-Research"},

    {"job_id": "de004", "job_title": "Senior Data Pipeline Engineer",
     "company_name": "Noon",              "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Remote",   "job_type": "Full Time",
     "category_tags": "Python,Kafka,Apache Spark,AWS,Redshift,Docker,Airflow,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "de005", "job_title": "Junior Data Engineer",
     "company_name": "El Sewedy Electric","city": "Cairo",        "experience_level": "Entry Level",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Python,SQL,PostgreSQL,Git,Airflow",
     "source_category": "Analyst-Research"},

    {"job_id": "de006", "job_title": "Big Data Engineer",
     "company_name": "Telecom Egypt",     "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Python,Hadoop,Apache Spark,Kafka,Hive,AWS,Docker",
     "source_category": "Engineering-Telecom-Technology"},

    # ── Data Science / ML (6 jobs) ────────────────────────────────────────────
    {"job_id": "ml001", "job_title": "Senior Machine Learning Engineer",
     "company_name": "Careem",            "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Python,TensorFlow,PyTorch,scikit-learn,Docker,AWS,MLOps,Pandas",
     "source_category": "IT-Software-Development"},

    {"job_id": "ml002", "job_title": "Data Scientist",
     "company_name": "Vodafone Egypt",    "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Python,scikit-learn,Pandas,NumPy,SQL,Machine Learning,Tableau",
     "source_category": "Analyst-Research"},

    {"job_id": "ml003", "job_title": "AI Engineer NLP",
     "company_name": "Instabug",          "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "Remote",   "job_type": "Full Time",
     "category_tags": "Python,PyTorch,NLP,Hugging Face,Large Language Models,Docker",
     "source_category": "IT-Software-Development"},

    {"job_id": "ml004", "job_title": "Computer Vision Engineer",
     "company_name": "Si-Vision",         "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Python,TensorFlow,Computer Vision,OpenCV,Docker,NumPy",
     "source_category": "IT-Software-Development"},

    {"job_id": "ml005", "job_title": "Junior Data Scientist",
     "company_name": "Jumia",             "city": "Cairo",        "experience_level": "Entry Level",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Python,scikit-learn,Pandas,SQL,Machine Learning,Git",
     "source_category": "Analyst-Research"},

    {"job_id": "ml006", "job_title": "Senior Data Analyst",
     "company_name": "Banque Misr",       "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Python,SQL,Power BI,Tableau,Pandas,Excel,Statistical Analysis",
     "source_category": "Analyst-Research"},

    # ── DevOps / Cloud (6 jobs) ───────────────────────────────────────────────
    {"job_id": "dv001", "job_title": "Senior DevOps Engineer",
     "company_name": "Paymob",            "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Docker,Kubernetes,AWS,Terraform,Jenkins,CI/CD,Linux,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "dv002", "job_title": "DevOps Engineer",
     "company_name": "Breadfast",         "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Docker,Kubernetes,GCP,Terraform,GitHub Actions,CI/CD,Linux",
     "source_category": "IT-Software-Development"},

    {"job_id": "dv003", "job_title": "Cloud Infrastructure Engineer",
     "company_name": "Vodafone Egypt",    "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "AWS,Azure,Docker,Kubernetes,Terraform,Ansible,CI/CD,Linux",
     "source_category": "Engineering-Telecom-Technology"},

    {"job_id": "dv004", "job_title": "DevOps / SRE Engineer",
     "company_name": "Instabug",          "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Remote",   "job_type": "Full Time",
     "category_tags": "Kubernetes,Docker,AWS,Prometheus,Grafana,CI/CD,Linux,Python",
     "source_category": "IT-Software-Development"},

    {"job_id": "dv005", "job_title": "Junior DevOps Engineer",
     "company_name": "Robusta",           "city": "Cairo",        "experience_level": "Entry Level",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Docker,Linux,Git,CI/CD,Jenkins,AWS",
     "source_category": "IT-Software-Development"},

    {"job_id": "dv006", "job_title": "Platform Engineer Kubernetes",
     "company_name": "Maxab",             "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Kubernetes,Docker,Terraform,AWS,Helm,ArgoCD,CI/CD,Python",
     "source_category": "IT-Software-Development"},

    # ── Full Stack (5 jobs) ───────────────────────────────────────────────────
    {"job_id": "fs001", "job_title": "Full Stack Developer React Node.js",
     "company_name": "Dsquares",          "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "React,Node.js,JavaScript,TypeScript,PostgreSQL,Docker,REST API,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "fs002", "job_title": "Senior Full Stack Engineer",
     "company_name": "Vezeeta",           "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "React,Node.js,Python,PostgreSQL,Docker,AWS,REST API,Microservices",
     "source_category": "IT-Software-Development"},

    {"job_id": "fs003", "job_title": "Full Stack Django React Developer",
     "company_name": "Halan",             "city": "Alexandria",   "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Python,Django,React,JavaScript,PostgreSQL,REST API,Docker,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "fs004", "job_title": "Junior Full Stack Developer",
     "company_name": "Flat6Labs",         "city": "Cairo",        "experience_level": "Entry Level",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "JavaScript,React,Node.js,MongoDB,REST API,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "fs005", "job_title": "Full Stack Laravel Vue Developer",
     "company_name": "Noon",              "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "PHP,Laravel,Vue.js,MySQL,REST API,Docker,Git",
     "source_category": "IT-Software-Development"},

    # ── Mobile (4 jobs) ───────────────────────────────────────────────────────
    {"job_id": "mb001", "job_title": "Senior Flutter Developer",
     "company_name": "Paymob",            "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Flutter,Dart,Firebase,REST API,Git,CI/CD",
     "source_category": "IT-Software-Development"},

    {"job_id": "mb002", "job_title": "Flutter Mobile Developer",
     "company_name": "Breadfast",         "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Flutter,Dart,Firebase,REST API,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "mb003", "job_title": "React Native Developer",
     "company_name": "Swvl",             "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "React Native,JavaScript,TypeScript,Firebase,REST API,Git",
     "source_category": "IT-Software-Development"},

    {"job_id": "mb004", "job_title": "Android Developer Kotlin",
     "company_name": "Jumia",             "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Android Development,Kotlin,Firebase,REST API,Git,Jetpack Compose",
     "source_category": "IT-Software-Development"},

    # ── QA / Testing (3 jobs) ─────────────────────────────────────────────────
    {"job_id": "qa001", "job_title": "QA Automation Engineer",
     "company_name": "Instabug",          "city": "Cairo",        "experience_level": "Experienced",
     "work_mode": "Remote",   "job_type": "Full Time",
     "category_tags": "Selenium,Python,Pytest,Jenkins,CI/CD,Jira,Agile",
     "source_category": "IT-Software-Development"},

    {"job_id": "qa002", "job_title": "Senior QA Automation Engineer",
     "company_name": "Paymob",            "city": "Cairo",        "experience_level": "Senior Management",
     "work_mode": "Hybrid",   "job_type": "Full Time",
     "category_tags": "Selenium,Java,JUnit,Jenkins,CI/CD,Jira,Agile,Postman",
     "source_category": "IT-Software-Development"},

    {"job_id": "qa003", "job_title": "Manual QA Tester",
     "company_name": "Halan",             "city": "Cairo",        "experience_level": "Entry Level",
     "work_mode": "On-site",  "job_type": "Full Time",
     "category_tags": "Jira,Postman,Agile,SQL",
     "source_category": "IT-Software-Development"},
]

# Raw jobs CSV fields (matching parser/card_parser.py output)
_JOB_FIELDS = [
    "job_id", "job_title", "job_url", "company_name", "location_raw", "city",
    "posted_date_raw", "job_type", "work_mode", "experience_level",
    "category_tags", "source_category", "scraped_at",
]


def generate(verbose: bool = True) -> None:
    """Generate both CSV files using the real extraction pipeline."""
    settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"Generating mock data for {len(MOCK_JOBS)} jobs ...")

    # ── Write raw_jobs.csv ───────────────────────────────────────────────────
    with settings.RAW_JOBS_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_JOB_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for job in MOCK_JOBS:
            row = {
                **job,
                "job_url":       f"https://wuzzuf.net/jobs/p/{job['job_id']}-mock-egypt",
                "location_raw":  f"{job['city']}, Egypt",
                "posted_date_raw": "2 days ago",
                "scraped_at":    NOW,
            }
            writer.writerow(row)

    if verbose:
        print(f"  [OK] raw_jobs.csv -- {len(MOCK_JOBS)} rows -> {settings.RAW_JOBS_CSV}")

    # ── Run extraction pipeline and write extracted_skills.csv ───────────────
    from extraction.skill_extractor import _ensure_csv_header, _append_skills_to_csv

    _ensure_csv_header(settings.EXTRACTED_SKILLS_CSV)

    total_skill_rows = 0
    for job in MOCK_JOBS:
        full_job = {
            **job,
            "job_url":    f"https://wuzzuf.net/jobs/p/{job['job_id']}-mock-egypt",
            "scraped_at": NOW,
        }
        rows = extract_skills_for_job(full_job)
        if rows:
            _append_skills_to_csv(rows, settings.EXTRACTED_SKILLS_CSV)
            total_skill_rows += len(rows)

    if verbose:
        print(f"  [OK] extracted_skills.csv -- {total_skill_rows} rows -> {settings.EXTRACTED_SKILLS_CSV}")
        print("Mock data generation complete.")


if __name__ == "__main__":
    generate(verbose=True)
