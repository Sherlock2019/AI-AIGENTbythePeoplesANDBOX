"""Unified credit + asset appraisal policy text embedded into the RAG store."""
from __future__ import annotations

CREDIT_ASSET_POLICY_TEXT = """🧩 Unified Policy Summary for Credit & Asset Appraisal

A clean, consolidated policy view used across Risk, Credit, and Asset Agents.

🏦 1. Credit Appraisal Policies (Borrower + Loan Evaluation)
1.1 Borrower Eligibility

Must provide complete KYC/ID, income proof, liabilities.

Must meet minimum age & residency requirements.

Must have no unresolved fraud or sanctions alerts from KYC Agent.

1.2 Income & DTI (Debt-to-Income) Policy

DTI = Total Monthly Obligations / Monthly Income

DTI ≤ 40% → Acceptable

40% < DTI ≤ 50% → Review/Enhanced Assessment

DTI > 50% → High Risk / Reject

Additional rules:

Income anomalies require verification (bank statements, tax forms).

Seasonal income requires 6-month average.

1.3 Credit Score / PD (Probability of Default) Policy

PD ≤ 5% → Low Risk

5% < PD ≤ 15% → Medium Risk (Require additional checks)

PD > 15% → High Risk / Decline or require collateral

Override rules:

Manual overrides must capture rationale.

Large unsecured loans must meet higher score thresholds.

1.4 LTV (Loan-to-Value) Policy

LTV = Loan Amount / Appraised Asset Value

LTV ≤ 70% → Safe

70% < LTV ≤ 80% → Review / Require additional documents

LTV > 80% → Reject or apply additional collateral

Special cases:

First-time borrowers: cap LTV at 75%.

High-risk industries: reduce max LTV by 5–10%.

1.5 Income Verification Policy

Mandatory verification for loan amounts > $5,000.

Multiple income sources require consolidated verification.

High fluctuation (>30% month-to-month) triggers enhanced checks.

1.6 Adverse Credit (Negative History) Policy

Any recent delinquency (<12 months) triggers manual review.

Bankruptcy within last 7 years → reject unless secured.

Defaults automatically require collateral.

1.7 Decision Policy Matrix
DTI	PD	LTV	Decision
≤40%	≤5%	≤70%	Approve
≤40%	5–15%	≤80%	Review
>50%	any	>80%	Reject
Medium DTI + Medium PD	≤70%	Review with enhanced verification	
🏡 2. Asset Appraisal Policies (Collateral Evaluation)
2.1 Fair Market Value (FMV) Policy

FMV is computed using:

Comparable assets (“comps”)

Condition score

Geographic factors

Age, model, usage, depreciation curves

FMV must be:

Traceable

Data-driven

Cross-checked with external comps

2.2 AI-Adjusted Value Policy

AI-adjusted FMV considers:

Encumbrances or liens

Fraud signals

Seller misreporting

Operator overrides

Policy:

AI-adjusted value must be at least 90% consistent with comps.

Differences >10% require manual review.

2.3 Haircut Policy (Risk Deduction)

Haircuts reduce FMV to create Realizable Value.

Haircut examples:

Real estate: 5–20% depending on condition

Vehicles: 10–30% depending on age >5 years

Electronics: 20–40% unless nearly new

Rules:

Apply highest haircut when data quality is low.

Haircuts stack with fraud flags.

2.4 Encumbrance / Legal Verification

Failure cases:

Conflicting ownership

Lien or loan already registered

Missing proof of ownership

Stolen or disputed items

Policy:

Any encumbrance → automatically set encumbrance_flag = 1

Blocks approval unless cleared manually.

2.5 Collateral Acceptability

Asset must satisfy:

Traceable ownership

Photos or documents to prove possession

No critical damage

Not blacklisted (fraud/stolen lists)

Unacceptable collateral:

Unregistered property

Heavily damaged assets

Digital goods (unless platform-verified)

Perishables (food, flowers, livestock)

High-theft items without verification

2.6 Final Collateral Value Policy

Realizable Value = AI-Adjusted FMV × (1 – Haircut)

This value is used in LTV calculation for credit decisions.

🔗 3. Cross-Agent Policies (Credit ↔ Asset)
3.1 Collateral Must Match Borrower Data

Cross-check:

Borrower name ↔ asset owner

Address ↔ property docs

Loan type ↔ asset category

Mismatch → Review manually.

3.2 Combined Risk Score

Consolidated risk is computed as:

Combined Risk = PD + (Encumbrance Risk × 0.5) + (LTV Risk)


If Combined Risk > 25% → Reject or require co-signer.

3.3 Fraud Overrides

If Fraud Agent flags:

Synthetic ID

Inconsistent income

Face mismatch

Suspicious documents

Duplicate device ID across multiple applications

→ Entire appraisal + credit review is paused.

🔥 4. Approval / Decline Rules
APPROVE

PD ≤ 10%

DTI ≤ 45%

LTV ≤ 70%

No fraud flags

Clean asset with realizable value > loan amount

REVIEW

Medium DTI (40–50%)

Medium PD (5–15%)

Minor inconsistencies in documents

Some haircut but realizable value still acceptable

REJECT

PD > 15%

DTI > 50%

LTV > 85%

Asset encumbrance

Fraud Agent red flags

Missing required documentation
"""

__all__ = ["CREDIT_ASSET_POLICY_TEXT"]
