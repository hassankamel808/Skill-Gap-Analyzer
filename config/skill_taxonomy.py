"""
config/skill_taxonomy.py
========================
Master skill taxonomy, alias normalization map, role-category keyword
dictionary, and classification priority list.

DATA STRUCTURES
---------------
SKILL_TAXONOMY        — dict[category_label -> list[canonical_skill]]
SKILL_ALIAS_MAP       — dict[raw_variant -> canonical_skill]
ROLE_CATEGORY_KEYWORDS — dict[role_label -> list[title_keywords]]
ROLE_CATEGORY_PRIORITY — list[role_label] (ordered, first-match wins)

HELPER FUNCTIONS
----------------
get_all_skills()      — flat list of every canonical skill across all categories
get_canonical(raw)    — resolve a raw string to its canonical form (or None)
classify_role(title)  — classify a job title string into a role category
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. SKILL TAXONOMY
# ---------------------------------------------------------------------------
# Keys are human-readable category labels.
# Values are lists of CANONICAL skill names (used throughout the pipeline).
# ---------------------------------------------------------------------------

SKILL_TAXONOMY: dict[str, list[str]] = {

    "programming_languages": [
        "Python",
        "JavaScript",
        "TypeScript",
        "Java",
        "C#",
        "C++",
        "C",
        "Go",
        "Rust",
        "Kotlin",
        "Swift",
        "Ruby",
        "PHP",
        "Scala",
        "R",
        "Dart",
        "SQL",
        "Bash",
        "PowerShell",
        "MATLAB",
        "Perl",
        "Groovy",
        "Elixir",
        "Haskell",
    ],

    "frameworks_libraries": [
        # Frontend
        "React",
        "Angular",
        "Vue.js",
        "Next.js",
        "Svelte",
        "jQuery",
        "Bootstrap",
        "Tailwind CSS",
        # Backend / Full-Stack
        "Node.js",
        "Express.js",
        "NestJS",
        "Django",
        "Flask",
        "FastAPI",
        "Spring Boot",
        "Spring Framework",
        "ASP.NET",
        ".NET",
        "Laravel",
        "Ruby on Rails",
        "Symfony",
        "Gin",
        # Mobile
        "Flutter",
        "React Native",
        "SwiftUI",
        "Jetpack Compose",
        # Data / ML
        "TensorFlow",
        "PyTorch",
        "Keras",
        "scikit-learn",
        "XGBoost",
        "LightGBM",
        "Pandas",
        "NumPy",
        "SciPy",
        "Matplotlib",
        "Seaborn",
        "Plotly",
        # Big Data
        "Apache Spark",
        "Hadoop",
        "Kafka",
        "Flink",
        "Airflow",
        "dbt",
        # API
        "GraphQL",
        "REST API",
        "gRPC",
        "WebSocket",
    ],

    "databases": [
        "PostgreSQL",
        "MySQL",
        "MongoDB",
        "Redis",
        "Elasticsearch",
        "Cassandra",
        "DynamoDB",
        "Oracle DB",
        "SQL Server",
        "Neo4j",
        "Firebase",
        "SQLite",
        "MariaDB",
        "Snowflake",
        "BigQuery",
        "Redshift",
        "CockroachDB",
        "InfluxDB",
        "Couchbase",
    ],

    "devops_cloud": [
        # Cloud Platforms
        "AWS",
        "Azure",
        "GCP",
        # Containerisation / Orchestration
        "Docker",
        "Kubernetes",
        "Helm",
        "ArgoCD",
        # Infrastructure as Code
        "Terraform",
        "Ansible",
        "Pulumi",
        "CloudFormation",
        # CI/CD
        "CI/CD",
        "Jenkins",
        "GitHub Actions",
        "GitLab CI",
        "CircleCI",
        "Travis CI",
        "Azure DevOps",
        "Bamboo",
        # Monitoring / Observability
        "Prometheus",
        "Grafana",
        "Datadog",
        "New Relic",
        "ELK Stack",
        "Splunk",
        "Jaeger",
        # Web Servers / Proxies
        "Nginx",
        "Apache",
        "HAProxy",
        # OS / Networking
        "Linux",
        "Unix",
        "Bash Scripting",
        "Networking",
        "TCP/IP",
        "DNS",
        "VPN",
        # Secrets / Security Tools
        "Vault",
        "IAM",
    ],

    "data_ml_ai": [
        "Machine Learning",
        "Deep Learning",
        "NLP",
        "Computer Vision",
        "Large Language Models",
        "RAG",
        "MLOps",
        "Data Engineering",
        "ETL",
        "Data Warehouse",
        "Data Lake",
        "Feature Engineering",
        "Model Deployment",
        "A/B Testing",
        "Statistical Analysis",
        "Time Series Analysis",
        "Recommendation Systems",
        "Reinforcement Learning",
        "Generative AI",
        "LangChain",
        "Hugging Face",
        "OpenAI API",
        "Databricks",
        "Tableau",
        "Power BI",
        "Looker",
        "Metabase",
        "Superset",
    ],

    "cybersecurity": [
        "Cybersecurity",
        "Penetration Testing",
        "Vulnerability Assessment",
        "SIEM",
        "SOC",
        "OWASP",
        "ISO 27001",
        "Network Security",
        "Application Security",
        "Cloud Security",
        "Zero Trust",
        "Encryption",
        "PKI",
        "Firewalls",
        "IDS/IPS",
        "Threat Intelligence",
        "Incident Response",
        "Digital Forensics",
        "Ethical Hacking",
        "Burp Suite",
        "Metasploit",
        "Nmap",
        "Wireshark",
        "GDPR Compliance",
        "HIPAA",
        "PCI-DSS",
    ],

    "tools_practices": [
        # Version Control
        "Git",
        "GitHub",
        "GitLab",
        "Bitbucket",
        # Project Management
        "Jira",
        "Confluence",
        "Trello",
        "Notion",
        "Asana",
        # Methodologies
        "Agile",
        "Scrum",
        "Kanban",
        "SAFe",
        "Lean",
        # Architecture / Design
        "Microservices",
        "Service Mesh",
        "Event-Driven Architecture",
        "Domain-Driven Design",
        "Design Patterns",
        "System Design",
        "API Design",
        "TDD",
        "BDD",
        "Code Review",
        # Auth / Security Concepts
        "OAuth",
        "JWT",
        "SSO",
        "LDAP",
        # QA / Testing Tools
        "Selenium",
        "Playwright",
        "Cypress",
        "Jest",
        "Pytest",
        "JUnit",
        "Postman",
        "SoapUI",
        "Appium",
        "TestNG",
        "LoadRunner",
        "JMeter",
        # UI/UX Tools
        "Figma",
        "Adobe XD",
        "Sketch",
        "InVision",
        "Zeplin",
    ],

    "mobile": [
        "iOS Development",
        "Android Development",
        "Cross-Platform Development",
        "Push Notifications",
        "App Store Deployment",
        "Google Play Deployment",
        "Mobile UI Design",
        "SQLite",
        "Core Data",
        "Realm",
        "BLE / Bluetooth",
    ],
}

# ---------------------------------------------------------------------------
# 2. SKILL ALIAS MAP
# ---------------------------------------------------------------------------
# Maps raw/variant skill strings to their CANONICAL form in SKILL_TAXONOMY.
# Keys are lower-cased for case-insensitive resolution.
# Values are the EXACT canonical string as it appears in SKILL_TAXONOMY.
# ---------------------------------------------------------------------------

SKILL_ALIAS_MAP: dict[str, str] = {

    # Python
    "python3": "Python",
    "python 3": "Python",
    "py": "Python",

    # JavaScript
    "js": "JavaScript",
    "javascript es6": "JavaScript",
    "es6": "JavaScript",
    "es2015": "JavaScript",
    "vanilla js": "JavaScript",
    "vanilla javascript": "JavaScript",

    # TypeScript
    "ts": "TypeScript",

    # Java
    "java 8": "Java",
    "java 11": "Java",
    "java 17": "Java",
    "java 21": "Java",
    "core java": "Java",

    # C#
    "c sharp": "C#",
    "csharp": "C#",
    "c# .net": "C#",

    # C++
    "c plus plus": "C++",
    "cpp": "C++",

    # Go
    "golang": "Go",
    "go language": "Go",

    # SQL
    "t-sql": "SQL",
    "tsql": "SQL",
    "pl/sql": "SQL",
    "plsql": "SQL",
    "oracle sql": "SQL",
    "hql": "SQL",
    "nosql": "SQL",           # loose — extractor should gate context

    # React
    "react.js": "React",
    "reactjs": "React",
    "react js": "React",
    "react.js developer": "React",
    "reactjs developer": "React",

    # Angular
    "angularjs": "Angular",
    "angular js": "Angular",
    "angular 2+": "Angular",
    "angular 14": "Angular",
    "angular 17": "Angular",

    # Vue.js
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue js": "Vue.js",
    "vue 3": "Vue.js",

    # Next.js
    "nextjs": "Next.js",
    "next js": "Next.js",

    # Node.js
    "node": "Node.js",
    "nodejs": "Node.js",
    "node js": "Node.js",
    "node.js developer": "Node.js",

    # Express.js
    "express": "Express.js",
    "expressjs": "Express.js",

    # NestJS
    "nest": "NestJS",
    "nest.js": "NestJS",

    # Spring Boot
    "spring": "Spring Boot",        # gate with context in extractor
    "spring mvc": "Spring Boot",
    "spring security": "Spring Boot",
    "spring cloud": "Spring Boot",

    # .NET / ASP.NET
    "dotnet": ".NET",
    ".net core": ".NET",
    "asp.net core": "ASP.NET",
    "asp.net mvc": "ASP.NET",
    "asp.net web api": "ASP.NET",

    # Django
    "django rest framework": "Django",
    "drf": "Django",

    # Flask
    "flask api": "Flask",

    # FastAPI
    "fast api": "FastAPI",

    # TensorFlow
    "tensorflow 2": "TensorFlow",
    "tf": "TensorFlow",

    # PyTorch
    "torch": "PyTorch",

    # scikit-learn
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",

    # Pandas
    "pandas library": "Pandas",

    # Apache Spark
    "spark": "Apache Spark",
    "pyspark": "Apache Spark",

    # Kafka
    "apache kafka": "Kafka",

    # Airflow
    "apache airflow": "Airflow",

    # dbt
    "data build tool": "dbt",

    # REST API
    "restful api": "REST API",
    "rest": "REST API",
    "restful": "REST API",
    "restful web services": "REST API",
    "restful services": "REST API",

    # GraphQL
    "graph ql": "GraphQL",

    # PostgreSQL
    "postgres": "PostgreSQL",
    "psql": "PostgreSQL",
    "postgresql db": "PostgreSQL",

    # MySQL
    "my sql": "MySQL",

    # MongoDB
    "mongo": "MongoDB",
    "mongo db": "MongoDB",

    # SQL Server
    "mssql": "SQL Server",
    "ms sql": "SQL Server",
    "ms sql server": "SQL Server",
    "microsoft sql server": "SQL Server",

    # Oracle DB
    "oracle": "Oracle DB",
    "oracle database": "Oracle DB",

    # Redis
    "redis cache": "Redis",

    # Elasticsearch
    "elastic search": "Elasticsearch",
    "elastic": "Elasticsearch",
    "elk": "ELK Stack",

    # Firebase
    "firebase realtime db": "Firebase",
    "firestore": "Firebase",

    # AWS
    "amazon web services": "AWS",
    "amazon aws": "AWS",

    # Azure
    "microsoft azure": "Azure",
    "azure cloud": "Azure",

    # GCP
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "google cloud services": "GCP",

    # Kubernetes
    "k8s": "Kubernetes",
    "k 8 s": "Kubernetes",

    # Docker
    "docker container": "Docker",
    "containerization": "Docker",
    "docker compose": "Docker",

    # Terraform
    "terraform iac": "Terraform",

    # CI/CD
    "cicd": "CI/CD",
    "ci cd": "CI/CD",
    "continuous integration": "CI/CD",
    "continuous deployment": "CI/CD",
    "continuous delivery": "CI/CD",

    # GitHub Actions
    "github action": "GitHub Actions",

    # GitLab CI
    "gitlab pipeline": "GitLab CI",

    # Machine Learning
    "ml": "Machine Learning",

    # Deep Learning
    "dl": "Deep Learning",

    # NLP
    "natural language processing": "NLP",
    "text mining": "NLP",
    "nlp engineer": "NLP",

    # Computer Vision
    "cv": "Computer Vision",
    "image processing": "Computer Vision",
    "opencv": "Computer Vision",

    # Large Language Models
    "llm": "Large Language Models",
    "llms": "Large Language Models",
    "large language model": "Large Language Models",
    "gpt": "Large Language Models",
    "chatgpt": "Large Language Models",

    # RAG
    "retrieval augmented generation": "RAG",
    "retrieval-augmented generation": "RAG",

    # MLOps
    "ml ops": "MLOps",

    # ETL
    "etl pipeline": "ETL",
    "elt": "ETL",
    "data integration": "ETL",

    # Power BI
    "powerbi": "Power BI",
    "power bi desktop": "Power BI",
    "microsoft power bi": "Power BI",

    # Tableau
    "tableau desktop": "Tableau",

    # Data Warehouse
    "data warehousing": "Data Warehouse",
    "dwh": "Data Warehouse",
    "edw": "Data Warehouse",

    # Penetration Testing
    "pentest": "Penetration Testing",
    "pentesting": "Penetration Testing",
    "ethical hacking": "Ethical Hacking",

    # Git
    "git version control": "Git",

    # Agile
    "agile methodology": "Agile",
    "agile development": "Agile",

    # Scrum
    "scrum master": "Scrum",
    "scrum methodology": "Scrum",

    # Design Patterns
    "software design patterns": "Design Patterns",
    "oop": "Design Patterns",
    "object-oriented programming": "Design Patterns",
    "solid principles": "Design Patterns",

    # System Design
    "software architecture": "System Design",
    "solution architecture": "System Design",
    "distributed systems": "System Design",

    # TDD
    "test driven development": "TDD",
    "test-driven development": "TDD",

    # Figma
    "figma design": "Figma",

    # iOS Development
    "ios": "iOS Development",
    "ios development": "iOS Development",
    "ios developer": "iOS Development",

    # Android Development
    "android": "Android Development",
    "android development": "Android Development",
    "android sdk": "Android Development",

    # Flutter
    "flutter development": "Flutter",
    "flutter developer": "Flutter",

    # React Native
    "react-native": "React Native",
    "rn": "React Native",
}

# ---------------------------------------------------------------------------
# 3. ROLE CATEGORY KEYWORDS
# ---------------------------------------------------------------------------
# Maps a role category label to a list of lower-cased title keyword phrases.
# Classification uses first-match on ROLE_CATEGORY_PRIORITY (see below).
# ---------------------------------------------------------------------------

ROLE_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Backend": [
        "backend",
        "back-end",
        "back end",
        "server-side",
        "api developer",
        "microservices",
        "java developer",
        "python developer",
        ".net developer",
        "php developer",
        "node developer",
        "spring developer",
    ],
    "Frontend": [
        "frontend",
        "front-end",
        "front end",
        "ui developer",
        "react developer",
        "angular developer",
        "vue developer",
        "javascript developer",
        "web developer",
    ],
    "Full Stack": [
        "full stack",
        "fullstack",
        "full-stack",
    ],
    "Data Science / ML": [
        "data scientist",
        "machine learning",
        "ml engineer",
        "ai engineer",
        "data analyst",
        "nlp engineer",
        "computer vision",
        "deep learning engineer",
    ],
    "Data Engineering": [
        "data engineer",
        "etl",
        "data pipeline",
        "big data",
        "spark engineer",
        "analytics engineer",
    ],
    "DevOps / Cloud": [
        "devops",
        "sre",
        "cloud engineer",
        "infrastructure",
        "platform engineer",
        "site reliability",
        "devsecops",
    ],
    "Mobile": [
        "ios",
        "android",
        "mobile developer",
        "flutter",
        "react native",
        "swift developer",
        "kotlin developer",
    ],
    "QA / Testing": [
        "qa",
        "test engineer",
        "sdet",
        "quality assurance",
        "automation tester",
        "manual tester",
        "testing engineer",
    ],
    "Cybersecurity": [
        "security engineer",
        "penetration tester",
        "soc analyst",
        "cybersecurity",
        "information security",
        "infosec",
        "network security engineer",
    ],
    "UI/UX": [
        "ui/ux",
        "ux developer",
        "interaction designer",
        "product designer",
        "ui designer",
        "ux designer",
    ],
}

# ---------------------------------------------------------------------------
# 4. ROLE CATEGORY PRIORITY
# ---------------------------------------------------------------------------
# Classification iterates this list IN ORDER and returns the FIRST match.
# More specific / less ambiguous categories are placed earlier.
# "Other Tech" is the fallback when no keyword matches.
# ---------------------------------------------------------------------------

ROLE_CATEGORY_PRIORITY: list[str] = [
    "Data Science / ML",
    "Data Engineering",
    "Cybersecurity",
    "DevOps / Cloud",
    "Mobile",
    "QA / Testing",
    "UI/UX",
    "Backend",
    "Frontend",
    "Full Stack",
    "Other Tech",
]

# ---------------------------------------------------------------------------
# 5. HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_all_skills() -> list[str]:
    """
    Return a flat, deduplicated list of every canonical skill across all
    taxonomy categories, sorted alphabetically.

    Returns
    -------
    list[str]
        All canonical skill strings.
    """
    seen: set[str] = set()
    result: list[str] = []
    for skills in SKILL_TAXONOMY.values():
        for skill in skills:
            if skill not in seen:
                seen.add(skill)
                result.append(skill)
    return sorted(result)


def get_canonical(raw: str) -> str | None:
    """
    Resolve a raw/variant skill string to its canonical form.

    Resolution order:
    1. Exact case-insensitive match in SKILL_ALIAS_MAP.
    2. Exact case-insensitive match against canonical skills in SKILL_TAXONOMY.
    3. Return None if no match found (caller decides how to handle).

    Parameters
    ----------
    raw : str
        Unprocessed skill string (e.g. "reactjs", "  React.JS ", "k8s").

    Returns
    -------
    str | None
        Canonical skill name, or None if not found.
    """
    normalized = raw.strip().lower()

    # Step 1: alias map lookup
    if normalized in SKILL_ALIAS_MAP:
        return SKILL_ALIAS_MAP[normalized]

    # Step 2: direct match against canonical skill names (case-insensitive)
    all_skills = get_all_skills()
    skill_lower_map = {s.lower(): s for s in all_skills}
    if normalized in skill_lower_map:
        return skill_lower_map[normalized]

    return None


def classify_role(title: str) -> str:
    """
    Classify a job title string into a role category using keyword matching.

    Iterates ROLE_CATEGORY_PRIORITY in order and returns the label of the
    FIRST category whose keywords appear in the lower-cased title.
    Falls back to "Other Tech" if no match is found.

    Parameters
    ----------
    title : str
        Raw job title string (e.g. "Senior Data Engineer", "iOS Developer").

    Returns
    -------
    str
        Role category label (e.g. "Data Engineering", "Mobile", "Other Tech").
    """
    title_lower = title.strip().lower()

    for category in ROLE_CATEGORY_PRIORITY:
        if category == "Other Tech":
            # Fallback — always matches
            return "Other Tech"
        keywords = ROLE_CATEGORY_KEYWORDS.get(category, [])
        for keyword in keywords:
            if keyword in title_lower:
                return category

    return "Other Tech"


def get_skill_category(canonical_skill: str) -> str | None:
    """
    Return the taxonomy category label for a given canonical skill name.

    Parameters
    ----------
    canonical_skill : str
        A canonical skill string (e.g. "Python", "Docker", "React").

    Returns
    -------
    str | None
        The category label (e.g. "programming_languages"), or None if not found.
    """
    for category, skills in SKILL_TAXONOMY.items():
        if canonical_skill in skills:
            return category
    return None
