#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-help}"

IMAGE="${IMAGE:-hugme-sandbox:latest}"
RUN_PORT_API="${RUN_PORT_API:-8090}"
RUN_PORT_UI="${RUN_PORT_UI:-8502}"
RUN_OLLAMA_URL="${RUN_OLLAMA_URL:-http://host.docker.internal:11434}"

usage() {
  cat <<'EOF'
Usage:
  ./deploy.sh docker             # build + run locally with Docker
  IMAGE=myrepo/hugme:prod ./deploy.sh docker

  REGISTRY_IMAGE=myrepo/hugme:prod \
  K8S_NAMESPACE=prod \
  K8S_SERVICE_TYPE=LoadBalancer \
  ./deploy.sh k8s                # render manifest and kubectl apply

Environment knobs:
  IMAGE                 Image tag to build/run locally (default: hugme-sandbox:latest)
  RUN_PORT_API          Host port for FastAPI when running docker (default: 8090)
  RUN_PORT_UI           Host port for Streamlit when running docker (default: 8502)
  RUN_OLLAMA_URL        Ollama endpoint the container should call (default: host.docker.internal)

  REGISTRY_IMAGE        Image reference that the cluster can pull (defaults to IMAGE)
  K8S_NAMESPACE         Namespace for k8s resources (default: default)
  K8S_REPLICAS          Deployment replicas (default: 1)
  K8S_SERVICE_TYPE      ClusterIP | NodePort | LoadBalancer (default: LoadBalancer)
  K8S_OLLAMA_URL        Ollama endpoint reachable from the cluster (default: http://ollama.default:11434)
EOF
}

docker_mode() {
  echo "==> Building Docker image '${IMAGE}'"
  docker build -t "${IMAGE}" "${ROOT}"

  echo "==> Starting container (Ctrl+C to stop)..."
  docker run --rm \
    -p "${RUN_PORT_API}:8090" \
    -p "${RUN_PORT_UI}:8502" \
    -e OLLAMA_URL="${RUN_OLLAMA_URL}" \
    -e API_PORT=8090 \
    -e UI_PORT=8502 \
    "${IMAGE}"
}

k8s_mode() {
  command -v kubectl >/dev/null 2>&1 || { echo "kubectl not found in PATH"; exit 1; }

  REGISTRY_IMAGE="${REGISTRY_IMAGE:-${IMAGE}}"
  export K8S_IMAGE="${REGISTRY_IMAGE}"
  export K8S_NAMESPACE="${K8S_NAMESPACE:-default}"
  export K8S_REPLICAS="${K8S_REPLICAS:-1}"
  export K8S_SERVICE_TYPE="${K8S_SERVICE_TYPE:-LoadBalancer}"
  export K8S_OLLAMA_URL="${K8S_OLLAMA_URL:-http://ollama.default:11434}"

  if [[ -z "${REGISTRY_IMAGE}" ]]; then
    echo "REGISTRY_IMAGE must be set to an image the cluster can pull (e.g., ghcr.io/org/app:tag)"
    exit 1
  fi

  echo "==> Applying Kubernetes manifests to namespace ${K8S_NAMESPACE}"
  envsubst < "${ROOT}/k8s/deployment.yaml" | kubectl apply -f -
}

case "${MODE}" in
  docker) docker_mode ;;
  k8s) k8s_mode ;;
  help|--help|-h) usage ;;
  *) echo "Unknown mode '${MODE}'"; usage; exit 1 ;;
esac
