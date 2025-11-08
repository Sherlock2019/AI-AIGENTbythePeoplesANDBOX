"""UI tabs for the Anti-Fraud & KYC agent."""
from .intake import render_intake_tab
from .anonymize import render_anonymize_tab
from .kyc_verification import render_kyc_tab
from .fraud_detection import render_fraud_tab
from .policy import render_policy_tab
from .review import render_review_tab
from .train import render_train_tab
from .report import render_report_tab

__all__ = [
    "render_intake_tab",
    "render_anonymize_tab",
    "render_kyc_tab",
    "render_fraud_tab",
    "render_policy_tab",
    "render_review_tab",
    "render_train_tab",
    "render_report_tab",
]
