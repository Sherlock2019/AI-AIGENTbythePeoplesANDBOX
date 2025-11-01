import pandas as pd
import re

def preprocess_kaggle_dataset(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # --- Step 1: Standardize column names ---
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # --- Step 2: Drop PII ---
    pii_patterns = ["name", "email", "phone", "address"]
    df = df[[c for c in df.columns if not any(p in c for p in pii_patterns)]]

    # --- Step 3: Convert datatypes ---
    for col in ["income", "loan_amount", "collateral_value", "existing_debt"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # --- Step 4: Add missing credit features if needed ---
    if "dti" not in df.columns and {"income", "existing_debt"} <= set(df.columns):
        df["dti"] = df["existing_debt"] / (df["income"] + 1e-9)

    if "ltv" not in df.columns and {"loan_amount", "collateral_value"} <= set(df.columns):
        df["ltv"] = df["loan_amount"] / (df["collateral_value"] + 1e-9)

    # --- Step 5: Ensure consistent schema ---
    if "application_id" not in df.columns:
        df.insert(0, "application_id", [f"APP_{i:04d}" for i in range(1, len(df) + 1)])

    return df

