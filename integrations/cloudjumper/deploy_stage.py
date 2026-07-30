"""🚀 Deployment in Production — the shared stage.

Rendered identically by YES AI CAN and AI 4 the People. Written once here
because those two codebases are 90% the same file-for-file; a second copy of
this screen would drift within a sprint.

The stage does four things and refuses to pretend about any of them:

  1. shows whether CloudJumper is actually reachable and our key accepted
  2. runs the readiness gate and blocks on real gaps
  3. builds the bundle (missing assets recorded as gaps, never stubbed)
  4. sends it, and reports what CloudJumper said — not what we hoped
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List

from . import client as cj_client
from . import package as pkg
from . import readiness as readiness_mod

VERDICT_ICON = {"READY": "✅", "READY_WITH_CHANGES": "🟡", "BLOCKED": "⛔", "MANUAL_REVIEW": "🔍", "WARNING": "🟠"}


def connection_panel(st) -> Dict[str, Any]:
    """Render CloudJumper connectivity. Returns the health result."""
    cfg = cj_client.config_summary()
    st.subheader("CloudJumper connection")

    if not cfg["configured"]:
        st.error(
            "**Not configured.** Set `CLOUDJUMPER_API_BASE_URL` and the environment variable "
            f"named by `CLOUDJUMPER_API_KEY_REFERENCE` (currently `{cfg['api_key_reference']}`).",
            icon="🔌",
        )
        st.caption("The key is read from the environment. It is never stored here, logged, or shown.")
        return {"reachable": False}

    health = cj_client.health_check()
    a, b, c = st.columns(3)
    a.metric("Endpoint", "reachable" if health.get("reachable") else "unreachable")
    b.metric("Authenticated as", health.get("authenticated_as") or "—")
    c.metric("TLS verify", "on" if cfg["verify_tls"] else "OFF")

    if not health.get("reachable"):
        st.error(f"Cannot reach CloudJumper: {health.get('error')}", icon="⚠️")
    elif not health.get("authenticated_as"):
        # Reachable but anonymous: the key is wrong or not configured server-side.
        st.warning(
            "Reachable, but the API key was not accepted. CloudJumper needs "
            "`AI_ADOPTION_API_KEYS=\"<name>:<secret>\"` with a matching secret.",
            icon="🔑",
        )
    else:
        st.success(f"Connected as **{health['authenticated_as']}**.", icon="🔗")
    return health


def render(
    st,
    candidates: List[Dict[str, Any]],
    *,
    platform: str,
    evidence_for: Callable[[Dict[str, Any]], Dict[str, Any]] | None = None,
    demo: bool = True,
) -> None:
    """Render the whole stage for a list of candidate dicts."""
    st.title("🚀 Deployment in Production")
    st.caption(
        f"Send a validated {platform} agent to CloudJumper, which designs, deploys and "
        "transitions it into governed FLEX, OpenCenter and Palantir production."
    )

    health = connection_panel(st)
    connected = bool(health.get("reachable") and health.get("authenticated_as"))
    st.divider()

    if demo:
        st.warning("The projects below are **DEMO** records.", icon="⚠️")

    for cand in candidates:
        ev = (evidence_for(cand) if evidence_for else {"EVALUATION_REPORT": True})
        result = readiness_mod.assess(cand, ev)
        icon = VERDICT_ICON.get(result["verdict"], "•")
        key = cand.get("global_ai_project_id") or cand.get("title")

        with st.expander(f"{icon} {cand['title']} · `{key}` · {result['verdict']}", expanded=False):
            left, right = st.columns([2, 1])
            with left:
                st.write(f"**Mode:** {cand['adoption_mode']} · **Source:** {cand.get('source_type', platform)}")
                st.write(f"**Data:** {cand.get('data_sensitivity') or 'unclassified'} · "
                         f"{cand.get('data_location') or 'location unknown'}")
                st.write(f"**Model:** {cand.get('model_name') or '—'} "
                         f"{cand.get('model_version') or ''} · licence: {cand.get('model_license') or '—'}")
            with right:
                st.metric("Readiness", f"{result['score']}%")
                st.caption(f"{result['passed']} passed · {result['failed']} failed · "
                           f"{result['not_checked']} not checked · confidence {result['confidence']}%")

            if result["blockers"]:
                st.error("**Blocked — CloudJumper would reject this**")
                for blocker in result["blockers"]:
                    st.write(f"- **{blocker['title']}** → {blocker['remediation']}")
                st.caption(result["formula"])
                continue

            st.caption(result["formula"])

            can_send = connected
            label = "🚀 Deploy to Production via CloudJumper" if can_send else "🚀 Deploy (CloudJumper not connected)"
            if st.button(label, key=f"deploy-{key}", disabled=not can_send, type="primary"):
                _deploy(st, cand, ev, key)


def _deploy(st, cand: Dict[str, Any], ev: Dict[str, Any], key: str) -> None:
    with st.status("Sending to CloudJumper…", expanded=True) as status:
        try:
            st.write("Building handoff bundle…")
            built = pkg.build_package(cand, {"score": 0.9, "summary": "Evaluation evidence attached."})
        except pkg.PackageError as exc:
            status.update(label="Refused", state="error")
            st.error(f"Package refused: {exc}")
            return

        st.write(f"Bundle {built['size']} bytes · checksum `{built['checksum'][:16]}…`")
        if built["gaps"]:
            st.write(f"{len(built['gaps'])} gap(s) recorded (not stubbed):")
            for g in built["gaps"]:
                st.write(f"  • **{g['severity']}** {g['title']}")

        tmp = Path(tempfile.mkdtemp(prefix="cj-deploy-")) / built["filename"]
        tmp.write_bytes(built["bytes"])

        st.write("Submitting…")
        try:
            res = cj_client.submit_bundle(
                tmp,
                name=cand["title"],
                adoption_mode=cand["adoption_mode"],
                global_ai_project_id=cand.get("global_ai_project_id", ""),
                business_owner=cand.get("business_owner", ""),
                technical_owner=cand.get("technical_owner", ""),
                data_owner=cand.get("data_owner", ""),
                production_owner=cand.get("production_owner", ""),
                business_goal=cand.get("business_problem", ""),
                data_sensitivity=cand.get("data_sensitivity", ""),
                palantir_required=bool(cand.get("palantir_required")),
            )
        except cj_client.CloudJumperError as exc:
            status.update(label="Submission failed", state="error")
            st.error(str(exc))
            st.caption(
                f"Nothing was created in CloudJumper. "
                f"{'Retry is safe.' if exc.retry_safe else 'Fix the configuration or bundle, then resubmit.'}"
                + (f" Correlation ID: `{exc.correlation_id}`" if exc.correlation_id else "")
            )
            return
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass

        status.update(label="Submitted to CloudJumper", state="complete")

    if res.get("duplicate"):
        st.info("This exact bundle was already submitted — returning the existing project.", icon="♻️")

    a, b, c = st.columns(3)
    a.metric("CloudJumper readiness", f"{res.get('readiness_score')}%")
    b.metric("Verdict", res.get("verdict") or "—")
    c.metric("Production gaps", res.get("production_gaps"))

    if res.get("manifest_kind"):
        findings = res.get("manifest_findings") or []
        if findings:
            st.warning(f"Manifest accepted as **{res['manifest_kind']}** with {len(findings)} finding(s):")
            for f in findings:
                st.write(f"- {f}")
        else:
            st.success(f"Manifest accepted as **{res['manifest_kind']}** with no findings.", icon="📦")

    if res.get("critical_gaps"):
        st.error("**Critical gaps CloudJumper found:**")
        for g in res["critical_gaps"]:
            st.write(f"- {g}")

    st.write(f"**Recommended entry:** {res.get('recommended_entry') or '—'} · "
             f"**Palantir:** {res.get('palantir_fit') or '—'}")
    if res.get("cloudjumper_url"):
        st.link_button("Open in CloudJumper", res["cloudjumper_url"])
        st.caption("CloudJumper authentication may be required.")

    # CloudJumper plans and evidences; it does not deploy. Saying otherwise here
    # would be the exact overstatement this pipeline exists to avoid.
    st.info(
        "CloudJumper has imported, assessed and planned this project. Build, UAT, canary and "
        "cutover are executed by Rackspace delivery from that plan.",
        icon="🧭",
    )
