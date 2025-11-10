## 🧩 Unified Risk Orchestration Agent

The missing layer above the Asset, Credit, and Anti-Fraud/KYC agents is a supervisor that composes their outputs into one bank-grade verdict. It is the “brain” that coordinates sequencing, merges artifacts, and publishes the final package stakeholders need.

### 1. Quick Definition

| Agent | Role (What it is) | Core Tasks (What it does) | Key Features (How it works) |
| --- | --- | --- | --- |
| 🧩 **Unified Risk Orchestration Agent** | Top-level coordinator that composes Asset + Credit + KYC into a single decision | • Trigger Asset → Fraud/KYC → Credit pipeline in the correct order<br>• Pass outputs/artifacts across agents<br>• Standardize schemas/metadata<br>• Merge valuations + fraud signals + credit scores<br>• Auto-route exceptions to humans<br>• Publish APIs for LOS/CRM integrations | • Multi-agent DAG orchestrator (priority-aware)<br>• Cross-agent schema harmonization layer<br>• Rule-based priority routing (e.g., freeze if fraud risk high)<br>• Aggregated risk score = f(asset_value, fraud_risk, credit_pd)<br>• Generates `unified_risk_decision.json` + evidence bundle |

### 2. Why It’s Needed

Banks can’t rely on a stack of independent agent outputs. The underwriting desk, risk committee, and LOS/LMS expect **one** final answer:

1. **Identity / Fraud** – Is the borrower real and low risk?
2. **Collateral** – Is the pledged asset actually worth enough?
3. **Credit** – Can the borrower repay (PD, rules, explainability)?
4. **Unified decision** – Given 1–3, should we approve, review, or reject?

Only a master coordinator can guarantee the interactions (e.g., rerun asset valuation if fraud triggers “re-inspect document”) and keep downstream evidence in sync.

### 3. What the Agent Produces

**Primary artifact:** `unified_risk_decision.json`

Includes:

- Borrower identity check, sanctions hits, fraud risk tier.
- Asset FMV, `ai_adjusted`, realizable value, encumbrance notes.
- Credit metrics (score, PD, rule explanations, approval decision).
- Consolidated risk tier + aggregated score.
- Final recommendation (`approve`, `review`, `reject`) with reason codes.
- Evidence index (documents, transcripts, images) for audit + regulators.

Secondary artifacts:

- `unified_risk_report.pdf` for human review.
- API payload for LOS/CRM so downstream systems ingest the same verdict.

### 4. Pipeline Responsibilities

1. **Trigger order**: Asset → Fraud/KYC → Credit by default (configurable DAG).
2. **Data sharing**: Provide normalized payloads (JSON + optional CSV) between stages.
3. **Priority routing**: e.g., if fraud risk > threshold, skip credit and flag human review.
4. **Schema harmonization**: Align borrower IDs, collateral IDs, run IDs across agents.
5. **Explainability envelope**: Merge reason codes from all agents into one narrative.
6. **Exception workflows**: When any stage fails, orchestrator emits tasks for humans.

### 5. Integration Targets

- **Credit Officers / Underwriters** – receive the PDF + interactive dashboard.
- **Risk Committee** – gets weekly/monthly aggregated exports.
- **Core Banking / LOS / LMS / CRM** – consume the unified JSON via API.

### 6. Implementation Notes / Next Steps

1. **Controller Service** – add a `unified_agent` FastAPI router that:
   - Accepts borrower payloads.
   - Calls existing agent APIs in sequence.
   - Stores intermediate artifacts (.tmp_runs) for audit.
2. **State Machine** – maintain DAG + rules (e.g., `fraud_high` → reroute).
3. **Evidence Bundler** – packaging script to gather CSV/JSON/images into one deliverable.
4. **Streamlit UI** – add “Unified Risk Agent” page to monitor pipeline runs and download the final package.
5. **API Contract** – publish `POST /v1/unified_decision` returning `unified_risk_decision.json`.

Once in place, Asset + Credit + Fraud agents remain specialists, while the Unified Risk Orchestration Agent compounds their strengths into a single, bank-ready decision artifact.

### 7. Current Implementation Snapshot

- `POST /v1/unified/decision` (FastAPI) accepts a borrower ID and the latest asset/fraud/credit metrics, computes an aggregated risk tier + recommendation, and persists `unified_risk_decision.json` under `services/api/.runs/unified/`.
- `services/ui/pages/unified_risk.py` is the new Streamlit dashboard that lets operators submit borrower snapshots, view the unified verdict, and download the JSON artifact while monitoring overall portfolio status.
- Landing → Agents table now lists the 🧩 Unified Risk Orchestration Agent so operators can reach the dashboard alongside the domain agents.
