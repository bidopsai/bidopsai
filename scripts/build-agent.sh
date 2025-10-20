#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME=$(basename "$0")
BUILDER_NAME="arm64-builder"
NO_CACHE=false
CUSTOM_BUILDER=""

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME <agent-directory> <repository-name> [tag] [options]

Build ARM64-compatible Docker image for Strands agent using Docker Buildx.

Arguments:
  agent-directory   Path to Strands agent project containing Dockerfile
  repository-name   ECR repository name (without registry URI)
  tag              Docker image tag (default: latest)

Options:
  --no-cache       Disable Docker build cache
  --builder NAME   Custom buildx builder name (default: $BUILDER_NAME)
  -h, --help       Show this help message

Examples:
  $SCRIPT_NAME ./agentcore strands-agents
  $SCRIPT_NAME ./agentcore strands-agents v1.0.0
  $SCRIPT_NAME ./agentcore strands-agents latest --no-cache

Exit Codes:
  0  Success - image built successfully
  1  Invalid arguments or missing dependencies
  2  Dockerfile not found
  3  Docker build failed
  4  Buildx configuration failed

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

check_dependencies() {
  if ! command -v docker &>/dev/null; then
    log_error "Docker not found. Install Docker Desktop or Docker Engine."
    log_error "Suggestion: https://docs.docker.com/get-docker/"
    exit 1
  fi

  if ! docker buildx version &>/dev/null; then
    log_error "Docker Buildx not available."
    log_error "Suggestion: Install with 'docker buildx create --use' or upgrade Docker Desktop."
    exit 1
  fi
}

parse_args() {
  if [[ $# -eq 0 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    usage
  fi

  if [[ $# -lt 2 ]]; then
    log_error "Missing required arguments."
    log_error "Usage: $SCRIPT_NAME <agent-directory> <repository-name> [tag] [options]"
    exit 1
  fi

  AGENT_DIR="$1"
  REPO_NAME="$2"
  TAG="${3:-latest}"

  shift 2
  [[ $# -gt 0 ]] && shift

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-cache)
        NO_CACHE=true
        shift
        ;;
      --builder)
        CUSTOM_BUILDER="$2"
        shift 2
        ;;
      *)
        log_error "Unknown option: $1"
        exit 1
        ;;
    esac
  done

  if [[ -n "$CUSTOM_BUILDER" ]]; then
    BUILDER_NAME="$CUSTOM_BUILDER"
  fi
}

validate_agent_directory() {
  if [[ ! -d "$AGENT_DIR" ]]; then
    log_error "Agent directory not found: $AGENT_DIR"
    log_error "Suggestion: Provide a valid path to your Strands agent project."
    exit 2
  fi

  if [[ ! -f "$AGENT_DIR/Dockerfile" ]]; then
    log_error "Dockerfile not found in $AGENT_DIR"
    log_error "Suggestion: Create a Dockerfile in your agent directory with ARM64 base image."
    exit 2
  fi
}

configure_buildx() {
  log_info "Checking Docker Buildx availability..."

  if docker buildx inspect "$BUILDER_NAME" &>/dev/null; then
    log_info "Using existing buildx builder: $BUILDER_NAME"
    docker buildx use "$BUILDER_NAME"
    return 0
  fi

  log_info "Creating buildx builder: $BUILDER_NAME"
  
  if ! docker buildx create \
    --name "$BUILDER_NAME" \
    --driver docker-container \
    --use \
    --bootstrap; then
    log_error "Failed to create buildx builder."
    log_error "Suggestion: Check Docker daemon is running and you have sufficient permissions."
    exit 4
  fi

  log_success "Buildx builder created: $BUILDER_NAME"
}

build_image() {
  local image_name="$REPO_NAME:$TAG"
  local cache_flag=""

  if [[ "$NO_CACHE" == "true" ]]; then
    cache_flag="--no-cache"
  fi

  log_info "Building Docker image for ARM64..."
  log_info "Image: $image_name"
  log_info "Context: $AGENT_DIR"
  log_info "Platform: linux/arm64"

  if ! docker buildx build \
    --platform linux/arm64 \
    --tag "$image_name" \
    --load \
    $cache_flag \
    "$AGENT_DIR"; then
    log_error "Build failed. Check Dockerfile syntax and build context."
    log_error "Suggestion: Review build logs above for specific errors."
    exit 3
  fi

  log_success "Image built: $image_name (linux/arm64)"
}

display_image_info() {
  local image_name="$REPO_NAME:$TAG"
  
  local image_id
  image_id=$(docker images "$image_name" --format "{{.ID}}" | head -n1)
  
  local image_size
  image_size=$(docker images "$image_name" --format "{{.Size}}" | head -n1)

  log_info "Image ID: sha256:$image_id"
  log_info "Image size: $image_size"

  local architecture
  architecture=$(docker inspect "$image_name" --format '{{.Architecture}}' 2>/dev/null || echo "unknown")
  
  if [[ "$architecture" != "arm64" ]]; then
    log_error "Warning: Image architecture is $architecture, expected arm64"
    log_error "Suggestion: Verify Dockerfile uses ARM64-compatible base image."
  fi
}

main() {
  parse_args "$@"
  check_dependencies
  validate_agent_directory
  configure_buildx
  build_image
  display_image_info
  
  log_success "Build complete!"
}

main "$@"
