#!/usr/bin/env bash
# Redeploys the "canvas-connect-observability" EC2 instance (see
# deploy/observability-cloudformation.yml) to whatever's on origin/main:
# pulls the latest observability/ config plus the pinned image tags in
# observability/docker-compose.yml, and restarts the stack. Talks to the
# instance over SSM only (no SSH).
#
# Unlike deploy/deploy.sh (the app's deploy), there's no image tag to pass
# in and no "last known-good" rollback: the images here are public,
# pinned tags versioned in git, not something CI builds and promotes, so
# a bad deploy means "revert the commit and redeploy", not "roll back to
# a previous ECR tag".
#
# Required env vars: AWS_REGION
# Optional: DEPLOY_HEALTH_URL — Grafana's health endpoint (e.g.
#           http://<observability-elastic-ip>/api/health); health check
#           is skipped, with a warning, if it's not set.
set -euo pipefail

: "${AWS_REGION:?}"

STACK_NAME="canvas-connect-observability"

INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=${STACK_NAME}" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].InstanceId" --output text)

if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" = "None" ]; then
  echo "::error::No running '${STACK_NAME}' EC2 instance found — has deploy/observability-cloudformation.yml been deployed?"
  exit 1
fi
echo "Target instance: $INSTANCE_ID"

# Runs commands on the instance over SSM and waits for them to finish.
# Prints the command's stdout/stderr either way. Returns the command's exit
# status (0 = Success) without itself aborting the script (see set -e note
# on the caller below). Identical to deploy/deploy.sh's helper of the same
# name — kept duplicated rather than shared, since these are two small,
# independent scripts and a shared-lib indirection isn't worth it here.
run_on_instance() {
  local comment="$1"
  shift
  local params_file
  params_file=$(mktemp)
  printf '%s\n' "$@" | jq -R . | jq -s '{commands: .}' >"$params_file"

  local command_id
  command_id=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --comment "$comment" \
    --parameters "file://$params_file" \
    --query "Command.CommandId" --output text)
  rm -f "$params_file"

  aws ssm wait command-executed --command-id "$command_id" --instance-id "$INSTANCE_ID" || true

  local result
  result=$(aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" --output json)
  echo "$result" | jq '{Status, StandardOutputContent, StandardErrorContent}'
  [ "$(echo "$result" | jq -r '.Status')" = "Success" ]
}

if ! run_on_instance "Deploy observability stack via GitHub Actions" \
  "set -euo pipefail" \
  "cd /opt/observability" \
  "git fetch origin main" \
  "git checkout origin/main -- observability" \
  "docker compose -f observability/docker-compose.yml -f observability/docker-compose.prod.yml pull" \
  "docker compose -f observability/docker-compose.yml -f observability/docker-compose.prod.yml up -d"; then
  echo "::error::Deploy command failed on the instance (see output above)."
  exit 1
fi

if [ -z "${DEPLOY_HEALTH_URL:-}" ]; then
  echo "::warning::DEPLOY_HEALTH_URL not set — skipping health check (deploy is unverified)."
  exit 0
fi

for i in $(seq 1 20); do
  if curl -fsS -o /dev/null "$DEPLOY_HEALTH_URL"; then
    echo "Health check passed: $DEPLOY_HEALTH_URL is up."
    exit 0
  fi
  echo "Attempt $i/20: $DEPLOY_HEALTH_URL not healthy yet, retrying in 5s..."
  sleep 5
done

echo "::error::Health check failed after deploying."
exit 1
