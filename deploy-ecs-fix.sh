#!/bin/bash
set -e

ACCOUNT_ID="568790270051"
REGION="us-east-1"
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/bidopsai/app"

echo "================================"
echo "🚀 ECS Deployment Fix"
echo "================================"

# Step 1: Build web app
echo ""
echo "📦 Step 1/4: Building web app Docker image..."
docker build -f docker/apps/web/Dockerfile \
  --build-arg NEXT_PUBLIC_API_URL=https://api.bidops.ai \
  --build-arg NEXT_PUBLIC_AGENT_CORE_URL=http://agentcore.bidopsai.local:8080 \
  --build-arg NEXT_PUBLIC_AWS_REGION=us-east-1 \
  --build-arg NEXT_PUBLIC_COGNITO_USER_POOL_ID=TBD \
  --build-arg NEXT_PUBLIC_COGNITO_CLIENT_ID=TBD \
  -t bidopsai/app:latest .

echo ""
echo "🔐 Step 2/4: Logging into ECR..."
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

echo ""
echo "🏷️  Step 3/4: Tagging and pushing to ECR..."
docker tag bidopsai/app:latest ${ECR_REPO}:latest
docker push ${ECR_REPO}:latest

echo ""
echo "☁️  Step 4/4: Deploying ComputeStack..."
cd infra
source .venv/bin/activate
echo "Running CDK diff to show what will change..."
cdk diff ComputeStack || true
echo ""
read -p "Continue with deployment? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  cdk deploy ComputeStack
else
  echo "Deployment cancelled"
  exit 0
fi

echo ""
echo "✅ Deployment complete!"
echo "Check ECS service status with: aws ecs describe-services --cluster bidopsai-cluster --services BffService --region us-east-1"
