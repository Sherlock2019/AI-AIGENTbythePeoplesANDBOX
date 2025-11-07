# ───────────────────────────────────────────────
# G — DEPLOYMENT & EXPORT STAGE
# ───────────────────────────────────────────────
import os, glob, hashlib, json, zipfile, requests
import streamlit as st
from datetime import datetime, timezone
from pathlib import Path

st.set_page_config(page_title="Stage G — Deployment & Export", page_icon="🚀")

st.title("🚀 Stage G — Deployment & Export")
st.caption("Package, verify, and publish production bundles for external deployment.")

EXPORT_DIR = Path("./exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

# ───────────────────────────────────────────────
# 1️⃣ Detect the latest ZIP archive
# ───────────────────────────────────────────────
st.subheader("📦 Detected Export Packages")
zip_files = sorted(EXPORT_DIR.glob("export_production_*.zip"), reverse=True)
if not zip_files:
    st.warning("⚠️ No export ZIP found. Run Stage F and export first.")
    st.stop()

latest_zip = zip_files[0]
st.success(f"✅ Latest package: `{latest_zip.name}` ({latest_zip.stat().st_size/1e6:.2f} MB)")

# ───────────────────────────────────────────────
# 2️⃣ Compute checksum + digital signature
# ───────────────────────────────────────────────
st.subheader("🔐 Checksum & Integrity Verification")

sha256 = hashlib.sha256(latest_zip.read_bytes()).hexdigest()
checksum_file = latest_zip.with_suffix(".sha256")
checksum_file.write_text(sha256)
st.code(sha256, language="text")
st.caption(f"Checksum saved → `{checksum_file.name}`")

# Optional: simple signature stub (replace with real key-based signing if needed)
signature_file = latest_zip.with_suffix(".sig")
signature_file.write_text(f"SIGNED BY AI-AGENT-HUB @ {datetime.now(timezone.utc).isoformat()}")
st.caption(f"Signature stub saved → `{signature_file.name}`")

# ───────────────────────────────────────────────
# 3️⃣ Upload options (S3 / Swift / GitHub)
# ───────────────────────────────────────────────
st.subheader("☁️ Upload Options")

dest = st.radio("Choose target destination", ["AWS S3", "OpenStack Swift", "GitHub Release"])

if dest == "AWS S3":
    st.info("Upload via boto3 (requires AWS credentials).")
    bucket = st.text_input("S3 Bucket Name", "my-ai-models")
    key = st.text_input("S3 Object Key", latest_zip.name)
    if st.button("⬆️ Upload to S3"):
        import boto3
        try:
            s3 = boto3.client("s3")
            s3.upload_file(str(latest_zip), bucket, key)
            st.success(f"✅ Uploaded to s3://{bucket}/{key}")
        except Exception as e:
            st.error(f"❌ Upload failed: {e}")

elif dest == "OpenStack Swift":
    st.info("Upload via python-swiftclient (requires Swift credentials).")
    container = st.text_input("Swift Container", "models")
    if st.button("⬆️ Upload to Swift"):
        try:
            from swiftclient.service import SwiftService, SwiftUploadObject
            with SwiftService() as swift:
                swift.upload(container, [SwiftUploadObject(str(latest_zip))])
            st.success(f"✅ Uploaded to Swift container `{container}`")
        except Exception as e:
            st.error(f"❌ Swift upload failed: {e}")

elif dest == "GitHub Release":
    st.info("Upload via GitHub API (requires token).")
    repo = st.text_input("GitHub Repo (e.g. username/repo)", "RackspaceAI/asset-appraisal-agent")
    token = st.text_input("Personal Access Token", type="password")
    tag = datetime.now().strftime("v%Y%m%d-%H%M%S")
    if st.button("⬆️ Upload to GitHub Release"):
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
        try:
            # Create release
            r = requests.post(f"https://api.github.com/repos/{repo}/releases",
                              headers=headers,
                              json={"tag_name": tag, "name": f"Model Release {tag}",
                                    "body": "Automated deployment from Stage G"})
            r.raise_for_status()
            upload_url = r.json()["upload_url"].split("{")[0]
            with open(latest_zip, "rb") as f:
                ur = requests.post(f"{upload_url}?name={latest_zip.name}",
                                   headers={**headers, "Content-Type": "application/zip"}, data=f)
            ur.raise_for_status()
            st.success(f"✅ Uploaded to GitHub Release `{tag}`")
        except Exception as e:
            st.error(f"❌ GitHub upload failed: {e}")

# ───────────────────────────────────────────────
# 4️⃣ Deployment Audit Record
# ───────────────────────────────────────────────
st.subheader("🧾 Deployment Audit")
audit_record = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "export_file": latest_zip.name,
    "checksum": sha256,
    "destination": dest,
}
with open(EXPORT_DIR / "deployment_audit.json", "a", encoding="utf-8") as f:
    f.write(json.dumps(audit_record) + "\n")

st.success("Deployment audit updated ✅")
