#!/usr/bin/env bash
# Redeploys the "canvas-connect" EC2 instance (see cloudformation.yml) to
# the image CI just built and pushed to ECR (job build-and-push in
# .github/workflows/ci-cd.yml), health-checks it, and automatically rolls
# back to the last known-good image if the health check fails. Talks to the
# instance over SSM only (no SSH).
#
# Required env vars: AWS_REGION, GITHUB_SHA
# Optional: DEPLOY_HEALTH_URL — health check (and therefore rollback) is
#           skipped, with a warning, if it's not set.
set -euo pipefail

: "${AWS_REGION:?}"
: "${GITHUB_SHA:?}"

LAST_GOOD_PARAM="/canvas-connect/last-good-sha"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/canvas-connect"
ECR_REGISTRY="${ECR_URI%/*}"

INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=canvas-connect" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].InstanceId" --output text)

if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" = "None" ]; then
  echo "::error::No running 'canvas-connect' EC2 instance found — has deploy/cloudformation.yml been deployed?"
  exit 1
fi
echo "Target instance: $INSTANCE_ID"

# Runs commands on the instance over SSM and waits for them to finish.
# Prints the command's stdout/stderr either way. Returns the command's exit
# status (0 = Success) without itself aborting the script (see set -e note
# on callers below).
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

# Only pulls config files that matter for running a prebuilt image (not the
# whole app source — the image already has it baked in).
deploy_tag() {
  local tag="$1"
  echo "Deploying image tag: $tag"
  run_on_instance "Deploy $tag via GitHub Actions" \
    "set -euo pipefail" \
    "cd /opt/app" \
    "git fetch origin main" \
    "git checkout origin/main -- docker-compose.yml docker-compose.prod.yml deploy/Caddyfile" \
    "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}" \
    "docker pull ${ECR_URI}:${tag}" \
    "APP_IMAGE=${ECR_URI}:${tag} docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
}

health_check() {
  if [ -z "${DEPLOY_HEALTH_URL:-}" ]; then
    echo "::warning::DEPLOY_HEALTH_URL not set — skipping health check (deploy is unverified, no rollback possible)."
    return 0
  fi
  for i in $(seq 1 20); do
    if curl -fsS -o /dev/null "$DEPLOY_HEALTH_URL"; then
      echo "Health check passed: $DEPLOY_HEALTH_URL is up."
      return 0
    fi
    echo "Attempt $i/20: $DEPLOY_HEALTH_URL not healthy yet, retrying in 5s..."
    sleep 5
  done
  return 1
}

LAST_GOOD=$(aws ssm get-parameter --name "$LAST_GOOD_PARAM" --query "Parameter.Value" --output text 2>/dev/null || echo "")

if ! deploy_tag "$GITHUB_SHA"; then
  echo "::error::Deploy command failed on the instance (see output above) — nothing was health-checked or rolled back."
  exit 1
fi

if health_check; then
  aws ssm put-parameter --name "$LAST_GOOD_PARAM" --value "$GITHUB_SHA" --type String --overwrite >/dev/null
  echo "Deploy of $GITHUB_SHA succeeded and is healthy."
  exit 0
fi

echo "::error::Health check failed after deploying $GITHUB_SHA."

if [ -z "$LAST_GOOD" ] || [ "$LAST_GOOD" = "None" ]; then
  echo "::error::No previous known-good deploy recorded (first-ever deploy?) — nothing to roll back to. Manual intervention needed."
  exit 1
fi

echo "Rolling back to last known-good image: $LAST_GOOD"
if deploy_tag "$LAST_GOOD" && health_check; then
  echo "::warning::Rolled back to $LAST_GOOD after $GITHUB_SHA failed its health check."
else
  echo "::error::Rollback to $LAST_GOOD also failed — manual intervention needed."
fi
exit 1
