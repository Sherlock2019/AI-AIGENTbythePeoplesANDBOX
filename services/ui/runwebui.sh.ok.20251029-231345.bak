# ensure deps are in your existing venv
cd ~/credit-appraisal-agent-poc/services/api
source .venv/bin/activate
pip install streamlit requests pandas -q

# start UI on an open port (8502 if 8501 is used by Docker)
cd ~/credit-appraisal-agent-poc/services/ui
streamlit run app.py --server.port 8502

