#!/bin/bash
set -euo pipefail

# Script: Sync VERSION file into all package manifests
# Usage:
#   bash scripts/common/sync-version.sh          # Write VERSION into manifests
#   bash scripts/common/sync-version.sh --check   # Check for drift (exit non-zero if out of sync)
#
# Compatible with macOS (BSD grep/sed) and Linux (GNU grep/sed).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION_FILE="${REPO_ROOT}/VERSION"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Portable helpers
# ---------------------------------------------------------------------------

# grep_perl PATTERN FILE — Perl-compatible regex extraction without grep -P.
# Uses perl itself, which is available on both macOS and Linux.
grep_perl() {
    local pattern="$1"
    local file="$2"
    perl -ne "if (/${pattern}/) { print \$1, \"\n\" }" "${file}" 2>/dev/null || true
}

# sed_inplace EXPRESSION FILE — in-place sed compatible with BSD and GNU.
sed_inplace() {
    local expr="$1"
    local file="$2"
    if sed --version 2>/dev/null | grep -q GNU; then
        sed -i "${expr}" "${file}"
    else
        sed -i "" "${expr}" "${file}"
    fi
}

# sed_inplace_first PATTERN REPLACEMENT FILE — replace only first occurrence.
# BSD sed does not support the 0,/pat/s/// address form.
sed_inplace_first() {
    local pattern="$1"
    local replacement="$2"
    local file="$3"
    perl -i -pe "s/${pattern}/${replacement}/ if !(\$done++) " "${file}"
}

# ---------------------------------------------------------------------------
# Validate VERSION file
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Target manifests
# ---------------------------------------------------------------------------
PYPROJECT="${REPO_ROOT}/backend/pyproject.toml"
FE_PKG="${REPO_ROOT}/frontend/ai.client/package.json"
INFRA_PKG="${REPO_ROOT}/infrastructure/package.json"
README="${REPO_ROOT}/README.md"

CHECK_MODE=false
if [ "${1:-}" = "--check" ]; then
    CHECK_MODE=true
fi

errors=0

sync_or_check() {
    local file="$1"
    local current="$2"
    local label="$3"
    local expected="${4:-${VERSION}}"

    if [ "${current}" = "${expected}" ]; then
        echo -e "${GREEN}[OK]${NC} ${label}: ${current}"
    elif [ "${CHECK_MODE}" = true ]; then
        echo -e "${RED}[DRIFT]${NC} ${label}: ${current} (expected ${expected})"
        errors=$((errors + 1))
    fi
}

# ---------------------------------------------------------------------------
# Read current versions (portable — no grep -P)
# ---------------------------------------------------------------------------
PY_VER=$(grep_perl '^version\s*=\s*"([^"]+)"' "${PYPROJECT}" | head -1)
FE_VER=$(grep_perl '"version"\s*:\s*"([^"]+)"' "${FE_PKG}" | head -1)
INFRA_VER=$(grep_perl '"version"\s*:\s*"([^"]+)"' "${INFRA_PKG}" | head -1)
README_BADGE_VER=$(grep_perl 'badge/Release-v([^-?][^?]*)(?=-)' "${README}" | head -1 | sed 's/--/-/g' || true)
README_CURRENT_VER=$(grep_perl '\*\*Current release:\*\* v(.*)' "${README}" | tr -d '[:space:]' | head -1)

