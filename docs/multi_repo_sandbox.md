# Multi-Repo Sandbox Integration Guide

This guide explains how to transition from a monolithic agent repository to the multi-repo architecture recommended for the AI-AIGENTbythePeoplesANDBOX ecosystem.

## 1. Target Architecture Overview
```
rackspace-aisandbox/
├── ai-agent-hub/             # Orchestrator (FastAPI, registry-aware)
├── agent-credit-appraisal/   # Credit appraisal microservice
├── agent-asset-appraisal/    # Asset appraisal microservice
└── shared-agent-sdk/         # Shared utilities (optional)
```

Each agent repository remains autonomous while the hub coordinates routing through an agent registry.

## 2. Bootstrap a Local Workspace
Use the provided script to create the directory structure, seed FastAPI entrypoints, and optionally wire in shared utilities.

```bash
./scripts/init_multi_repo.sh \
  --workspace "$HOME/rackspace-aisandbox" \
  --credit-agent https://github.com/Sherlock2019/credit-appraisal-agent-poc.git \
  --asset-agent https://github.com/Sherlock2019/asset-appraisal-agent-.git
```

### Script Highlights
- **Configurable workspace**: choose where the scaffold lives.
- **Branch pinning**: `--credit-branch main` (defaults to repo default branch).
- **Shared SDK toggle**: `--with-shared-sdk` seeds a reusable Python package with helpers.
- **Hub seeding skip**: `--skip-hub` allows reusing an existing orchestrator checkout.

Run `./scripts/init_multi_repo.sh --help` for the full set of options.

## 3. Connect Existing Agents
Once the workspace is created:
1. Navigate into each agent repo (e.g., `agent-credit-appraisal/`).
2. Follow its README to install dependencies and start the FastAPI server (common port choices: 8091, 8092).
3. Update the hub registry to point at the running services (see below).

## 4. Maintain the Agent Registry
Copy the example registry into your hub repo and adjust URLs as needed:

```bash
cp infra/agent_registry.example.yaml ai-agent-hub/agent_registry.yaml
```

Edit `ai-agent-hub/agent_registry.yaml`:

```yaml
agents:
  credit_appraisal:
    url: "http://localhost:8091"
    version: "1.2.0"
  asset_appraisal:
    url: "http://localhost:8092"
    version: "1.0.3"
```

The orchestrator reads this file on startup and routes `/run/{agent_name}` requests to the proper service.

## 5. Suggested CI/CD Workflow
1. **Agent Repos**: run unit tests, linting, and model validation per agent.
2. **Hub Repo**: ensure registry changes and hub API tests pass.
3. **Shared SDK**: publish to internal package index; bump version in agents as needed.
4. **Deployment**: redeploy individual agents without affecting others.

## 6. Next Steps
- Containerize each agent with Dockerfiles and a `docker-compose.yml` (future work).
- Add monitoring & logging instrumentation to the hub.
- Expand the registry to include metadata (capabilities, auth requirements, model versions).
