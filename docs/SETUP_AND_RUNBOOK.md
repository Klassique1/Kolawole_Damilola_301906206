# Setup, GitHub & Operations Runbook

This runbook provides reproducible steps to install the local database stack, configure repository-scoped GitHub SSH/HTTPS authentication, initialise databases, run portfolio modules progressively, and verify every deliverable.

---

## 1. Local Toolchain Installation (Windows)

### Required Software
| Tool | Purpose | Package ID (`winget`) |
| :--- | :--- | :--- |
| **Git** | Version control & progressive commits | `Git.Git` |
| **Python 3.12+** | Reusable DB runner, benchmarks, concurrency harness | `Python.Python.3.12` |
| **PostgreSQL 17** | Relational engine (Portfolios 1–3 & 5) + `psql` / pgAdmin 4 | `PostgreSQL.PostgreSQL.17` |
| **MongoDB 9 Server** | Document NoSQL engine (Portfolios 4–5) | `MongoDB.Server` |
| **MongoDB Shell** | Interactive `mongosh` CLI & script runner | `MongoDB.Shell` |
| **MongoDB Compass** *(optional)* | Visual GUI for document/index screenshots | `MongoDB.Compass.Full` |

### Option A: Zero-Admin User-Space Installation *(Used in This Environment)*
Official PostgreSQL 17, MongoDB 9, and `mongosh` archives are installed under `%USERPROFILE%\tools\databases\` and managed via `scripts/manage_local_dbs.ps1` without requiring Windows Administrator elevation or hardcoded passwords (random local dev credentials are generated directly into the gitignored `.env`):

```powershell
# First-time initialization (generates .env, runs initdb, creates least-privilege DB role, starts services)
powershell -ExecutionPolicy Bypass -File .\scripts\manage_local_dbs.ps1 -Action init

# Daily lifecycle commands
powershell -ExecutionPolicy Bypass -File .\scripts\manage_local_dbs.ps1 -Action start
powershell -ExecutionPolicy Bypass -File .\scripts\manage_local_dbs.ps1 -Action status
powershell -ExecutionPolicy Bypass -File .\scripts\manage_local_dbs.ps1 -Action stop
```

### Option B: System-Wide Install via `winget` *(Requires Admin UAC)*
Run in an **Administrator** PowerShell window:

```powershell
winget install --id Python.Python.3.12 --exact --scope user --accept-package-agreements --accept-source-agreements
winget install --id PostgreSQL.PostgreSQL.17 --exact --accept-package-agreements --accept-source-agreements
winget install --id MongoDB.Server --exact --accept-package-agreements --accept-source-agreements
winget install --id MongoDB.Shell --exact --accept-package-agreements --accept-source-agreements
```

### Verify Local Services & PATH
```powershell
python --version
psql --version
mongod --version
mongosh --version
Get-Service postgresql*, MongoDB*
```

> **Note:** If `psql` is not automatically on `PATH`, add `C:\Program Files\PostgreSQL\17\bin` to your user `PATH` environment variable and restart your terminal.

---

## 2. Repository-Scoped GitHub Configuration

To configure GitHub authentication cleanly at the repository level without storing tokens or passwords in the codebase:

### Option A: Dedicated SSH Key *(Recommended — Production Standard)*

1. **Generate an Ed25519 SSH key pair** (never store keys inside the repo):
   ```powershell
   ssh-keygen -t ed25519 -C "your_email@example.com" -f "$env:USERPROFILE\.ssh\id_ed25519_github"
   ```
2. **Copy the public key** and add it to GitHub under *Settings -> SSH and GPG keys -> New SSH key*:
   ```powershell
   Get-Content "$env:USERPROFILE\.ssh\id_ed25519_github.pub" | Set-Clipboard
   ```
3. **Configure repo-local Git identity & SSH command** inside `advanced-database-portfolio/`:
   ```powershell
   git init -b main
   git config --local user.name "Your Portfolio Name"
   git config --local user.email "your_email@example.com"
   git config --local core.sshCommand "ssh -i ~/.ssh/id_ed25519_github -o IdentitiesOnly=yes"
   git remote add origin git@github.com:<GITHUB_USERNAME>/<REPO_NAME>.git
   ```
4. **Verify SSH authentication before pushing:**
   ```powershell
   ssh -i "$env:USERPROFILE\.ssh\id_ed25519_github" -o IdentitiesOnly=yes -T git@github.com
   ```
   Expected output: `Hi <GITHUB_USERNAME>! You've successfully authenticated...`

### Option B: Repo-Scoped HTTPS via Git Credential Manager
If you prefer HTTPS instead of SSH:
```powershell
git init -b main
git config --local user.name "Your Portfolio Name"
git config --local user.email "your_email@example.com"
git config --local credential.https://github.com.username "<GITHUB_USERNAME>"
git remote add origin https://<GITHUB_USERNAME>@github.com/<GITHUB_USERNAME>/<REPO_NAME>.git
```
Embedding your GitHub username in the remote URL while keeping `credential.useHttpPath` unset lets Git Credential Manager manage authentication securely outside the repository.

### Assessor Access Requirement (PDF Section 5 & 6)
1. Ensure the GitHub repository visibility is set to **Private**.
2. Before submitting on the LMS, verify the private repository is accessible to the course assessor (for example, by inviting their provided GitHub account under *Repository -> Settings -> Collaborators*).

---

## 3. Environment & Database Initialization

1. **Create your local virtual environment and install dependencies:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .
   ```
2. **Create `.env` from `.env.example` (never commit `.env`):**
   ```powershell
   Copy-Item .env.example .env
   ```
   Update `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGADMIN_PASSWORD`, `MONGO_URI`, and `MONGO_DATABASE` to match your local installation.
3. **Create a dedicated least-privilege PostgreSQL role & database** (run once in `psql -U postgres`):
   ```sql
   CREATE ROLE novapay_app WITH LOGIN PASSWORD 'STRONG_LOCAL_PASSWORD';
   CREATE DATABASE novapay_core OWNER novapay_app;
   ```
   *(Update `novapay_app` / `novapay_core` if running a different case study from `case_study.json`.)*

---

## 4. Progressive Execution & Commit Workflow

Work through each portfolio activity incrementally, verifying outputs before committing:

1. **Foundation Commit:** Repo scaffold, `case_study.json`, `core/` harness, documentation.
2. **Portfolio 1 (`portfolio-1-database-design/`):** ER diagram, DDL migrations, constraints, verification seed -> commit.
3. **Portfolio 2 (`portfolio-2-query-optimisation/`):** Analytical workload seed, baseline `EXPLAIN (ANALYZE, BUFFERS)`, index migrations, optimised comparison report -> commit.
4. **Portfolio 3 (`portfolio-3-transactions-concurrency/`):** Atomic `COMMIT`/`ROLLBACK` transfer & reversal scripts, concurrent race condition vs. `SELECT ... FOR UPDATE` / `SERIALIZABLE` harness logs -> commit.
5. **Portfolio 4 (`portfolio-4-nosql/`):** MongoDB JSON Schema validation, compound/TTL indexes, aggregation pipelines, execution stats & justification -> commit.
6. **Portfolio 5 (`portfolio-5-distributed-cloud/`):** PostgreSQL declarative range partitioning + replication/sharding architecture & failover/CAP analysis -> commit.
7. **Final Documentation:** Polish LMS 2–3 page summary, screenshots, technical reflection, references, and AI Use Declaration -> commit.
