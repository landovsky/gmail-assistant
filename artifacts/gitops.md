# GitOps Context

## Infrastructure

**Provider:** DigitalOcean
**Platform:** K3s cluster on single VPS
**Orchestration:** Kubernetes (K3s) with Flux CD GitOps
**Container Runtime:** containerd (K3s default)
**Container Registry:** GitHub Container Registry (`ghcr.io/landovsky/gmail-assistant`)
**DNS:** DigitalOcean DNS management
**Ingress:** Traefik (bundled with K3s)
**TLS:** cert-manager + Let's Encrypt

## Environments

| Environment | Trigger | URL |
|------------|---------|-----|
| **Production** | Push to `production` branch | `https://gmail.kopernici.cz` |

Single environment. No staging. Development happens on `main`, deploy by merging to `production`.

## Deployment

**Method:** GitOps — push to main triggers image build, Flux detects new image and updates cluster
**K3s Manifests Repo:** `github.com/landovsky/k3s` (`apps/gmail-assistant/`)
**Image:** `ghcr.io/landovsky/gmail-assistant`

**Deploy Process:**
1. Push code to `main` branch
2. GitHub Actions builds Docker image, pushes to ghcr.io with semver tag
3. Flux ImageUpdateAutomation detects new tag (polls every 5m)
4. Flux commits updated image tag to k3s repo
5. Flux Kustomization applies updated manifests to cluster
6. K3s pulls new image, restarts pod with rolling update

**Health Checks:**
- Liveness: `GET /api/health` (period: 30s, initial delay: 10s)
- Readiness: `GET /api/health` (period: 10s, initial delay: 5s)

## Build & Runtime

**Docker Image:** Multi-stage build with uv
- Builder: `python:3.12-slim` + uv (installs deps into venv)
- Runtime: `python:3.12-slim` (copies venv from builder)

**Dockerfile:** `Dockerfile` (project root)

**Process:**
```
web: uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Single process runs the FastAPI app with embedded async worker pool (3 workers) and scheduler.

## Services

**Database:** SQLite with PersistentVolumeClaim (1Gi, `local-path` storageClass)
**LLM Gateway:** LiteLLM (Gemini for classification, Gemini/Claude for drafts)
**External APIs:** Gmail API (OAuth), Google Pub/Sub (webhook push notifications)

**Connection:**
- Database: Local file at `/app/data/inbox.db`
- Gmail: OAuth credentials + refresh token at `/app/config/`

## Monitoring & Logging

**Error Tracking:**
- **Service:** BugSink (Sentry-compatible)
- **DSN:** `GMA_SENTRY_DSN` env var
- **Endpoint:** `bugs.kopernici.cz/66`

**Logs:**
- Container stdout/stderr via `kubectl logs`
- Log level configurable via `GMA_SERVER_LOG_LEVEL` (currently `debug`)

**Admin UI:** `https://gmail.kopernici.cz/admin/` — SQLAdmin read-only database browser (emails, jobs, events, LLM calls)

## Backups

**Database:** Not yet configured. SQLite file on PVC (`local-path`).
**Recovery:** Rebuild from Git (manifests) + recreate secrets manually.

## Secrets Management

**Storage:** Kubernetes Secrets (created manually via `kubectl`)
**Script:** `bin/k8s-update-secrets` — deletes and recreates both secrets from local env/files
**Rotation:** Manual

**Two secrets:**

`gmail-assistant-secrets` (API keys):
```bash
kubectl create secret generic gmail-assistant-secrets \
  --from-literal=GEMINI_API_KEY='...' \
  --from-literal=ANTHROPIC_API_KEY='...' \
  -n default
```

`gmail-assistant-config` (OAuth files):
```bash
kubectl create secret generic gmail-assistant-config \
  --from-file=credentials.json=config/credentials.json \
  --from-file=token.json=config/token.json \
  -n default
```

## CI/CD Pipeline

**PR/Branch Testing:** `.github/workflows/ci.yml`
- Ruff lint + format check
- pytest on Python 3.11 + 3.12

**Docker Build:** `.github/workflows/docker.yml`
- Triggered on push to `main`
- Builds multi-stage Docker image with uv
- Pushes to `ghcr.io/landovsky/gmail-assistant:{version}` + `:latest`
- Version extracted from `pyproject.toml`
- Uses GitHub Actions cache (gha)

**Deployment Flow:**
1. Develop on feature branches, merge to `main`
2. Push triggers CI tests (lint + pytest)
3. Merge `main` → `production` → Docker build + push to ghcr.io
4. Flux detects new image → auto-deploys to cluster

## Configuration

**Environment Variables (K8s deployment.yaml):**

**Core Application:**
- `GMA_ENVIRONMENT` — `production`
- `GMA_SERVER_LOG_LEVEL` — `debug` (will switch to `info` when stable)
- `GMA_SENTRY_DSN` — BugSink endpoint

**Database:**
- `GMA_DB_BACKEND` — `sqlite`
- `GMA_DB_SQLITE_PATH` — `/app/data/inbox.db`

**Authentication:**
- `GMA_AUTH_CREDENTIALS_FILE` — `/app/config/credentials.json`
- `GMA_AUTH_TOKEN_FILE` — `/app/config/token.json`

**Secrets (via secretKeyRef):**
- `GEMINI_API_KEY` — Google Gemini API access (required)
- `ANTHROPIC_API_KEY` — Anthropic API access (optional)

## Kubernetes Resources

**Namespace:** `default`

| Resource | Name | Notes |
|----------|------|-------|
| Deployment | `gmail-assistant-deployment` | 1 replica, 256Mi/200m req, 512Mi/500m limit |
| Service | `gmail-assistant-service` | ClusterIP, port 80 → 8000 |
| Ingress | `gmail-assistant-ingress` | `gmail.kopernici.cz`, TLS via Let's Encrypt |
| PVC | `gmail-assistant-db` | 1Gi, local-path, ReadWriteOnce |
| Secret | `gmail-assistant-secrets` | API keys |
| Secret | `gmail-assistant-config` | OAuth credentials.json + token.json |
| Middleware | `redirect-https` | Traefik HTTPS redirect |
| ImageRepository | `gmail-assistant` | Scans ghcr.io every 5m |
| ImagePolicy | `gmail-assistant` | Semver >=0.0.0 |
| ImageUpdateAutomation | `gmail-assistant` | Auto-commits tag updates |

## Volumes

| Mount Path | Source | Purpose |
|------------|--------|---------|
| `/app/data` | PVC `gmail-assistant-db` | SQLite database (inbox.db + WAL) |
| `/app/config` | Secret `gmail-assistant-config` | OAuth credentials (read-only) |

## Post-Deploy Checklist

- [ ] DNS A record: `gmail.kopernici.cz` → cluster IP
- [ ] Create K8s secrets: `bin/k8s-update-secrets`
- [ ] Update Gmail Pub/Sub webhook URL to `https://gmail.kopernici.cz/webhook/gmail`
- [ ] Verify: `curl https://gmail.kopernici.cz/api/health`
- [ ] Verify admin: `https://gmail.kopernici.cz/admin/`

## Useful Commands

```bash
# Check deployment status
kubectl get pods -l app=gmail-assistant -n default
flux get kustomization gmail-assistant

# View logs
kubectl logs deployment/gmail-assistant-deployment -n default --tail=100 -f

# Force redeploy
kubectl rollout restart deployment/gmail-assistant-deployment -n default

# Update secrets
bin/k8s-update-secrets

# Force Flux sync
flux reconcile kustomization gmail-assistant --with-source
```