# uv.lock uses PEP 440 format (e.g., 1.0.0b16 instead of 1.0.0-beta.16)
UV_LOCK="${REPO_ROOT}/backend/uv.lock"
UV_LOCK_VER=""
if [ -f "${UV_LOCK}" ]; then
    UV_LOCK_VER=$(perl -ne '
        if (/name = "agentcore-stack"/) { $found=1 }
        if ($found && /^version = "([^"]+)"/) { print "$1\n"; exit }
        if ($found && /^\[/) { exit }
    ' "${UV_LOCK}" || true)
fi

# Convert SemVer prerelease to PEP 440 (e.g., 1.0.0-beta.16 → 1.0.0b16)
# Handles compound prereleases like 1.0.0-wsu-beta.25 → 1.0.0wsub25
PEP440_VERSION=$(echo "${VERSION}" | sed -E 's/-alpha\./a/; s/-beta\./b/; s/-rc\./rc/; s/-//g')

# ---------------------------------------------------------------------------
# Check mode
# ---------------------------------------------------------------------------
if [ "${CHECK_MODE}" = true ]; then
    echo "Checking manifests against VERSION=${VERSION}..."
    sync_or_check "${PYPROJECT}" "${PY_VER}" "backend/pyproject.toml"
    sync_or_check "${FE_PKG}" "${FE_VER}" "frontend/ai.client/package.json"
    sync_or_check "${INFRA_PKG}" "${INFRA_VER}" "infrastructure/package.json"
    sync_or_check "${README}" "${README_BADGE_VER}" "README.md (badge)"
    sync_or_check "${README}" "${README_CURRENT_VER}" "README.md (current release)"
    if [ -f "${UV_LOCK}" ]; then
        sync_or_check "${UV_LOCK}" "${UV_LOCK_VER}" "backend/uv.lock" "${PEP440_VERSION}"
    fi

    if [ ${errors} -gt 0 ]; then
        echo -e "\n${RED}[FAIL]${NC} ${errors} manifest(s) out of sync. Run: bash scripts/common/sync-version.sh"
        exit 1
    else
        echo -e "\n${GREEN}[PASS]${NC} All manifests in sync."
        exit 0
    fi
fi

# ---------------------------------------------------------------------------
# Sync mode — update all manifests
# ---------------------------------------------------------------------------
echo "Syncing VERSION=${VERSION} into manifests..."

sed_inplace "s/^version = \".*\"/version = \"${VERSION}\"/" "${PYPROJECT}"
echo -e "${GREEN}[UPDATED]${NC} backend/pyproject.toml"

sed_inplace_first '"version": "[^"]*"' "\"version\": \"${VERSION}\"" "${FE_PKG}"
echo -e "${GREEN}[UPDATED]${NC} frontend/ai.client/package.json"

sed_inplace_first '"version": "[^"]*"' "\"version\": \"${VERSION}\"" "${INFRA_PKG}"
echo -e "${GREEN}[UPDATED]${NC} infrastructure/package.json"

# README.md: version badge and "Current release" text
# shields.io uses -- for literal hyphens in badge text
BADGE_VERSION=$(echo "${VERSION}" | sed 's/-/--/g')
sed_inplace "s|badge/Release-v[^?]*|badge/Release-v${BADGE_VERSION}-6366f1|" "${README}"
sed_inplace "s|\*\*Current release:\*\* v.*|\*\*Current release:\*\* v${VERSION}|" "${README}"
echo -e "${GREEN}[UPDATED]${NC} README.md (badge + current release)"

# ---------------------------------------------------------------------------
# Regenerate lockfiles
# ---------------------------------------------------------------------------
echo -e "\nRegenerating lockfiles..."

if command -v uv &>/dev/null; then
    (cd "${REPO_ROOT}/backend" && uv lock)
    echo -e "${GREEN}[UPDATED]${NC} backend/uv.lock"
else
    echo -e "${RED}[SKIP]${NC} backend/uv.lock (uv not installed — run: curl -LsSf https://astral.sh/uv/install.sh | sh)"
fi

npm install --package-lock-only --prefix "${REPO_ROOT}/frontend/ai.client" 2>/dev/null
echo -e "${GREEN}[UPDATED]${NC} frontend/ai.client/package-lock.json"

npm install --package-lock-only --prefix "${REPO_ROOT}/infrastructure" 2>/dev/null
echo -e "${GREEN}[UPDATED]${NC} infrastructure/package-lock.json"

echo -e "\n${GREEN}[DONE]${NC} All manifests and lockfiles updated to ${VERSION}"
