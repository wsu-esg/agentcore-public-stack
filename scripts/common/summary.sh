#!/bin/bash
# Summary generator library for GitHub Actions job summaries
# Provides reusable functions that produce standardized markdown for $GITHUB_STEP_SUMMARY
# Usage: source scripts/common/summary.sh

set -euo pipefail

# Get the repository root directory
SUMMARY_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# ---------------------------------------------------------------------------
# write_header — Compact per-job summary (default for most jobs)
#
# Shows only the job name, status, and stack. Use this for every job except
# the first/main one in a workflow (which should use write_workflow_header).
#
# Params:
#   $1  job_name    Display name of the job (e.g. "App API — Build")
#   $2  status      One of: success, failure, partial
#   $3  stack_name  (optional) CDK stack name (e.g. "AppApiStack")
#
# Appends markdown to $GITHUB_STEP_SUMMARY.
# ---------------------------------------------------------------------------
write_header() {
  local job_name="${1:?write_header: job_name is required}"
  local status="${2:?write_header: status is required}"
  local stack_name="${3:-}"

  local status_emoji
  case "${status}" in
    success) status_emoji="✅" ;;
    failure) status_emoji="❌" ;;
    partial) status_emoji="⚠️" ;;
    *)       status_emoji="❓" ;;
  esac

  {
    echo "## ${status_emoji} ${job_name}"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# write_workflow_header — Full summary header (use ONCE per workflow run)
#
# Shows comprehensive run context: environment, region, project prefix,
# version, commit, branch, trigger, actor, and run link. Call this in the
# first meaningful job of each workflow (e.g. the build or deploy job).
#
# Params:
#   $1  workflow_name   Display name of the workflow (e.g. "App API")
#   $2  status          One of: success, failure, partial
#   $3  stack_name      CDK stack name (e.g. "AppApiStack")
#
# Reads from environment:
#   CDK_PROJECT_PREFIX, CDK_AWS_REGION, GITHUB_SHA, GITHUB_REF_NAME,
#   GITHUB_EVENT_NAME, GITHUB_ACTOR, GITHUB_RUN_ID, GITHUB_EVENT_PATH
#
# Reads VERSION file from repo root and first line of current commit message.
# Appends markdown to $GITHUB_STEP_SUMMARY.
# ---------------------------------------------------------------------------
write_workflow_header() {
  local workflow_name="${1:?write_workflow_header: workflow_name is required}"
  local status="${2:?write_workflow_header: status is required}"
  local stack_name="${3:-}"

  # --- Status emoji ---
  local status_emoji
  case "${status}" in
    success) status_emoji="✅" ;;
    failure) status_emoji="❌" ;;
    partial) status_emoji="⚠️" ;;
    *)       status_emoji="❓" ;;
  esac

  # --- Version from VERSION file ---
  local version="unknown"
  if [ -f "${SUMMARY_REPO_ROOT}/VERSION" ]; then
    version="$(tr -d '[:space:]' < "${SUMMARY_REPO_ROOT}/VERSION")"
  fi

  # --- Git metadata ---
  local short_sha="${GITHUB_SHA:0:7}"
  local branch="${GITHUB_REF_NAME:-unknown}"
  local commit_message
  commit_message="$(git -C "${SUMMARY_REPO_ROOT}" log -1 --pretty=%s 2>/dev/null || echo "N/A")"

  # --- Environment detection ---
  local environment
  if [ "${GITHUB_REF_NAME:-}" = "main" ]; then
    environment="production"
  elif [ "${GITHUB_REF_NAME:-}" = "develop" ]; then
    environment="development"
  else
    environment="${GITHUB_REF_NAME:-unknown}"
  fi

  # --- Trigger type ---
  local trigger="${GITHUB_EVENT_NAME:-unknown}"

  # --- Write header markdown ---
  {
    echo "## ${status_emoji} ${workflow_name}"
    echo ""
    echo "| | |"
    echo "|---|---|"
    echo "| **Status** | ${status_emoji} ${status} |"
    echo "| **Environment** | \`${environment}\` |"
    echo "| **Region** | \`${CDK_AWS_REGION:-N/A}\` |"
    echo "| **Project Prefix** | \`${CDK_PROJECT_PREFIX:-N/A}\` |"
    if [ -n "${stack_name}" ]; then
      echo "| **Stack** | \`${stack_name}\` |"
    fi
    echo "| **Version** | \`${version}\` |"
    echo "| **Commit** | \`${short_sha}\` — ${commit_message} |"
    echo "| **Branch** | \`${branch}\` |"
    echo "| **Trigger** | \`${trigger}\` |"
    echo "| **Actor** | ${GITHUB_ACTOR:-N/A} |"
    echo "| **Run** | [#${GITHUB_RUN_ID:-N/A}](https://github.com/${GITHUB_REPOSITORY:-}/actions/runs/${GITHUB_RUN_ID:-}) |"
    echo ""

    # --- workflow_dispatch inputs ---
    if [ "${GITHUB_EVENT_NAME:-}" = "workflow_dispatch" ] && [ -n "${GITHUB_EVENT_PATH:-}" ] && [ -f "${GITHUB_EVENT_PATH:-}" ]; then
      local inputs
      inputs="$(jq -r '.inputs // empty | to_entries[] | "| \(.key) | `\(.value)` |"' "${GITHUB_EVENT_PATH}" 2>/dev/null || true)"
      if [ -n "${inputs}" ]; then
        echo "### Dispatch Inputs"
        echo ""
        echo "| Parameter | Value |"
        echo "|---|---|"
        echo "${inputs}"
        echo ""
      fi
    fi
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# write_collapsible — Wrap content in a collapsible <details> section
#
# Params:
#   $1  summary_label   Text shown on the collapsed summary line
#   $2  content         Markdown/HTML content inside the collapsible block
#
# Appends to $GITHUB_STEP_SUMMARY.
# ---------------------------------------------------------------------------
write_collapsible() {
  local summary_label="${1:?write_collapsible: summary_label is required}"
  local content="${2:?write_collapsible: content is required}"

  {
    echo "<details>"
    echo "<summary>${summary_label}</summary>"
    echo ""
    echo "${content}"
    echo ""
    echo "</details>"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# write_cdk_outputs_table — Render CDK outputs JSON as a markdown table
#
# Params:
#   $1  outputs_json_file   Path to the CDK outputs JSON file
#
# CDK outputs files have the structure:
#   { "StackName": { "OutputKey1": "value1", "OutputKey2": "value2" } }
#
# Parses the first stack object with jq, renders as a markdown table
# (Output Key | Value), and wraps in a collapsible section.
# Appends to $GITHUB_STEP_SUMMARY.
# ---------------------------------------------------------------------------
write_cdk_outputs_table() {
  local outputs_json_file="${1:?write_cdk_outputs_table: outputs_json_file is required}"

  if [ ! -f "${outputs_json_file}" ]; then
    echo "> ⚠️ CDK outputs file not found: \`${outputs_json_file}\`" >> "${GITHUB_STEP_SUMMARY}"
    return 0
  fi

  local table_rows
  table_rows="$(jq -r '.[] | to_entries[] | "| \(.key) | `\(.value)` |"' "${outputs_json_file}" 2>/dev/null || true)"

  if [ -z "${table_rows}" ]; then
    echo "> ⚠️ No outputs found in \`${outputs_json_file}\`" >> "${GITHUB_STEP_SUMMARY}"
    return 0
  fi

  local table_content
  table_content="| Output Key | Value |
|---|---|
${table_rows}"

  write_collapsible "📋 Stack Outputs" "${table_content}"
}

# ---------------------------------------------------------------------------
# write_timing_footer — Display phase durations and total wall-clock time
#
# Params:
#   $@  key=value pairs for phase timings (e.g., "install=45" "build=120" "deploy=300")
#       Each key is the phase name, each value is the duration in seconds.
#
# Reads from environment:
#   SECONDS — bash built-in tracking elapsed time since shell start
#
# Converts seconds to human-readable format (Xm Ys) and renders a timing
# table with one row per phase plus a total wall-clock row from $SECONDS.
# Appends to $GITHUB_STEP_SUMMARY.
# ---------------------------------------------------------------------------
write_timing_footer() {
  local phase key value minutes seconds

  {
    echo "### ⏱️ Timing"
    echo ""
    echo "| Phase | Duration |"
    echo "|---|---|"

    for phase in "$@"; do
      key="${phase%%=*}"
      value="${phase#*=}"
      minutes=$(( value / 60 ))
      seconds=$(( value % 60 ))
      echo "| ${key} | ${minutes}m ${seconds}s |"
    done

    local total_minutes total_seconds
    total_minutes=$(( SECONDS / 60 ))
    total_seconds=$(( SECONDS % 60 ))
    echo "| **Total wall-clock** | **${total_minutes}m ${total_seconds}s** |"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# write_failure_summary — Render failure diagnostics in a collapsible section
#
# Params:
#   $1  step_name   Name of the step that failed (e.g. "Docker Build")
#   $2  exit_code   Exit code from the failed step
#   $3  log_tail    Last 20 lines of log output from the failed step
#
# Uses write_collapsible to wrap the failure details in a <details> block.
# Appends to $GITHUB_STEP_SUMMARY.
# ---------------------------------------------------------------------------
write_failure_summary() {
  local step_name="${1:?write_failure_summary: step_name is required}"
  local exit_code="${2:?write_failure_summary: exit_code is required}"
  local log_tail="${3:-}"

  local content="**Step:** ${step_name}
**Exit Code:** \`${exit_code}\`

\`\`\`
${log_tail}
\`\`\`"

  write_collapsible "❌ Failure Details — ${step_name}" "${content}"
}

# ---------------------------------------------------------------------------
# write_build_summary — Display Docker build metadata in a summary table
#
# Params:
#   $1  image_tag         Docker image tag (e.g. "abc1234")
#   $2  platform          Target platform (e.g. "linux/arm64")
#   $3  image_size_bytes  Compressed image size in bytes
#   $4  ecr_uri           Full ECR repository URI
#   $5  image_digest      Image digest (SHA256)
#
# Reads from environment (optional):
#   CACHE_HIT_PYTHON — "true" if Python dependency cache was hit
#   CACHE_HIT_NODE   — "true" if Node dependency cache was hit
#
# Converts image_size_bytes to human-readable format and renders a
# "Build Summary" markdown table with all image metadata.
# Appends to $GITHUB_STEP_SUMMARY.
# ---------------------------------------------------------------------------
write_build_summary() {
  local image_tag="${1:?write_build_summary: image_tag is required}"
  local platform="${2:?write_build_summary: platform is required}"
  local image_size_bytes="${3:?write_build_summary: image_size_bytes is required}"
  local ecr_uri="${4:-}"
  local image_digest="${5:-}"

  # --- Convert bytes to human-readable size ---
  local human_size
  if command -v numfmt &>/dev/null; then
    human_size="$(numfmt --to=iec-i --suffix=B "${image_size_bytes}" 2>/dev/null || echo "${image_size_bytes} B")"
  else
    # Arithmetic fallback
    if [ "${image_size_bytes}" -ge 1073741824 ] 2>/dev/null; then
      human_size="$(awk "BEGIN { printf \"%.1f GiB\", ${image_size_bytes} / 1073741824 }")"
    elif [ "${image_size_bytes}" -ge 1048576 ] 2>/dev/null; then
      human_size="$(awk "BEGIN { printf \"%.0f MiB\", ${image_size_bytes} / 1048576 }")"
    elif [ "${image_size_bytes}" -ge 1024 ] 2>/dev/null; then
      human_size="$(awk "BEGIN { printf \"%.0f KiB\", ${image_size_bytes} / 1024 }")"
    else
      human_size="${image_size_bytes} B"
    fi
  fi

  # --- Write build summary markdown ---
  {
    echo "### 🐳 Build Summary"
    echo ""
    echo "| | |"
    echo "|---|---|"
    echo "| **Image Tag** | \`${image_tag}\` |"
    echo "| **Platform** | \`${platform}\` |"
    echo "| **Compressed Size** | ${human_size} |"
    if [ -n "${ecr_uri}" ]; then
      echo "| **ECR URI** | \`${ecr_uri}\` |"
    fi
    if [ -n "${image_digest}" ]; then
      echo "| **Image Digest** | \`${image_digest}\` |"
    fi

    # --- Cache status (optional) ---
    if [ -n "${CACHE_HIT_PYTHON:-}" ] || [ -n "${CACHE_HIT_NODE:-}" ]; then
      echo ""
      echo "#### Cache Status"
      echo ""
      echo "| Dependency | Status |"
      echo "|---|---|"
      if [ -n "${CACHE_HIT_PYTHON:-}" ]; then
        if [ "${CACHE_HIT_PYTHON}" = "true" ]; then
          echo "| Python packages | ✅ Hit |"
        else
          echo "| Python packages | ❌ Miss |"
        fi
      fi
      if [ -n "${CACHE_HIT_NODE:-}" ]; then
        if [ "${CACHE_HIT_NODE}" = "true" ]; then
          echo "| Node modules | ✅ Hit |"
        else
          echo "| Node modules | ❌ Miss |"
        fi
      fi
    fi

    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# write_test_summary_python — Display Python test results in a summary table
#
# Params:
#   $1  total              Total number of tests
#   $2  passed             Number of tests passed
#   $3  failed             Number of tests failed
#   $4  skipped            Number of tests skipped
#   $5  duration_seconds   Test duration in seconds
#   $6  coverage_percent   (optional) Code coverage percentage
#   $7  failing_test_names (optional) Newline-separated list of failing test
#                          names (max 10). If more than 5, wrapped in a
#                          collapsible section.
#
# Appends to $GITHUB_STEP_SUMMARY.
# ---------------------------------------------------------------------------
write_test_summary_python() {
  local total="${1:?write_test_summary_python: total is required}"
  local passed="${2:?write_test_summary_python: passed is required}"
  local failed="${3:?write_test_summary_python: failed is required}"
  local skipped="${4:?write_test_summary_python: skipped is required}"
  local duration_seconds="${5:?write_test_summary_python: duration_seconds is required}"
  local coverage_percent="${6:-}"
  local failing_test_names="${7:-}"

  # --- Status emoji ---
  local status_emoji="✅"
  if [ "${failed}" -gt 0 ] 2>/dev/null; then
    status_emoji="❌"
  fi

  # --- Duration formatting ---
  local minutes seconds
  minutes=$(( duration_seconds / 60 ))
  seconds=$(( duration_seconds % 60 ))

  {
    echo "### 🐍 Python Tests"
    echo ""
    echo "| | |"
    echo "|---|---|"
    echo "| **Result** | ${status_emoji} |"
    echo "| **Total** | ${total} |"
    echo "| **Passed** | ${passed} |"
    echo "| **Failed** | ${failed} |"
    echo "| **Skipped** | ${skipped} |"
    echo "| **Duration** | ${minutes}m ${seconds}s |"
    if [ -n "${coverage_percent}" ]; then
      echo "| **Coverage** | ${coverage_percent}% |"
    fi
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"

  # --- Failing test names ---
  if [ -n "${failing_test_names}" ]; then
    local test_count=0
    local test_list=""
    while IFS= read -r name; do
      [ -z "${name}" ] && continue
      test_count=$(( test_count + 1 ))
      test_list="${test_list}- \`${name}\`
"
    done <<< "${failing_test_names}"

    if [ "${test_count}" -gt 5 ]; then
      write_collapsible "❌ Failing Tests (${test_count})" "${test_list}"
    elif [ "${test_count}" -gt 0 ]; then
      {
        echo "${test_list}"
        echo ""
      } >> "${GITHUB_STEP_SUMMARY}"
    fi
  fi
}

# ---------------------------------------------------------------------------
# write_test_summary_frontend — Display frontend test results in a summary table
#
# Params:
#   $1  total_suites       Total number of test suites
#   $2  total_tests        Total number of individual tests
#   $3  passed             Number of tests passed
#   $4  failed             Number of tests failed
#   $5  duration_seconds   Test duration in seconds
#   $6  coverage_percent   (optional) Code coverage percentage
#
# Appends to $GITHUB_STEP_SUMMARY.
# ---------------------------------------------------------------------------
write_test_summary_frontend() {
  local total_suites="${1:?write_test_summary_frontend: total_suites is required}"
  local total_tests="${2:?write_test_summary_frontend: total_tests is required}"
  local passed="${3:?write_test_summary_frontend: passed is required}"
  local failed="${4:?write_test_summary_frontend: failed is required}"
  local duration_seconds="${5:?write_test_summary_frontend: duration_seconds is required}"
  local coverage_percent="${6:-}"

  # --- Status emoji ---
  local status_emoji="✅"
  if [ "${failed}" -gt 0 ] 2>/dev/null; then
    status_emoji="❌"
  fi

  # --- Duration formatting ---
  local minutes seconds
  minutes=$(( duration_seconds / 60 ))
  seconds=$(( duration_seconds % 60 ))

  {
    echo "### 🌐 Frontend Tests"
    echo ""
    echo "| | |"
    echo "|---|---|"
    echo "| **Result** | ${status_emoji} |"
    echo "| **Test Suites** | ${total_suites} |"
    echo "| **Total Tests** | ${total_tests} |"
    echo "| **Passed** | ${passed} |"
    echo "| **Failed** | ${failed} |"
    echo "| **Duration** | ${minutes}m ${seconds}s |"
    if [ -n "${coverage_percent}" ]; then
      echo "| **Coverage** | ${coverage_percent}% |"
    fi
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# write_test_summary_cdk — Display CDK validation results
#
# Params:
#   $1  result          Validation result: "pass" or "fail"
#   $2  resource_count  Number of CloudFormation resources in the template
#
# Appends to $GITHUB_STEP_SUMMARY.
# ---------------------------------------------------------------------------
write_test_summary_cdk() {
  local result="${1:?write_test_summary_cdk: result is required}"
  local resource_count="${2:?write_test_summary_cdk: resource_count is required}"

  # --- Status emoji ---
  local status_emoji
  case "${result}" in
    pass) status_emoji="✅" ;;
    fail) status_emoji="❌" ;;
    *)    status_emoji="❓" ;;
  esac

  {
    echo "### 🏗️ CDK Validation"
    echo ""
    echo "| | |"
    echo "|---|---|"
    echo "| **Result** | ${status_emoji} ${result} |"
    echo "| **Resources** | ${resource_count} |"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# write_test_summary_docker — Display Docker image test results
#
# Params:
#   $1  health_check_result   Health check result: "pass" or "fail"
#   $2  startup_time_seconds  Container startup time in seconds
#
# Appends to $GITHUB_STEP_SUMMARY.
# ---------------------------------------------------------------------------
write_test_summary_docker() {
  local health_check_result="${1:?write_test_summary_docker: health_check_result is required}"
  local startup_time_seconds="${2:?write_test_summary_docker: startup_time_seconds is required}"

  # --- Status emoji ---
  local status_emoji
  case "${health_check_result}" in
    pass) status_emoji="✅" ;;
    fail) status_emoji="❌" ;;
    *)    status_emoji="❓" ;;
  esac

  {
    echo "### 🐳 Docker Tests"
    echo ""
    echo "| | |"
    echo "|---|---|"
    echo "| **Health Check** | ${status_emoji} ${health_check_result} |"
    echo "| **Startup Time** | ${startup_time_seconds}s |"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# write_deploy_summary — Render stack-specific deployment details
#
# Params:
#   $1  stack_type   One of: infrastructure, app-api, inference-api, frontend,
#                    gateway, rag-ingestion, sagemaker, bootstrap
#
# Dispatches to an internal helper that extracts relevant fields from CDK
# outputs JSON files and/or environment variables, then renders a markdown
# table appended to $GITHUB_STEP_SUMMARY.
#
# CDK outputs files (written by each stack's deploy script):
#   infrastructure  → infrastructure/infrastructure-outputs.json
#   app-api         → cdk-outputs-app-api.json
#   inference-api   → cdk-outputs-inference-api.json
#   frontend        → (CloudFormation describe-stacks; no --outputs-file)
#   gateway         → (no --outputs-file in current deploy script)
#   rag-ingestion   → cdk-outputs-rag-ingestion.json
#   sagemaker       → cdk-outputs-sagemaker-fine-tuning.json
#   bootstrap       → (no CDK outputs; reads env vars)
#
# Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9
# ---------------------------------------------------------------------------
write_deploy_summary() {
  local stack_type="${1:?write_deploy_summary: stack_type is required}"

  case "${stack_type}" in
    infrastructure)  _deploy_infrastructure ;;
    app-api)         _deploy_app_api ;;
    inference-api)   _deploy_inference_api ;;
    frontend)        _deploy_frontend ;;
    gateway)         _deploy_gateway ;;
    rag-ingestion)   _deploy_rag_ingestion ;;
    sagemaker)       _deploy_sagemaker ;;
    bootstrap)       _deploy_bootstrap ;;
    *)
      echo "> ⚠️ Unknown stack type: \`${stack_type}\`" >> "${GITHUB_STEP_SUMMARY}"
      return 0
      ;;
  esac
}

# ---------------------------------------------------------------------------
# _safe_jq — Extract a value from a CDK outputs JSON file safely
#
# Params:
#   $1  file    Path to the CDK outputs JSON file
#   $2  key     The output key to extract (e.g. "VpcId")
#
# CDK outputs use the full prefixed stack name as the top-level key
# (e.g. "dev-project-InfrastructureStack"), so we use .[] to skip it.
# Returns the value or "N/A" if the file is missing or the key is absent.
# ---------------------------------------------------------------------------
_safe_jq() {
  local file="${1}"
  local key="${2}"
  if [ -f "${file}" ]; then
    local val
    val="$(jq -r ".[] | .${key} // empty" "${file}" 2>/dev/null || true)"
    echo "${val:-N/A}"
  else
    echo "N/A"
  fi
}

# ---------------------------------------------------------------------------
# _deploy_infrastructure — Infrastructure stack deploy summary
#
# Reads: infrastructure/infrastructure-outputs.json
# Shows: VPC ID, ALB ARN, ECS Cluster name, DynamoDB table count, S3 bucket count
# Requirement: 4.1
# ---------------------------------------------------------------------------
_deploy_infrastructure() {
  local outputs_file="${SUMMARY_REPO_ROOT}/infrastructure/infrastructure-outputs.json"

  if [ ! -f "${outputs_file}" ]; then
    echo "> ⚠️ Infrastructure outputs file not found: \`infrastructure/infrastructure-outputs.json\`" >> "${GITHUB_STEP_SUMMARY}"
    return 0
  fi

  local vpc_id alb_dns alb_url ecs_cluster
  vpc_id="$(_safe_jq "${outputs_file}" "VpcId")"
  alb_dns="$(_safe_jq "${outputs_file}" "AlbDnsName")"
  alb_url="$(_safe_jq "${outputs_file}" "AlbUrl")"
  ecs_cluster="$(_safe_jq "${outputs_file}" "EcsClusterName")"

  {
    echo "### 🏗️ Infrastructure Resources"
    echo ""
    echo "| Resource | Value |"
    echo "|---|---|"
    echo "| **VPC ID** | \`${vpc_id}\` |"
    echo "| **ALB DNS** | \`${alb_dns}\` |"
    if [ "${alb_url}" != "N/A" ]; then
      echo "| **ALB URL** | \`${alb_url}\` |"
    fi
    echo "| **ECS Cluster** | \`${ecs_cluster}\` |"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# _deploy_app_api — App API stack deploy summary
#
# Reads: cdk-outputs-app-api.json, IMAGE_TAG env var
# Shows: ECS service/cluster, task definition revision, image tag,
#        force-new-deployment confirmation
# Requirement: 4.2
# ---------------------------------------------------------------------------
_deploy_app_api() {
  local outputs_file="${SUMMARY_REPO_ROOT}/cdk-outputs-app-api.json"

  if [ ! -f "${outputs_file}" ]; then
    echo "> ⚠️ App API outputs file not found: \`cdk-outputs-app-api.json\`" >> "${GITHUB_STEP_SUMMARY}"
    return 0
  fi

  local cluster_name service_name task_def_arn
  cluster_name="$(_safe_jq "${outputs_file}" "EcsClusterName")"
  service_name="$(_safe_jq "${outputs_file}" "EcsServiceName")"
  task_def_arn="$(_safe_jq "${outputs_file}" "TaskDefinitionArn")"

  # Extract revision number from task definition ARN (last segment after ":")
  local task_revision="N/A"
  if [ "${task_def_arn}" != "N/A" ]; then
    task_revision="${task_def_arn##*:}"
  fi

  {
    echo "### 🚀 App API Deployment"
    echo ""
    echo "| Detail | Value |"
    echo "|---|---|"
    echo "| **ECS Cluster** | \`${cluster_name}\` |"
    echo "| **ECS Service** | \`${service_name}\` |"
    echo "| **Task Definition Revision** | \`${task_revision}\` |"
    echo "| **Image Tag** | \`${IMAGE_TAG:-N/A}\` |"
    echo "| **Force New Deployment** | ✅ Triggered |"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# _deploy_inference_api — Inference API stack deploy summary
#
# Reads: cdk-outputs-inference-api.json, IMAGE_TAG env var,
#        CDK_PROJECT_PREFIX env var
# Shows: image tag, SSM parameter path, target platform,
#        AgentCore Runtime update description
# Requirement: 4.3
# ---------------------------------------------------------------------------
_deploy_inference_api() {
  local outputs_file="${SUMMARY_REPO_ROOT}/cdk-outputs-inference-api.json"
  local ssm_path="/${CDK_PROJECT_PREFIX:-N/A}/inference-api/image-tag"

  {
    echo "### 🤖 Inference API Deployment"
    echo ""
    echo "| Detail | Value |"
    echo "|---|---|"
    echo "| **Image Tag** | \`${IMAGE_TAG:-N/A}\` |"
    echo "| **SSM Parameter** | \`${ssm_path}\` |"
    echo "| **Target Platform** | \`linux/arm64\` |"
    echo "| **Runtime Update** | SSM parameter change → EventBridge → runtime-updater Lambda → parallel runtime updates |"
  } >> "${GITHUB_STEP_SUMMARY}"

  if [ -f "${outputs_file}" ]; then
    local ecr_uri memory_id
    ecr_uri="$(_safe_jq "${outputs_file}" "EcrRepositoryUri")"
    memory_id="$(_safe_jq "${outputs_file}" "InferenceApiMemoryId")"

    {
      if [ "${ecr_uri}" != "N/A" ]; then
        echo "| **ECR Repository** | \`${ecr_uri}\` |"
      fi
      if [ "${memory_id}" != "N/A" ]; then
        echo "| **Memory ID** | \`${memory_id}\` |"
      fi
    } >> "${GITHUB_STEP_SUMMARY}"
  fi

  echo "" >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# _deploy_frontend — Frontend stack deploy summary
#
# Reads: infrastructure/frontend-outputs.json (if present) or env vars
# Shows: S3 bucket name, CloudFront distribution ID, cache invalidation
#        status, propagation time
# Requirement: 4.4
# ---------------------------------------------------------------------------
_deploy_frontend() {
  local outputs_file="${SUMMARY_REPO_ROOT}/infrastructure/frontend-outputs.json"

  local bucket_name distribution_id
  bucket_name="N/A"
  distribution_id="N/A"

  # Try CDK outputs file first
  if [ -f "${outputs_file}" ]; then
    bucket_name="$(_safe_jq "${outputs_file}" "FrontendBucketName")"
    distribution_id="$(_safe_jq "${outputs_file}" "DistributionId")"
  fi

  # Fall back to environment variables if outputs file not available
  if [ "${bucket_name}" = "N/A" ] && [ -n "${CDK_FRONTEND_BUCKET_NAME:-}" ]; then
    bucket_name="${CDK_FRONTEND_BUCKET_NAME}"
  fi
  if [ "${distribution_id}" = "N/A" ] && [ -n "${CLOUDFRONT_DISTRIBUTION_ID:-}" ]; then
    distribution_id="${CLOUDFRONT_DISTRIBUTION_ID}"
  fi

  {
    echo "### 🌐 Frontend Deployment"
    echo ""
    echo "| Detail | Value |"
    echo "|---|---|"
    echo "| **S3 Bucket** | \`${bucket_name}\` |"
    echo "| **CloudFront Distribution** | \`${distribution_id}\` |"
    echo "| **Cache Invalidation** | ✅ Triggered |"
    echo "| **Propagation Time** | 5–15 minutes |"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# _deploy_gateway — Gateway stack deploy summary
#
# Reads: cdk-outputs-gateway.json (if present) or env vars
# Shows: Lambda function count, MCP tool names, API Gateway endpoint URL
# Requirement: 4.5
# ---------------------------------------------------------------------------
_deploy_gateway() {
  local outputs_file="${SUMMARY_REPO_ROOT}/cdk-outputs-gateway.json"

  local gateway_url gateway_id gateway_status
  gateway_url="N/A"
  gateway_id="N/A"
  gateway_status="N/A"

  if [ -f "${outputs_file}" ]; then
    gateway_url="$(_safe_jq "${outputs_file}" "GatewayUrl")"
    gateway_id="$(_safe_jq "${outputs_file}" "GatewayId")"
    gateway_status="$(_safe_jq "${outputs_file}" "GatewayStatus")"
  fi

  {
    echo "### 🔌 Gateway Deployment"
    echo ""
    echo "| Detail | Value |"
    echo "|---|---|"
    echo "| **Lambda Functions** | 5 |"
    echo "| **MCP Tools** | Wikipedia, ArXiv, Google, Tavily, Finance |"
    echo "| **Gateway ID** | \`${gateway_id}\` |"
    echo "| **Gateway Status** | \`${gateway_status}\` |"
    if [ "${gateway_url}" != "N/A" ]; then
      echo "| **Gateway URL** | \`${gateway_url}\` |"
    fi
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# _deploy_rag_ingestion — RAG Ingestion stack deploy summary
#
# Reads: cdk-outputs-rag-ingestion.json, IMAGE_TAG env var
# Shows: image tag, target platform, ECS task definition details
# Requirement: 4.6
# ---------------------------------------------------------------------------
_deploy_rag_ingestion() {
  local outputs_file="${SUMMARY_REPO_ROOT}/cdk-outputs-rag-ingestion.json"

  {
    echo "### 📄 RAG Ingestion Deployment"
    echo ""
    echo "| Detail | Value |"
    echo "|---|---|"
    echo "| **Image Tag** | \`${IMAGE_TAG:-N/A}\` |"
    echo "| **Target Platform** | \`linux/arm64\` |"
  } >> "${GITHUB_STEP_SUMMARY}"

  if [ -f "${outputs_file}" ]; then
    local docs_bucket vector_bucket ingestion_lambda
    docs_bucket="$(_safe_jq "${outputs_file}" "DocumentsBucketName")"
    vector_bucket="$(_safe_jq "${outputs_file}" "VectorBucketName")"
    ingestion_lambda="$(_safe_jq "${outputs_file}" "IngestionLambdaArn")"

    {
      if [ "${docs_bucket}" != "N/A" ]; then
        echo "| **Documents Bucket** | \`${docs_bucket}\` |"
      fi
      if [ "${vector_bucket}" != "N/A" ]; then
        echo "| **Vector Bucket** | \`${vector_bucket}\` |"
      fi
      if [ "${ingestion_lambda}" != "N/A" ]; then
        echo "| **Ingestion Lambda** | \`${ingestion_lambda}\` |"
      fi
    } >> "${GITHUB_STEP_SUMMARY}"
  else
    echo "> ⚠️ RAG Ingestion outputs file not found: \`cdk-outputs-rag-ingestion.json\`" >> "${GITHUB_STEP_SUMMARY}"
  fi

  echo "" >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# _deploy_sagemaker — SageMaker Fine-Tuning stack deploy summary
#
# Reads: cdk-outputs-sagemaker-fine-tuning.json
# Shows: DynamoDB tables, S3 bucket name, SageMaker execution role ARN
# Requirement: 4.7
# ---------------------------------------------------------------------------
_deploy_sagemaker() {
  local outputs_file="${SUMMARY_REPO_ROOT}/cdk-outputs-sagemaker-fine-tuning.json"

  if [ ! -f "${outputs_file}" ]; then
    echo "> ⚠️ SageMaker outputs file not found: \`cdk-outputs-sagemaker-fine-tuning.json\`" >> "${GITHUB_STEP_SUMMARY}"
    return 0
  fi

  local jobs_table access_table data_bucket execution_role
  jobs_table="$(_safe_jq "${outputs_file}" "FineTuningJobsTableName")"
  access_table="$(_safe_jq "${outputs_file}" "FineTuningAccessTableName")"
  data_bucket="$(_safe_jq "${outputs_file}" "FineTuningDataBucketName")"
  execution_role="$(_safe_jq "${outputs_file}" "SageMakerExecutionRoleArn")"

  {
    echo "### 🧠 SageMaker Fine-Tuning Deployment"
    echo ""
    echo "| Resource | Value |"
    echo "|---|---|"
    echo "| **Jobs Table** | \`${jobs_table}\` |"
    echo "| **Access Table** | \`${access_table}\` |"
    echo "| **Data Bucket** | \`${data_bucket}\` |"
    echo "| **Execution Role** | \`${execution_role}\` |"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# _deploy_bootstrap — Bootstrap Data Seeding deploy summary
#
# Reads from environment: SEED_AUTH_PROVIDER_ID, TABLES_SEEDED, ITEMS_WRITTEN
# Shows: auth provider ID, DynamoDB items written, tables seeded
# Requirement: 4.8
# ---------------------------------------------------------------------------
_deploy_bootstrap() {
  local provider_id="${SEED_AUTH_PROVIDER_ID:-N/A}"
  local items_written="${ITEMS_WRITTEN:-N/A}"

  # Default tables seeded by the bootstrap script
  local tables_seeded="${TABLES_SEEDED:-auth-providers, user-quotas, managed-models, app-roles}"

  {
    echo "### 🌱 Bootstrap Data Seeding"
    echo ""
    echo "| Detail | Value |"
    echo "|---|---|"
    echo "| **Auth Provider ID** | \`${provider_id}\` |"
    echo "| **Items Written** | ${items_written} |"
    echo "| **Tables Seeded** | ${tables_seeded} |"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"
}

# ---------------------------------------------------------------------------
# write_version_check_summary — Display version check results with remediation
#
# Params:
#   $1  version_bumped    "pass" or "fail" — whether VERSION file was bumped
#   $2  manifests_synced  "pass" or "fail" — whether package manifests match VERSION
#   $3  lockfiles_synced  "pass" or "fail" — whether lockfiles are up to date
#   $4  old_version       (optional) Previous version from main branch
#   $5  new_version       (optional) New version from the PR branch
#
# Renders a checklist table with pass/fail status per check.
# When any check fails, appends remediation instructions with exact commands.
# Appends to $GITHUB_STEP_SUMMARY.
#
# Requirements: 6.1, 6.2, 6.3
# ---------------------------------------------------------------------------
write_version_check_summary() {
  local version_bumped="${1:?write_version_check_summary: version_bumped is required}"
  local manifests_synced="${2:?write_version_check_summary: manifests_synced is required}"
  local lockfiles_synced="${3:?write_version_check_summary: lockfiles_synced is required}"
  local old_version="${4:-}"
  local new_version="${5:-}"

  # --- Status emojis ---
  local version_emoji manifests_emoji lockfiles_emoji
  if [ "${version_bumped}" = "pass" ]; then version_emoji="✅"; else version_emoji="❌"; fi
  if [ "${manifests_synced}" = "pass" ]; then manifests_emoji="✅"; else manifests_emoji="❌"; fi
  if [ "${lockfiles_synced}" = "pass" ]; then lockfiles_emoji="✅"; else lockfiles_emoji="❌"; fi

  # --- Version details ---
  local version_details=""
  if [ -n "${old_version}" ] && [ -n "${new_version}" ]; then
    version_details="\`${old_version}\` → \`${new_version}\`"
  elif [ "${version_bumped}" = "pass" ]; then
    version_details="Bumped"
  else
    version_details="Not bumped"
  fi

  # --- Manifests details ---
  local manifests_details
  if [ "${manifests_synced}" = "pass" ]; then
    manifests_details="All manifests match"
  else
    manifests_details="Out of sync"
  fi

  # --- Lockfiles details ---
  local lockfiles_details
  if [ "${lockfiles_synced}" = "pass" ]; then
    lockfiles_details="All lockfiles match"
  else
    lockfiles_details="Out of sync"
  fi

  {
    echo "### 🔢 Version Check Results"
    echo ""
    echo "| Check | Status | Details |"
    echo "|---|---|---|"
    echo "| VERSION bumped | ${version_emoji} | ${version_details} |"
    echo "| Manifests in sync | ${manifests_emoji} | ${manifests_details} |"
    echo "| Lockfiles in sync | ${lockfiles_emoji} | ${lockfiles_details} |"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"

  # --- Remediation instructions (only when at least one check fails) ---
  if [ "${version_bumped}" = "fail" ] || [ "${manifests_synced}" = "fail" ] || [ "${lockfiles_synced}" = "fail" ]; then
    {
      echo "### 🛠️ Remediation"
      echo ""
      if [ "${version_bumped}" = "fail" ]; then
        echo "**VERSION not bumped** — Edit the \`VERSION\` file with the new version:"
        echo ""
        echo "\`\`\`bash"
        echo "# Edit the VERSION file with the new version"
        echo "echo \"X.Y.Z\" > VERSION"
        echo "bash scripts/common/sync-version.sh"
        echo "git add -A && git commit -m \"Bump version to X.Y.Z\""
        echo "\`\`\`"
        echo ""
      fi
      if [ "${manifests_synced}" = "fail" ] || [ "${lockfiles_synced}" = "fail" ]; then
        echo "**Manifests or lockfiles out of sync** — Run the sync script and commit:"
        echo ""
        echo "\`\`\`bash"
        echo "bash scripts/common/sync-version.sh"
        echo "git add -A && git commit -m \"Sync version manifests and lockfiles\""
        echo "\`\`\`"
        echo ""
      fi
    } >> "${GITHUB_STEP_SUMMARY}"
  fi
}

# ---------------------------------------------------------------------------
# write_nightly_summary — Render comprehensive nightly build status table
#
# Params:
#   $@  Job results as positional arguments, each in "name|status|duration"
#       format where:
#         name     = display name of the job
#         status   = success, failure, or skipped
#         duration = duration in seconds
#
# Reads from environment (all optional):
#   NIGHTLY_BACKEND_COVERAGE   — backend test coverage percentage
#   NIGHTLY_FRONTEND_COVERAGE  — frontend test coverage percentage
#   NIGHTLY_SMOKE_ENDPOINTS    — number of endpoints tested in smoke test
#   NIGHTLY_SMOKE_RESULTS      — smoke test results summary
#   NIGHTLY_TEARDOWN_STACKS    — stacks destroyed during teardown
#   NIGHTLY_AI_COVERAGE        — AI coverage analysis summary
#
# Example usage:
#   write_nightly_summary \
#     "Install Backend|success|83" \
#     "Test Backend|success|225" \
#     "Deploy Infrastructure|success|312" \
#     "Smoke Test|failure|45" \
#     "Teardown|skipped|0"
#
# Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
# ---------------------------------------------------------------------------
write_nightly_summary() {
  local total_duration=0
  local has_failure=false
  local has_skipped=false
  local all_success=true

  # --- First pass: compute aggregates ---
  local arg name status duration
  for arg in "$@"; do
    IFS='|' read -r name status duration <<< "${arg}"
    total_duration=$(( total_duration + duration ))
    case "${status}" in
      success) ;;
      failure) has_failure=true; all_success=false ;;
      skipped) has_skipped=true; all_success=false ;;
      *)       all_success=false ;;
    esac
  done

  # --- Aggregate status ---
  local aggregate_status
  if [ "${all_success}" = true ]; then
    aggregate_status="✅ All Passed"
  elif [ "${has_failure}" = true ]; then
    aggregate_status="❌ Failed"
  else
    aggregate_status="⚠️ Partial"
  fi

  # --- Total duration formatting ---
  local total_minutes total_seconds
  total_minutes=$(( total_duration / 60 ))
  total_seconds=$(( total_duration % 60 ))

  {
    echo "## 📊 Nightly Build Results"
    echo ""
    echo "| Job | Status | Duration |"
    echo "|---|---|---|"

    # --- Second pass: render rows ---
    for arg in "$@"; do
      IFS='|' read -r name status duration <<< "${arg}"

      local status_label
      case "${status}" in
        success) status_label="✅ Pass" ;;
        failure) status_label="❌ Fail" ;;
        skipped) status_label="⏭️ Skipped" ;;
        *)       status_label="❓ Unknown" ;;
      esac

      local minutes seconds
      minutes=$(( duration / 60 ))
      seconds=$(( duration % 60 ))

      echo "| ${name} | ${status_label} | ${minutes}m ${seconds}s |"
    done

    echo "| **Total** | **${aggregate_status}** | **${total_minutes}m ${total_seconds}s** |"
    echo ""
  } >> "${GITHUB_STEP_SUMMARY}"

  # --- Test Coverage section ---
  if [ -n "${NIGHTLY_BACKEND_COVERAGE:-}" ] || [ -n "${NIGHTLY_FRONTEND_COVERAGE:-}" ]; then
    {
      echo "### 📈 Test Coverage"
      echo ""
      echo "| Suite | Coverage |"
      echo "|---|---|"
      if [ -n "${NIGHTLY_BACKEND_COVERAGE:-}" ]; then
        echo "| Backend | ${NIGHTLY_BACKEND_COVERAGE}% |"
      fi
      if [ -n "${NIGHTLY_FRONTEND_COVERAGE:-}" ]; then
        echo "| Frontend | ${NIGHTLY_FRONTEND_COVERAGE}% |"
      fi
      echo ""
    } >> "${GITHUB_STEP_SUMMARY}"
  fi

  # --- Smoke Test Results section ---
  if [ -n "${NIGHTLY_SMOKE_ENDPOINTS:-}" ] || [ -n "${NIGHTLY_SMOKE_RESULTS:-}" ]; then
    {
      echo "### 🔥 Smoke Test Results"
      echo ""
      if [ -n "${NIGHTLY_SMOKE_ENDPOINTS:-}" ]; then
        echo "**Endpoints Tested:** ${NIGHTLY_SMOKE_ENDPOINTS}"
        echo ""
      fi
      if [ -n "${NIGHTLY_SMOKE_RESULTS:-}" ]; then
        echo "${NIGHTLY_SMOKE_RESULTS}"
        echo ""
      fi
    } >> "${GITHUB_STEP_SUMMARY}"
  fi

  # --- Teardown section ---
  if [ -n "${NIGHTLY_TEARDOWN_STACKS:-}" ]; then
    {
      echo "### 🧹 Teardown"
      echo ""
      echo "**Stacks Destroyed:** ${NIGHTLY_TEARDOWN_STACKS}"
      echo ""
    } >> "${GITHUB_STEP_SUMMARY}"
  fi

  # --- AI Coverage Analysis section (collapsible) ---
  if [ -n "${NIGHTLY_AI_COVERAGE:-}" ]; then
    write_collapsible "🤖 AI Coverage Analysis" "${NIGHTLY_AI_COVERAGE}"
  fi
}
