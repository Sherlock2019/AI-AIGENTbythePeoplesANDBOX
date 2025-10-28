from fastapi import FastAPI, Request
import requests, yaml

app = FastAPI(title="AI Agent Hub")

@app.on_event("startup")
def load_registry():
    global registry
    with open("services/registry/agent_registry.yaml") as f:
        registry = yaml.safe_load(f)

@app.get("/health")
def health(): return {"status": "hub ok"}

@app.post("/run/{agent_name}")
async def run_agent(agent_name: str, req: Request):
    payload = await req.json()
    if agent_name not in registry["agents"]:
        return {"error": f"Unknown agent: {agent_name}"}
    url = registry["agents"][agent_name]["url"] + "/run"
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        return {"error": str(e), "agent": agent_name}
