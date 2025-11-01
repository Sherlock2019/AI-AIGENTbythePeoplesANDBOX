import os, uuid, pandas as pd, numpy as np
import shap
from fpdf import FPDF
from agent_platform.agent_sdk import Agent
from model_utils import ensure_model, FEATURES

agent = Agent(name="credit_appraisal", root=os.path.dirname(__file__))

def make_pdf(report_path: str, items: list[dict], summary: dict, narrative: str | None):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Credit Appraisal Report", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Total applications: {summary['count']}", ln=True)
    pdf.cell(0, 8, f"Approved: {summary['approved']} | Denied: {summary['denied']}", ln=True)
    if narrative:
        pdf.ln(4); pdf.set_font("Arial", "B", 12); pdf.cell(0, 8, "Narrative:", ln=True)
        pdf.set_font("Arial", "", 11); pdf.multi_cell(0, 6, narrative)
    pdf.ln(4)
    pdf.set_font("Arial", "B", 12); pdf.cell(0, 8, "Top Explanations:", ln=True)
    pdf.set_font("Arial", "", 11)
    for it in items[:10]:
      pdf.multi_cell(0, 6, f"{it['application_id']}: decision={it['decision']}, "
                           f"score={it['score']:.3f}, reason={it['explanation']}")
    pdf.output(report_path)

@agent.runner
def run(inputs: dict, ctx: dict):
    csv_path = inputs["applications_csv"]
    df = pd.read_csv(csv_path)

    missing = [f for f in FEATURES if f not in df.columns]
    if missing: raise ValueError(f"Missing required columns: {missing}")

    model = ensure_model(df)
    X = df[FEATURES]
    proba = model.predict_proba(X)[:,1]
    decision = np.where(proba >= 0.5, "approve", "deny")

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    items = []
    for i in range(len(df)):
        sv = shap_values[i]
        idx = int(np.argmax(np.abs(sv)))
        feature = FEATURES[idx]
        direction = "increased" if sv[idx] > 0 else "decreased"
        explanation = f"{feature} {direction} approval likelihood most"
        items.append({
            "application_id": str(df.iloc[i].get("application_id", f"row_{i}")),
            "score": float(proba[i]),
            "decision": decision[i],
            "top_feature": feature,
            "shap": float(sv[idx]),
            "explanation": explanation
        })

    approved = int((decision == "approve").sum())
    summary = {"count": len(df), "approved": approved, "denied": int(len(df) - approved)}

    narrative = ctx.get("narrative") if isinstance(ctx, dict) else None

    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "services", "api", ".runs")
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, f"credit_report_{uuid.uuid4().hex}.pdf")
    make_pdf(report_path, items, summary, narrative)

    return {
      "scores": [{"application_id": it["application_id"], "score": it["score"], "decision": it["decision"]} for it in items],
      "explanations": items,
      "artifacts": {"explanation_pdf": report_path},
      "summary": summary
    }
