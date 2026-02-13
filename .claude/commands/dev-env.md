Start or stop the v2 dev environment (Pub/Sub + server + Gmail watch).

Usage: /dev-env <command> $ARGUMENTS

Commands: start, stop, status, update-endpoint

$ARGUMENTS is either a subcommand or an ngrok URL (for start/update-endpoint).

## Config

Project: `gmail-mcp-server-support`
Topic: `gmail-push-dev`
Subscription: `gmail-push-dev-sub`

## Instructions

**For `status`:**
1. Check subscription: `gcloud pubsub subscriptions describe gmail-push-dev-sub --project=gmail-mcp-server-support --format="yaml(pushConfig.pushEndpoint,state)"`
2. Check server: `pgrep -f "uvicorn src.main:app"`
3. Report both clearly

**For `start` (optionally with ngrok URL in $ARGUMENTS):**
1. If $ARGUMENTS contains an ngrok URL, use it. Otherwise ask user for their current ngrok URL.
2. Set push endpoint: `gcloud pubsub subscriptions modify-push-config gmail-push-dev-sub --push-endpoint=<URL>/webhook/gmail --project=gmail-mcp-server-support`
3. Start server if not running: `.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000` (run in background)
4. Call the admin API to register Gmail watch: `curl -X POST http://localhost:8000/admin/watch` (if endpoint exists, otherwise note it needs implementing)
5. Confirm everything is up

**For `stop`:**
1. Clear push endpoint: `gcloud pubsub subscriptions modify-push-config gmail-push-dev-sub --push-endpoint="" --project=gmail-mcp-server-support`
2. Stop server: kill uvicorn process
3. Confirm both are down

**For `update-endpoint` (ngrok URL in $ARGUMENTS):**
1. If $ARGUMENTS contains an ngrok URL, use it. Otherwise ask user.
2. Update push endpoint: `gcloud pubsub subscriptions modify-push-config gmail-push-dev-sub --push-endpoint=<URL>/webhook/gmail --project=gmail-mcp-server-support`
3. Verify: `gcloud pubsub subscriptions describe gmail-push-dev-sub --project=gmail-mcp-server-support --format="value(pushConfig.pushEndpoint)"`
4. Report the new endpoint
