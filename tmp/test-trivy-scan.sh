#!/bin/bash
set -e

echo "🔍 Testing Trivy Security Scanning Locally"
echo "=========================================="
echo ""

TRIVY=/tmp/trivy/trivy

# Test 1: Scan Frontend Dockerfile
echo "📦 Test 1: Scanning Frontend (docker/apps/web)"
echo "------------------------------------------------"
if [ -f "docker/apps/web/Dockerfile" ]; then
    echo "✓ Frontend Dockerfile found"
    
    # Scan for vulnerabilities (without building)
    echo "Running Trivy config scan..."
    $TRIVY config docker/apps/web/Dockerfile \
        --severity CRITICAL,HIGH \
        --exit-code 0 \
        --format table
    
    echo ""
    echo "✓ Frontend Dockerfile scan completed"
else
    echo "✗ Frontend Dockerfile not found!"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test 2: Scan AgentCore Dockerfile
echo "📦 Test 2: Scanning AgentCore (agentcore)"
echo "----------------------------------------"
if [ -f "agentcore/Dockerfile" ]; then
    echo "✓ AgentCore Dockerfile found"
    
    # Scan for vulnerabilities (without building)
    echo "Running Trivy config scan..."
    $TRIVY config agentcore/Dockerfile \
        --severity CRITICAL,HIGH \
        --exit-code 0 \
        --format table
    
    echo ""
    echo "✓ AgentCore Dockerfile scan completed"
else
    echo "✗ AgentCore Dockerfile not found!"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test 3: Scan filesystem for secrets/misconfigurations
echo "📦 Test 3: Scanning for secrets and misconfigurations"
echo "-----------------------------------------------------"
echo "Scanning .github/workflows directory..."
$TRIVY config .github/workflows/ \
    --severity CRITICAL,HIGH \
    --exit-code 0 \
    --format table

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test 4: What the pipeline will actually do (if images were built)
echo "📦 Test 4: Pipeline Simulation (image scanning)"
echo "-----------------------------------------------"
echo "NOTE: This requires building the Docker images first."
echo "In the pipeline, Trivy will scan the actual built images like:"
echo ""
echo "  trivy image \\"
echo "    --format sarif \\"
echo "    --output trivy-results.sarif \\"
echo "    --severity CRITICAL,HIGH \\"
echo "    <ECR_REPO_URI>:develop-abc123d"
echo ""
echo "The SARIF output gets uploaded to GitHub Security tab."

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Local Trivy Testing Complete!"
echo ""
echo "Summary:"
echo "--------"
echo "• Trivy can scan Dockerfiles for misconfigurations"
echo "• Trivy can scan built images for vulnerabilities"
echo "• Pipeline will scan images after build and upload to GitHub Security"
echo "• Exit code 0 = Report only (won't fail build)"
echo ""
