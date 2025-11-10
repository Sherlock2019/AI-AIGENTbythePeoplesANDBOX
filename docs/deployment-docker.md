# Docker Deployment Guide

Build the container directly from repo root:

```bash
docker build -t ai-aigent-ui:latest .
```

Run it locally with persistent model storage:

```bash
docker run -d --name ai-aigent \
  -p 8080:8080 \
  -v $(pwd)/agents:/app/agents \
  -v $(pwd)/exports:/app/exports \
  --env-file .env \
  ai-aigent-ui:latest
```

Using Docker Compose:

```bash
APP_PORT=8080 docker compose up -d
```

Push to your registry before deploying to AWS ECS, OpenStack, or Kubernetes:

```bash
docker tag ai-aigent-ui:latest <registry>/ai-aigent-ui:latest
docker push <registry>/ai-aigent-ui:latest
```

Provision infrastructure (ECS task, OpenStack VM, or k8s deployment) and run the image using the same mounts/env files so training artifacts persist. Use a load balancer or ingress controller to expose `APP_PORT`, and configure health checks against `/_stcore/health`.
