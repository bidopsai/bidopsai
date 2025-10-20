# Trivy Security Scan Results

## Summary

✅ **Frontend (docker/apps/web):** Clean - No security issues found
⚠️ **AgentCore (agentcore):** 1 HIGH severity finding

---

## Security Finding: AgentCore Dockerfile

**Severity:** HIGH  
**Issue ID:** AVD-DS-0002  
**Description:** Missing USER command in Dockerfile

### Problem

The AgentCore Dockerfile runs as `root` user by default, which is a security risk:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent.py .
EXPOSE 8000
CMD ["python", "agent.py"]  # ← Runs as root!
```

### Why This Matters

- **Container Escape Risk:** If the Python app is compromised, attacker has root privileges
- **Privilege Escalation:** Easier to exploit the host system
- **Security Best Practice:** Containers should run with least privilege

### Recommended Fix

Add a non-root user before the CMD instruction:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8000

CMD ["python", "agent.py"]
```

### Alternative (Simpler)

If you don't need specific UID/GID:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .

# Switch to nobody user (already exists in base image)
USER nobody

EXPOSE 8000

CMD ["python", "agent.py"]
```

---

## Pipeline Behavior

In your CI/CD pipeline (`ci-cd.yml`), the security scan job:

```yaml
security-scan:
  needs: [changes, build-app, build-agent]
  if: always() && (needs.build-app.result == 'success' || needs.build-agent.result == 'success')
  strategy:
    matrix:
      service:
        - name: app
          condition: needs.build-app.result == 'success'
        - name: agent
          condition: needs.build-agent.result == 'success'
```

**Current Configuration:**
- ✅ Scans will run after successful builds
- ✅ Results uploaded to GitHub Security tab (SARIF format)
- ✅ Won't fail the build (informational only)
- ✅ Uses OIDC authentication (secure)

**What You'll See:**
1. Build succeeds even with security findings
2. Findings appear in GitHub Security → Code scanning alerts
3. Each alert links to the specific CVE/issue
4. You can track remediation over time

---

## Next Steps

### Option 1: Fix Now (Recommended)
Fix the security issue before merging:
```bash
# Edit agentcore/Dockerfile to add USER command
# Commit the fix
# Re-test locally
```

### Option 2: Track in GitHub Security
Merge as-is and track in GitHub Security tab:
- Finding will appear in Security → Code scanning
- Create issue to fix later
- Monitor for new vulnerabilities in future builds

### Option 3: Make Scan Blocking (Strict)
Update pipeline to fail on HIGH/CRITICAL findings:

```yaml
# In security-scan job, change:
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    # ... other settings ...
    exit-code: '1'  # ← Fail build on findings (currently 0)
```

---

## Testing Locally

Run security scans anytime with:

```bash
# Scan Dockerfile for misconfigurations
/tmp/trivy/trivy config agentcore/Dockerfile --severity CRITICAL,HIGH

# Scan built image for vulnerabilities
docker build -t test-image agentcore/
/tmp/trivy/trivy image test-image --severity CRITICAL,HIGH

# Full test suite
./tmp/test-trivy-scan.sh
```

---

## References

- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [AVD-DS-0002: Running as root](https://avd.aquasec.com/misconfig/ds002)
- [Docker Security Best Practices](https://docs.docker.com/develop/security-best-practices/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
