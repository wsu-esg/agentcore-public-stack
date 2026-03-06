#!/bin/bash
set -euo pipefail

# Script: Sync VERSION file into all package manifests
# Usage:
#   bash scripts/common/sync-version.sh          # Write VERSION into manifests
#   bash scripts/common/sync-version.sh --check   # Check for drift (exit non-zero if out of sync)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION_FILE="${REPO_ROOT}/VERSION"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# Validate VERSION file
if [ ! -f "${VERSION_FILE}" ]; then
    echo -e "${RED}[ERROR]${NC} VERSION file not found at ${VERSION_FILE}"
    exit 1
fi

VERSION=$(tr -d '[:space:]' < "${VERSION_FILE}")

if [ -z "${VERSION}" ]; then
    echo -e "${RED}[ERROR]${NC} VERSION file is empty"
    exit 1
fi

if ! [[ "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
    echo -e "${RED}[ERROR]${NC} VERSION '${VERSION}' does not match SemVer format"
    exit 1
fi

# Target manifests
PYPROJECT="${REPO_ROOT}/backend/pyproject.toml"
FE_PKG="${REPO_ROOT}/frontend/ai.client/package.json"
INFRA_PKG="${REPO_ROOT}/infrastructure/package.json"

CHECK_MODE=false
if [ "${1:-}" = "--check" ]; then
    CHECK_MODE=true
fi

errors=0

sync_or_check() {
    local file="$1"
    local current="$2"
    local label="$3"

    if [ "${current}" = "${VERSION}" ]; then
        echo -e "${GREEN}[OK]${NC} ${label}: ${current}"
    elif [ "${CHECK_MODE}" = true ]; then
        echo -e "${RED}[DRIFT]${NC} ${label}: ${current} (expected ${VERSION})"
        errors=$((errors + 1))
    fi
}

# Read current versions
PY_VER=$(grep -oP '^version\s*=\s*"\K[^"]+' "${PYPROJECT}" || echo "")
FE_VER=$(grep -oP '"version"\s*:\s*"\K[^"]+' "${FE_PKG}" | head -1 || echo "")
INFRA_VER=$(grep -oP '"version"\s*:\s*"\K[^"]+' "${INFRA_PKG}" | head -1 || echo "")

if [ "${CHECK_MODE}" = true ]; then
    echo "Checking manifests against VERSION=${VERSION}..."
    sync_or_check "${PYPROJECT}" "${PY_VER}" "backend/pyproject.toml"
    sync_or_check "${FE_PKG}" "${FE_VER}" "frontend/ai.client/package.json"
    sync_or_check "${INFRA_PKG}" "${INFRA_VER}" "infrastructure/package.json"

    if [ ${errors} -gt 0 ]; then
        echo -e "\n${RED}[FAIL]${NC} ${errors} manifest(s) out of sync. Run: bash scripts/common/sync-version.sh"
        exit 1
    else
        echo -e "\n${GREEN}[PASS]${NC} All manifests in sync."
        exit 0
    fi
fi

# Sync mode — update all manifests
echo "Syncing VERSION=${VERSION} into manifests..."

sed -i "s/^version = \".*\"/version = \"${VERSION}\"/" "${PYPROJECT}"
echo -e "${GREEN}[UPDATED]${NC} backend/pyproject.toml"

# Use a temp file approach for JSON to avoid jq dependency issues
sed -i "0,/\"version\": \"[^\"]*\"/s/\"version\": \"[^\"]*\"/\"version\": \"${VERSION}\"/" "${FE_PKG}"
echo -e "${GREEN}[UPDATED]${NC} frontend/ai.client/package.json"

sed -i "0,/\"version\": \"[^\"]*\"/s/\"version\": \"[^\"]*\"/\"version\": \"${VERSION}\"/" "${INFRA_PKG}"
echo -e "${GREEN}[UPDATED]${NC} infrastructure/package.json"

echo -e "\n${GREEN}[DONE]${NC} All manifests updated to ${VERSION}"
