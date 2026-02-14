Manage the production environment (Pub/Sub + K3s server + Gmail watch).

Usage: /prod-env <command> $ARGUMENTS

Commands: start, stop, status, update-endpoint, logs, restart

$ARGUMENTS is either a subcommand or additional parameters.

## Config

Project: `gmail-mcp-server-support`
Topic: `gmail-push-prod`
Subscription: `gmail-push-prod-sub`
URL: `https://gmail.kopernici.cz`
Namespace: `default`
Deployment: `gmail-assistant-deployment`

## Instructions

**For `status`:**
1. Check subscription: `CLOUDSDK_PYTHON=python3 gcloud pubsub subscriptions describe gmail-push-prod-sub --project=gmail-mcp-server-support --format="yaml(pushConfig.pushEndpoint,state)"`
2. Check pod status: `kubectl get pods -l app=gmail-assistant -n default`
3. Check health endpoint: `curl -s https://gmail.kopernici.cz/api/health`
4. Report all clearly

**For `start`:**
1. Set push endpoint: `CLOUDSDK_PYTHON=python3 gcloud pubsub subscriptions modify-push-config gmail-push-prod-sub --push-endpoint=https://gmail.kopernici.cz/webhook/gmail --project=gmail-mcp-server-support`
2. Register Gmail watch: `curl -X POST https://gmail.kopernici.cz/admin/watch`
3. Verify health: `curl -s https://gmail.kopernici.cz/api/health`
4. Confirm everything is up

**For `stop`:**
1. Clear push endpoint: `CLOUDSDK_PYTHON=python3 gcloud pubsub subscriptions modify-push-config gmail-push-prod-sub --push-endpoint="" --project=gmail-mcp-server-support`
2. Confirm push endpoint is cleared (server stays running — only Gmail push notifications are stopped)

**For `update-endpoint` (URL in $ARGUMENTS):**
1. If $ARGUMENTS contains a URL, use it. Otherwise use `https://gmail.kopernici.cz`.
2. Update push endpoint: `CLOUDSDK_PYTHON=python3 gcloud pubsub subscriptions modify-push-config gmail-push-prod-sub --push-endpoint=<URL>/webhook/gmail --project=gmail-mcp-server-support`
3. Verify: `CLOUDSDK_PYTHON=python3 gcloud pubsub subscriptions describe gmail-push-prod-sub --project=gmail-mcp-server-support --format="value(pushConfig.pushEndpoint)"`
4. Report the new endpoint

**For `logs` (optional line count in $ARGUMENTS):**
1. Default to 100 lines if no count specified
2. Show logs: `kubectl logs deployment/gmail-assistant-deployment -n default --tail=<count>`

**For `restart`:**
1. Confirm with user before proceeding (production restart!)
2. Restart: `kubectl rollout restart deployment/gmail-assistant-deployment -n default`
3. Wait for rollout: `kubectl rollout status deployment/gmail-assistant-deployment -n default --timeout=120s`
4. Verify health: `curl -s https://gmail.kopernici.cz/api/health`
5. Report status
