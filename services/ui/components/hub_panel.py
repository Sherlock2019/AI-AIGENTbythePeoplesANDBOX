import streamlit as st, requests

def show_hub_panel(api_url: str, expanded: bool=False, key_prefix: str="hub"):
    with st.expander("📦 Models & Datasets Hub", expanded=expanded):
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**Hugging Face Models**")
            try:
                r = requests.get(f"{api_url}/v1/hub/models/list", timeout=10)
                models = r.json()
                model_ids = [m["id"] for m in models]
                mdl = st.selectbox("Select model", model_ids, key=f"{key_prefix}_model_sel")
                if st.button("Ensure model locally", key=f"{key_prefix}_ensure_model"):
                    r2 = requests.post(f"{api_url}/v1/hub/models/ensure", json={"model_id": mdl}, timeout=300)
                    st.success("Model ready")
                    st.json(r2.json())
            except Exception as e:
                st.error(f"Hub models error: {e}")

        with c2:
            st.markdown("**Datasets (HF & Kaggle)**")
            try:
                r = requests.get(f"{api_url}/v1/hub/datasets/list", timeout=10)
                dsets = r.json()
                ds_ids = [d["id"] for d in dsets]
                dsid = st.selectbox("Select dataset", ds_ids, key=f"{key_prefix}_dataset_sel")
                if st.button("Ensure dataset locally", key=f"{key_prefix}_ensure_dataset"):
                    r2 = requests.post(f"{api_url}/v1/hub/datasets/ensure", json={"dataset_id": dsid}, timeout=600)
                    st.success("Dataset ready")
                    st.json(r2.json())
            except Exception as e:
                st.error(f"Hub datasets error: {e}")
