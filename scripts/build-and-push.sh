#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME=$(basename "$0")
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REGION="${AWS_REGION:-us-east-1}"
NO_CACHE=false

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME <agent-directory> <repository-name> [tag] [region] [options]

Build ARM64 Docker image and push to ECR in one command.

Arguments:
  agent-directory   Path to Strands agent project containing Dockerfile
  repository-name   ECR repository name
  tag              Docker image tag (default: latest)
  region           AWS region for ECR (default: \$AWS_REGION or us-east-1)

Options:
  --no-cache       Disable Docker build cache
  -h, --help       Show this help message

Examples:
  $SCRIPT_NAME ./agentcore strands-agents
  $SCRIPT_NAME ./agentcore strands-agents v1.0.0 us-east-1

Exit Codes:
  0    Success - build and push completed
  1-4  Build stage failed (see build-agent.sh exit codes)
  5-6  Push stage failed (see push-to-ecr.sh exit codes)

EOF
  exit 0
}

log_info() {
  echo "[INFO] $*"
}

log_success() {
  echo "[SUCCESS] $*"
}

log_error() {
  echo "[ERROR] $*" >&2
}

log_stage() {
  echo ""
  echo "[INFO] === $* ==="
  echo ""
}

parse_args() {
  if [[ $# -eq 0 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    usage
  fi

  if [[ $# -lt 2 ]]; then
    log_error "Missing required arguments."
    log_error "Usage: $SCRIPT_NAME <agent-directory> <repository-name> [tag] [region] [options]"
    exit 1
  fi

  AGENT_DIR="$1"
  REPO_NAME="$2"
  TAG="${3:-latest}"

  shift 2
  [[ $# -gt 0 ]] && shift

  if [[ $# -gt 0 ]] && [[ ! "$1" =~ ^-- ]]; then
    REGION="$1"
    shift
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-cache)
        NO_CACHE=true
        shift
        ;;
      *)
        log_error "Unknown option: $1"
        exit 1
        ;;
    esac
  done
}

build_stage() {
  log_stage "STAGE 1: BUILD"

  local build_args=("$AGENT_DIR" "$REPO_NAME" "$TAG")
  
  if [[ "$NO_CACHE" == "true" ]]; then
    build_args+=("--no-cache")
  fi

  if ! "$SCRIPT_DIR/build-agent.sh" "${build_args[@]}"; then
    log_error "=== STAGE 1: BUILD FAILED ==="
    log_error "Build failed. Halting before push."
    exit $?
  fi
}

push_stage() {
  log_stage "STAGE 2: PUSH"

  local image_name="${REPO_NAME}:${TAG}"
  local push_args=("$image_name" "$REPO_NAME" "$REGION")

  if ! "$SCRIPT_DIR/push-to-ecr.sh" "${push_args[@]}"; then
    log_error "=== STAGE 2: PUSH FAILED ==="
    log_info "Local image still available: $image_name"
    log_error "Push failed. Image is built but not pushed to ECR."
    exit $?
  fi
}

display_final_summary() {
  local account_id
  account_id=$(aws sts get-caller-identity --query Account --output text --region "$REGION" 2>/dev/null || echo "unknown")
  
  local ecr_uri="${account_id}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${TAG}"

  log_stage "COMPLETE"
  log_success "Build and push workflow finished"
  log_info "Local image: ${REPO_NAME}:${TAG}"
  log_info "ECR URI: $ecr_uri"
  log_info "Region: $REGION"
}

main() {
  parse_args "$@"
  
  build_stage
  push_stage
  display_final_summary
  
  log_success "All stages complete!"
}

main "$@"
