#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME=$(basename "$0")
REGION="${AWS_REGION:-us-east-1}"
NO_VERIFY=false

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME <image-name> <repository-name> [region] [options]

Authenticate with AWS ECR and push Docker image to ECR repository.

Arguments:
  image-name        Local Docker image name (e.g., strands-agents:latest)
  repository-name   ECR repository name
  region           AWS region for ECR (default: \$AWS_REGION or us-east-1)

Options:
  --no-verify      Skip post-push verification
  -h, --help       Show this help message

Examples:
  $SCRIPT_NAME strands-agents:latest strands-agents
  $SCRIPT_NAME strands-agents:v1.0.0 strands-agents us-west-2

Exit Codes:
  0  Success - image pushed to ECR
  1  Invalid arguments or configuration
  2  AWS credentials invalid or missing
  3  ECR authentication failed
  4  Image not found locally
  5  Push operation failed
  6  Post-push verification failed

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
  if ! command -v aws &>/dev/null; then
    log_error "AWS CLI not found. Install AWS CLI v2."
    log_error "Suggestion: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
    exit 1
  fi

  if ! command -v docker &>/dev/null; then
    log_error "Docker not found. Install Docker Desktop or Docker Engine."
    exit 1
  fi

  if ! command -v jq &>/dev/null; then
    log_error "jq not found. Install jq for JSON parsing."
    log_error "Suggestion: brew install jq (macOS) or apt-get install jq (Linux)"
    exit 1
  fi
}

parse_args() {
  if [[ $# -eq 0 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    usage
  fi

  if [[ $# -lt 2 ]]; then
    log_error "Missing required arguments."
    log_error "Usage: $SCRIPT_NAME <image-name> <repository-name> [region] [options]"
    exit 1
  fi

  IMAGE_NAME="$1"
  REPO_NAME="$2"
  
  shift 2

  if [[ $# -gt 0 ]] && [[ ! "$1" =~ ^-- ]]; then
    REGION="$1"
    shift
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-verify)
        NO_VERIFY=true
        shift
        ;;
      *)
        log_error "Unknown option: $1"
        exit 1
        ;;
    esac
  done
}

validate_credentials() {
  log_info "Validating AWS credentials..."

  if ! aws sts get-caller-identity --region "$REGION" &>/dev/null; then
    log_error "AWS credentials not configured or invalid."
    log_error "Suggestion: Run 'aws configure' or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY."
    exit 2
  fi

  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
  
  log_info "Account ID: $ACCOUNT_ID"
}

validate_local_image() {
  log_info "Checking local image: $IMAGE_NAME"

  if ! docker images "$IMAGE_NAME" --format "{{.Repository}}:{{.Tag}}" | grep -q "^${IMAGE_NAME}$"; then
    log_error "Image not found: $IMAGE_NAME"
    log_error "Suggestion: Build the image first with build-agent.sh or docker build."
    exit 4
  fi

  log_info "Local image found: $IMAGE_NAME"
}

ensure_ecr_repository() {
  log_info "Checking ECR repository: $REPO_NAME"

  if aws ecr describe-repositories \
    --repository-names "$REPO_NAME" \
    --region "$REGION" &>/dev/null; then
    log_info "ECR repository exists: $REPO_NAME"
    return 0
  fi

  log_info "Creating ECR repository: $REPO_NAME (region: $REGION)"

  if ! aws ecr create-repository \
    --repository-name "$REPO_NAME" \
    --image-scanning-configuration scanOnPush=true \
    --region "$REGION" &>/dev/null; then
    log_error "Failed to create ECR repository."
    log_error "Suggestion: Check IAM permissions for ecr:CreateRepository."
    exit 5
  fi

  log_success "ECR repository created: $REPO_NAME"
}

authenticate_ecr() {
  log_info "Authenticating with ECR..."

  local ecr_registry="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

  if ! aws ecr get-login-password --region "$REGION" | \
    docker login --username AWS --password-stdin "$ecr_registry" &>/dev/null; then
    log_error "ECR authentication failed."
    log_error "Suggestion: Check IAM permissions for ecr:GetAuthorizationToken."
    exit 3
  fi

  log_success "Authenticated with ECR: $ecr_registry"
}

push_image() {
  local ecr_uri="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"
  local tag="${IMAGE_NAME##*:}"
  
  if [[ "$tag" == "$IMAGE_NAME" ]]; then
    tag="latest"
  fi

  local ecr_image="${ecr_uri}:${tag}"

  log_info "Tagging image: $IMAGE_NAME -> $ecr_image"
  
  if ! docker tag "$IMAGE_NAME" "$ecr_image"; then
    log_error "Failed to tag image."
    exit 5
  fi

  log_info "Pushing image to ECR..."
  log_info "Destination: $ecr_image"

  if ! docker push "$ecr_image"; then
    log_error "Push failed. Check network connectivity and ECR permissions."
    log_error "Suggestion: Retry the push or check Docker logs for details."
    exit 5
  fi

  log_success "Image pushed to ECR"
  log_info "ECR URI: $ecr_image"

  ECR_TAG="$tag"
}

verify_push() {
  if [[ "$NO_VERIFY" == "true" ]]; then
    return 0
  fi

  log_info "Verifying image in ECR..."

  local image_details
  if ! image_details=$(aws ecr describe-images \
    --repository-name "$REPO_NAME" \
    --image-ids imageTag="$ECR_TAG" \
    --region "$REGION" \
    --output json 2>&1); then
    log_error "Post-push verification failed."
    log_error "Image may not be available in ECR yet. Details: $image_details"
    exit 6
  fi

  local digest
  digest=$(echo "$image_details" | jq -r '.imageDetails[0].imageDigest')

  log_success "Image verified in ECR"
  log_info "Image digest: $digest"
}

main() {
  parse_args "$@"
  check_dependencies
  validate_credentials
  validate_local_image
  ensure_ecr_repository
  authenticate_ecr
  push_image
  verify_push
  
  log_success "Push complete!"
}

main "$@"
