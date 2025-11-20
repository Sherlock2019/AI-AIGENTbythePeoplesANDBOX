# Docker & Kubernetes Deployment

## Docker (local)
1. Build the image using the included Dockerfile:
   ```bash
   docker build -t hugme-sandbox .
   ```
2. Run the container (adjust ports if needed):
   ```bash
   docker run --rm -p 8090:8090 -p 8502:8502 \
     -e OLLAMA_URL=http://host.docker.internal:11434 \
     hugme-sandbox
   ```
   - API: http://localhost:8090/docs
   - UI:  http://localhost:8502

> Use a real hostname/IP for `OLLAMA_URL` if the host differs.

## Kubernetes
1. Ensure your image is published to a registry accessible by the cluster (set `REGISTRY_IMAGE`).
2. Apply the manifest (envsubst handled by `deploy.sh k8s`):
   ```bash
   REGISTRY_IMAGE=<registry>/hugme:tag \
   K8S_NAMESPACE=prod \
   K8S_SERVICE_TYPE=LoadBalancer \
   K8S_OLLAMA_URL=http://ollama.default:11434 \
   ./deploy.sh k8s
   ```
3. The k8s Service exposes ports 8090 (API) and 8502 (UI).

`deploy.sh` also supports `./deploy.sh docker` for a one-command build/run process.

Files packaged:
- Dockerfile
- docker-entrypoint.sh
- deploy.sh
- k8s/deployment.yaml
- this DEPLOYMENT_README.md
