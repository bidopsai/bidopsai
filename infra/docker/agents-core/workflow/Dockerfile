# =============================================================================
# BidOpsAI Workflow Supervisor Agent - Production Dockerfile
# =============================================================================
# Production deployment for AWS Bedrock AgentCore Runtime
# Based on AWS AgentCore best practices

FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Install system dependencies
RUN echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid-until && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm /etc/apt/apt.conf.d/99no-check-valid-until

# Copy uv configuration files AND README (needed for hatchling build)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies using uv
RUN uv sync --no-cache

# Copy the entire source directory
COPY . ./

# Set environment variables
ENV PORT=8080
ENV HOST=0.0.0.0
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_CACHE_DIR=/tmp/uv-cache
ENV HOME=/root

# Create cache directory
RUN mkdir -p /tmp/uv-cache && chmod 777 /tmp/uv-cache

# Create non-root user for production
RUN useradd -m -u 1000 bedrock_agentcore && \
    chown -R bedrock_agentcore:bedrock_agentcore /app /tmp/uv-cache

# Switch to non-root user
USER bedrock_agentcore

# Expose AgentCore port
EXPOSE 8080

# Health check using AgentCore /ping endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/ping || exit 1

# Set labels for metadata
ARG VERSION=0.1.0
ARG BUILD_DATE
LABEL maintainer="support@bidopsai.com" \
      description="BidOpsAI Workflow Supervisor Agent - AWS Bedrock AgentCore Runtime" \
      version="${VERSION}" \
      build-date="${BUILD_DATE}"

# Run with uvicorn using the BedrockAgentCoreApp instance
CMD ["uv", "run", "--no-cache", "uvicorn", "supervisors.workflow.agent_executor:app", "--host", "0.0.0.0", "--port", "8080"]