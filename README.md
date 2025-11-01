# 🏦 Banking Agent Liberty

> **AI agents for regulated banking workflows — fast, explainable, production‑ready.**
> **Thư viện tác nhân AI cho ngân hàng — nhanh, minh bạch, sẵn sàng triển khai.**

<p align="center">
  <img src="docs/hero-banner.png" alt="Banking Agent Liberty – Hero" width="960"/>
</p>

<p align="center">
  <a href="#">![Status](https://img.shields.io/badge/status-active-brightgreen)</a>
  <a href="#">![Python](https://img.shields.io/badge/Python-3.10%2B-blue)</a>
  <a href="#">![Streamlit](https://img.shields.io/badge/Streamlit-UI-red)</a>
  <a href="#">![FastAPI](https://img.shields.io/badge/API-FastAPI-teal)</a>
  <a href="#">![License](https://img.shields.io/badge/License-MIT-black)</a>
</p>

---

## 🔎 Table of Contents / Mục lục

* [What](#-what) • [So What](#-so-what) • [For Who](#-for-who) • [Where](#-where) • [What Now](#-what-now)
* [Key Features](#-key-features) • [KPIs](#-kpis) • [Architecture](#-architecture) • [Screenshots](#-screenshots)
* [Quickstart](#-quickstart) • [Docker](#-docker) • [Configuration](#-configuration)
* [Roadmap](#-roadmap) • [Contributing](#-contributing) • [License](#-license)

---

## ❓ What

**EN:** Banking Agent Liberty is a modular **AI agent library** for retail‑bank workflows. It ships with plug‑and‑play agents (Credit Appraisal, Asset Appraisal, KYC/AML helpers, Data Anonymization), a shared UI (Streamlit) and API layer (FastAPI), plus reproducible configs for on‑prem/OpenStack or cloud GPUs.

**VI:** Banking Agent Liberty là thư viện **tác nhân AI** dạng mô‑đun cho nghiệp vụ ngân hàng bán lẻ. Dự án cung cấp sẵn các agent (Thẩm định tín dụng, Định giá tài sản, hỗ trợ KYC/AML, Ẩn danh dữ liệu), UI dùng chung (Streamlit), API (FastAPI) và cấu hình triển khai lặp lại được trên OpenStack/on‑prem hoặc cloud GPU.

**Design contract / Giao ước thiết kế:** mỗi agent là một micro‑service với endpoint rõ ràng: `POST /run`, `GET /explain`, `POST /train`, `GET /health`.

---

## 💡 So What

**EN:** Traditional lending and collateral processes are slow, manual, siloed. Liberty makes them **explainable, auditable, automatable**.

* **Speed:** Synthetic seeding, one‑click anonymization, batch appraisal, cached explainability → days ➜ minutes.
* **Quality:** Feature store, SHAP‑style explainers, policy guards reduce bias & drift.
* **Compliance:** Data sovereignty defaults, verifiable logs, human‑in‑the‑loop trails for regulators.
* **Extensibility:** Swap models (HF, LightGBM, scikit‑learn) & vector DBs without UI changes.

**VI:** Quy trình tín dụng/tài sản truyền thống chậm, thủ công, rời rạc. Liberty biến chúng thành **minh bạch, kiểm toán được, tự động hóa** với tốc độ cao, chất lượng ổn định, tuân thủ chuẩn.

---

## 👥 For Who

* **EN:** Retail Banks, Fintechs, AI/Data teams, Solution Architects, Ops & Risk.
* **VI:** Ngân hàng bán lẻ, Fintech, đội AI/Dữ liệu, Kiến trúc sư giải pháp, Vận hành & Quản trị rủi ro.

---

## 📍 Where

* **EN:** Run on laptop, on‑prem OpenStack, or cloud GPUs. Data stays sovereign with edge anonymization.
* **VI:** Chạy trên máy cá nhân, OpenStack nội bộ hoặc cloud GPU; dữ liệu tuân thủ chủ quyền bằng ẩn danh tại biên.

---

## 🚀 What Now

1. **Clone & configure** (SSH)
2. **Launch Agent Hub UI** (try credit/asset flows)
3. **Connect data**: CSV/parquet or synthetic generator
4. **Ship** behind SSO & policies
5. **Measure KPIs** & iterate

> ⏩ Jump to [Quickstart](#-quickstart).

---

## ✨ Key Features

* **Credit Appraisal Agent** — decision + explanation (SHAP), scorecards, policy checks.
* **Asset Appraisal Agent** — market‑driven valuation, inspector field input, geo‑tag heatmaps.
* **Data Anonymizer** — PII masking & tokenization; reversible under custody keys.
* **Feedback → Retrain** — capture human outcomes, re‑train safely, version models.
* **Observability** — structured run IDs, audit logs, metrics, exportable reports.
* **Modular Backends** — Hugging Face, scikit‑learn/LightGBM, pluggable vector DBs.

> **Compliance lenses / Ống kính tuân thủ:** data localization, least‑privilege keys, immutable logs, model lineage.

---

## 📊 KPIs

| Domain     | KPI                              | Why it matters               | How Liberty helps                                     |
| ---------- | -------------------------------- | ---------------------------- | ----------------------------------------------------- |
| Credit     | **TAT (Time‑to‑Approve)**        | Faster decisions ➜ better CX | Synthetic seeding, batch scoring, cached explanations |
| Credit     | **Approval Quality / Default Δ** | Reduce risk                  | Feature store hygiene, policy guards, bias checks     |
| Asset      | **Valuation Variance**           | Pricing confidence           | Market comps + uncertainty bands                      |
| Asset      | **Inspector SLA**                | Field ops efficiency         | Mobile/CSV intake, geotag reminders                   |
| Ops        | **Model Drift / Fairness**       | Reliability & fairness       | Drift alerts, re‑train loop                           |
| Compliance | **Audit Completeness**           | Regulator trust              | Run IDs, artifacts, reproducible reports              |

---

## 🏗️ Architecture

```mermaid
flowchart LR
    UI[Streamlit UI]
(Landing / Agents / Runs) --> API[FastAPI]

    subgraph Agents
      CA[Credit Appraisal]
(/run /explain /train)
      AA[Asset Appraisal]
(/run /explain /train)
      DA[Data Anonymizer]
(/sanitize)
    end

    API --> CA
    API --> AA
    API --> DA

    CA --- FS[(Feature Store)]
    AA --- FS
    CA --> MLOps[(Models & Versioning)]
    AA --> MLOps
    API --> Logs[(Audit & Metrics)]
```

**Tenets / Nguyên tắc**

* Loose coupling via HTTP/JSON
* Deterministic runs with run IDs & artifacts
* Replaceable models & vector backends
* Edge anonymization + sovereign data defaults

---

## 🖼️ Screenshots

> Replace placeholders in `docs/` with your actual captures.

* **Agent Hub UI:** `docs/ui-overview.png`
* **Credit Appraisal:** `docs/ui-credit.png`
* **Asset Appraisal (map):** `docs/ui-asset-map.png`
* **Audit & Explainability:** `docs/ui-explain.png`

```html
<p align="center">
  <img src="docs/ui-overview.png" alt="Agent Hub" width="960"/>
</p>
```

---

## ⚡ Quickstart

> Requirements: Python 3.10+, Git; optional: Docker, GPU drivers.

```bash
# 1) Clone (SSH)
git clone git@github.com:Sherlock2019/banking-agent-liberty.git
cd banking-agent-liberty

# 2) Create venv & install
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r services/ui/requirements.txt
pip install -r services/api/requirements.txt

# 3) Run UI & API (two terminals)
# Terminal A (UI)
cd services/ui
streamlit run app.py

# Terminal B (API)
cd services/api
uvicorn main:app --reload --port 8000

# 4) Open the Hub
# http://localhost:8501
```

---

## 🐳 Docker

```bash
docker compose up -d --build
# Logs
docker compose logs -f ui api
```

---

## 🛠️ Configuration

```
.env
├─ AGENT__CREDIT__MODEL_DIR=agents/credit_appraisal/models/trained
├─ AGENT__ASSET__MODEL_DIR=agents/asset_appraisal/models/trained
├─ DATA__RUNS_DIR=services/ui/.runs
├─ SECURITY__ANON_KEYRING=.keys/anon
├─ GPU__PROFILE=auto   # cpu|cuda|mps|auto
```

* Put trained models under `agents/<agent>/models/trained/`
* Or start with **synthetic → anonymize → train** directly in UI
* Vector DB backends are pluggable (FAISS/pgvector/Qdrant)

---

## 🗺️ Reference Flows

**Credit Appraisal (EN/VI)**

1. Upload data / Tải dữ liệu (hoặc sinh tổng hợp)
2. Anonymize / Ẩn danh PII
3. Appraisal → score, decision, explanation / Thẩm định → điểm, quyết định, giải thích
4. Human review + policy check / Duyệt tay + kiểm chính sách
5. Export to core & logs / Xuất kết quả & lưu vết

**Asset Appraisal (EN/VI)**

1. Upload inventory or inspector report / Tải danh mục tài sản hoặc biên bản kiểm tra
2. Market comps + rules / So sánh thị trường + luật
3. Valuation + uncertainty / Định giá + độ bất định
4. Review + geo‑map / Duyệt + bản đồ vị trí
5. Export to credit flow / Đẩy sang luồng tín dụng

---

## 🧭 Roadmap

* [ ] Agent marketplace cards + per‑agent KPIs
* [ ] GPU profile selector & benchmarks
* [ ] Built‑in fairness & drift dashboards
* [ ] Pluggable vector DB (FAISS/PGVector/Qdrant)
* [ ] Multi‑tenant RBAC & SSO
* [ ] Mobile inspector intake app (offline‑first)

---

## 🤝 Contributing

* Open an issue with context (use case, data shape, compliance needs)
* Follow conventional commits
* Run tests before pushing

```bash
pytest -q
```

---

## 📄 License

MIT — see `LICENSE`.

---

### 📝 Notes

* Images in `docs/` are placeholders — replace with your branding.
* For regulated deployments, enable anonymization by default and review data residency.
