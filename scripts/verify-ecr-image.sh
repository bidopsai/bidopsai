#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME=$(basename "$0")
REGION="${AWS_REGION:-us-east-1}"
LIST_ALL=false
JSON_OUTPUT=false

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME <repository-name> [tag] [region] [options]

Verify image exists in ECR and display metadata.

Arguments:
  repository-name  ECR repository name
  tag             Image tag to verify (default: latest)
  region          AWS region (default: \$AWS_REGION or us-east-1)

Options:
  --list-all      List all tags in repository
  --json          Output raw JSON
  -h, --help      Show this help message

Examples:
  $SCRIPT_NAME strands-agents
  $SCRIPT_NAME strands-agents v1.0.0 us-east-1
  $SCRIPT_NAME strands-agents latest us-west-2 --json
  $SCRIPT_NAME strands-agents --list-all

Exit Codes:
  0  Success - image found and metadata displayed
  1  Invalid arguments
  2  AWS credentials invalid
  3  Repository not found
  4  Image tag not found

EOF
  exit 0
}

log_info() {
  echo "[INFO] $*"
}

log_error() {
  echo "[ERROR] $*" >&2
}

check_dependencies() {
  if ! command -v aws &>/dev/null; then
    log_error "AWS CLI not found. Install AWS CLI v2."
    exit 1
  fi

  if ! command -v jq &>/dev/null; then
    log_error "jq not found. Install jq for JSON parsing."
    exit 1
  fi
}

parse_args() {
  if [[ $# -eq 0 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    usage
  fi

  REPO_NAME="$1"
  TAG="latest"
  
  shift

  if [[ $# -gt 0 ]] && [[ ! "$1" =~ ^-- ]]; then
    TAG="$1"
    shift
  fi

  if [[ $# -gt 0 ]] && [[ ! "$1" =~ ^-- ]]; then
    REGION="$1"
    shift
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --list-all)
        LIST_ALL=true
        shift
        ;;
      --json)
        JSON_OUTPUT=true
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
  if ! aws sts get-caller-identity --region "$REGION" &>/dev/null; then
    log_error "AWS credentials not configured."
    log_error "Suggestion: Run 'aws configure'"
    exit 2
  fi
}

check_repository_exists() {
  if ! aws ecr describe-repositories \
    --repository-names "$REPO_NAME" \
    --region "$REGION" &>/dev/null; then
    log_error "Repository not found: $REPO_NAME"
    log_error "Suggestion: Create repository with push-to-ecr.sh or AWS Console."
    exit 3
  fi
}

list_all_tags() {
  log_info "Listing all tags in repository: $REPO_NAME"
  echo ""

  local images
  images=$(aws ecr describe-images \
    --repository-name "$REPO_NAME" \
    --region "$REGION" \
    --output json)

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$images" | jq '.imageDetails'
    return 0
  fi

  printf "%-20s %-20s %-10s %s\n" "TAG" "PUSHED" "SIZE" "DIGEST"
  printf "%-20s %-20s %-10s %s\n" "---" "------" "----" "------"

  echo "$images" | jq -r '
    .imageDetails 
    | sort_by(.imagePushedAt) 
    | reverse 
    | .[] 
    | select(.imageTags != null) 
    | .imageTags[] as $tag 
    | "\($tag)\t\(.imagePushedAt)\t\(.imageSizeInBytes)\t\(.imageDigest)"
  ' | while IFS=$'\t' read -r tag pushed size digest; do
    local pushed_formatted
    pushed_formatted=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${pushed%.*}" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "$pushed")
    
    local size_mb=$((size / 1024 / 1024))
    local digest_short="${digest:0:19}..."
    
    printf "%-20s %-20s %-10s %s\n" "$tag" "$pushed_formatted" "${size_mb} MB" "$digest_short"
  done
}

display_single_tag() {
  if [[ "$JSON_OUTPUT" != "true" ]]; then
    log_info "Querying ECR for image: ${REPO_NAME}:${TAG}"
    echo ""
  fi

  local image_details
  if ! image_details=$(aws ecr describe-images \
    --repository-name "$REPO_NAME" \
    --image-ids imageTag="$TAG" \
    --region "$REGION" \
    --output json 2>&1); then
    log_error "Image tag not found: $TAG"
    log_error "Details: $image_details"
    exit 4
  fi

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    local account_id
    account_id=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
    
    echo "$image_details" | jq --arg repo "$REPO_NAME" --arg region "$REGION" --arg tag "$TAG" --arg account "$account_id" '{
      repository: $repo,
      region: $region,
      imageTag: $tag,
      imageDigest: .imageDetails[0].imageDigest,
      imageSizeInBytes: .imageDetails[0].imageSizeInBytes,
      imagePushedAt: .imageDetails[0].imagePushedAt,
      imageManifestMediaType: .imageDetails[0].imageManifestMediaType,
      imageScanStatus: (.imageDetails[0].imageScanStatus.status // "N/A"),
      registryId: $account
    }'
    return 0
  fi

  local digest size pushed manifest_type
  digest=$(echo "$image_details" | jq -r '.imageDetails[0].imageDigest')
  size=$(echo "$image_details" | jq -r '.imageDetails[0].imageSizeInBytes')
  pushed=$(echo "$image_details" | jq -r '.imageDetails[0].imagePushedAt')
  manifest_type=$(echo "$image_details" | jq -r '.imageDetails[0].imageManifestMediaType')

  local size_mb=$((size / 1024 / 1024))
  
  local account_id
  account_id=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
  
  local ecr_uri="${account_id}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${TAG}"

  cat <<EOF
Repository: $REPO_NAME
Region: $REGION
Tag: $TAG
Digest: $digest
Size: $size_mb MB
Pushed: $pushed
URI: $ecr_uri
Manifest Type: $manifest_type
EOF

  local scan_status
  scan_status=$(echo "$image_details" | jq -r '.imageDetails[0].imageScanStatus.status // "N/A"')
  
  if [[ "$scan_status" != "N/A" ]]; then
    echo "Scan Status: $scan_status"
  fi
}

main() {
  parse_args "$@"
  check_dependencies
  validate_credentials
  check_repository_exists

  if [[ "$LIST_ALL" == "true" ]]; then
    list_all_tags
  else
    display_single_tag
  fi
}

main "$@"
