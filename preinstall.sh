#!/usr/bin/env bash
set -euo pipefail

# Preinstall script - Install all requirements once to speed up newstart.sh
# Run this once: ./preinstall.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"

echo "🔧 Preinstalling requirements for faster startup..."

# Create venv if needed
if [[ ! -d "${VENV}" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "${VENV}"
fi

# Activate venv
source "${VENV}/bin/activate"

echo "Upgrading pip and wheel..."
python -m pip install -U pip wheel setuptools --root-user-action=ignore

echo "Installing API requirements..."
if [[ -f "${ROOT}/services/api/requirements.txt" ]]; then
  pip install -r "${ROOT}/services/api/requirements.txt" --root-user-action=ignore
  echo "✅ API requirements installed"
else
  echo "⚠️  API requirements.txt not found"
fi

echo "Installing UI requirements..."
if [[ -f "${ROOT}/services/ui/requirements.txt" ]]; then
  pip install -r "${ROOT}/services/ui/requirements.txt" --root-user-action=ignore --ignore-installed blinker
  echo "✅ UI requirements installed"
else
  echo "⚠️  UI requirements.txt not found"
fi

# Fix urllib3 conflict if kubernetes is installed
if python -c "import kubernetes" 2>/dev/null; then
  echo "Fixing urllib3 version conflict..."
  pip install "urllib3<2.4.0,>=1.24.2" --root-user-action=ignore 2>/dev/null || true
fi

echo ""
echo "✅ Preinstallation complete! newstart.sh will now skip installation steps."
