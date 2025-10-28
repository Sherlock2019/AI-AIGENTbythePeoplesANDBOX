# 🧠 AI-AIGENTbythePeoplesANDBOX — Global AI Agent Sandbox

This repository orchestrates multiple AI Agents (each hosted in its own repo) under a unified sandbox environment.

## 🌐 Connected Agents
| Agent | Repo | Port | Description |
|--------|------|------|-------------|
| Credit Appraisal | [credit-appraisal-agent-poc](https://github.com/Sherlock2019/credit-appraisal-agent-poc) | 8091 | Credit scoring & risk evaluation |
| Asset Appraisal | [asset-appraisal-agent-](https://github.com/Sherlock2019/asset-appraisal-agent-) | 8092 | Asset valuation & field verification |

## 🧭 Registry
Defined in `services/registry/agent_registry.yaml`.

## 🚀 Run Locally
```bash
bash scripts/start_all.sh
# or stop
bash scripts/stop_all.sh
