#!/usr/bin/env bash
# Polls Grafana's alert API for newly-fired alerts and hands each one to a
# headless coding agent to investigate. See README.md for the full picture.
#
# Runs the poll loop itself (every $POLL_INTERVAL_SECONDS, default 60) —
# pass --once to run a single cycle and exit instead, e.g. for cron/systemd-
# timer setups that already provide the "every minute" part.
#
# Env vars:
#   GRAFANA_URL             Base URL of the Grafana instance to poll.
#                            Default: http://localhost:3001 (this repo's
#                            local observability/docker-compose.yml).
#   GRAFANA_API_TOKEN        Preferred auth: a Grafana service account token
#                            (Bearer). Falls back to GRAFANA_USER/
#                            GRAFANA_PASSWORD basic auth if unset — fine for
#                            local dev, not recommended for a real deploy.
#   GRAFANA_USER             Default: admin
#   GRAFANA_PASSWORD         Default: admin (the docker-compose.yml dev
#                            default — see observability/README.md; use a
#                            real token against a real deployment).
#   POLL_INTERVAL_SECONDS    Default: 60
#   AGENT_CMD                How to invoke the headless coding agent; the
#                            alert prompt is appended as the final argument.
#                            Default: "claude -p --restricted --output-format
#                            json" — headless, and --restricted means no
#                            Bash/code-execution/WebFetch tools, so an
#                            unattended run can only read the repo and
#                            report back, never act on it. Override to point
#                            at a different agent CLI, or to loosen/tighten
#                            what this one's allowed to do.
#   STATE_FILE                Default: <script dir>/.state.json
#   INCIDENTS_DIR              Default: <script dir>/incidents
#   PROMPT_TEMPLATE            Default: <script dir>/prompt-template.md
#   REPO_ROOT                  Default: this repo's root (via git). Passed to
#                              the agent as its working directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3001}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-60}"
AGENT_CMD="${AGENT_CMD:-claude -p --restricted --output-format json}"
STATE_FILE="${STATE_FILE:-$SCRIPT_DIR/.state.json}"
INCIDENTS_DIR="${INCIDENTS_DIR:-$SCRIPT_DIR/incidents}"
PROMPT_TEMPLATE="${PROMPT_TEMPLATE:-$SCRIPT_DIR/prompt-template.md}"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

for cmd in curl jq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "::error::'$cmd' is required but not on PATH." >&2; exit 1; }
done
[ -f "$PROMPT_TEMPLATE" ] || { echo "::error::Prompt template not found: $PROMPT_TEMPLATE" >&2; exit 1; }

mkdir -p "$INCIDENTS_DIR"
[ -f "$STATE_FILE" ] || echo '{}' > "$STATE_FILE"

log() { echo "[$(date -u +%FT%TZ)] $*"; }

# Alertmanager-compatible API: unlike the Prometheus-rules API, this only
# ever lists alerts that have actually fired (past their "for" duration),
# never ones merely Pending — matching "when an alert fires".
fetch_active_alerts() {
  local auth_args=()
  if [ -n "${GRAFANA_API_TOKEN:-}" ]; then
    auth_args=(-H "Authorization: Bearer ${GRAFANA_API_TOKEN}")
  else
    auth_args=(-u "${GRAFANA_USER}:${GRAFANA_PASSWORD}")
  fi
  curl -fsS "${auth_args[@]}" "${GRAFANA_URL%/}/api/alertmanager/grafana/api/v2/alerts" \
    | jq '[.[] | select(.status.state == "active")]'
}

# Builds the prompt for one alert: the static instructions in
# PROMPT_TEMPLATE, followed by that alert's details (both a human-readable
# summary and the full raw payload, so the agent has everything without
# needing tools it doesn't have in --restricted mode).
render_prompt() {
  local alert_json="$1"
  cat "$PROMPT_TEMPLATE"
  echo
  echo "## Alert"
  echo
  jq -r '
    "- Name: " + (.labels.alertname // "unknown") +
    "\n- Service: " + (.labels.service // "unknown") +
    "\n- Environment: " + (.labels.deployment_environment_name // "unknown") +
    "\n- Version: " + (.labels.service_version // "unknown") +
    "\n- Owner: " + (.labels.owner // "unknown") +
    "\n- Severity: " + (.labels.severity // "unknown") +
    "\n- Firing since: " + .startsAt +
    "\n- Dashboard: " + (.annotations.dashboard_url // "n/a") +
    "\n- Summary: " + (.annotations.summary // "n/a") +
    "\n- Description: " + (.annotations.description // "n/a")
  ' <<<"$alert_json"
  echo
  echo "Full raw alert payload:"
  echo
  echo '```json'
  jq '.' <<<"$alert_json"
  echo '```'
}

# Invokes the headless agent for one newly-fired alert and writes an
# incident report with its findings.
handle_new_alert() {
  local alert_json="$1"
  local fingerprint alertname timestamp incident_file prompt agent_output result exit_code
  fingerprint=$(jq -r '.fingerprint' <<<"$alert_json")
  alertname=$(jq -r '.labels.alertname // "unknown"' <<<"$alert_json")
  timestamp=$(date -u +%Y%m%dT%H%M%SZ)
  incident_file="$INCIDENTS_DIR/${timestamp}-${fingerprint}.md"

  log "New alert firing: $alertname ($fingerprint) — invoking headless agent"

  prompt="$(render_prompt "$alert_json")"

  # Word-split AGENT_CMD (a plain space-separated command like the default
  # "claude -p --restricted --output-format json") into an array so the
  # prompt — which can be long, multi-line, and contain quotes — is passed
  # as one properly-preserved final argument, not re-parsed by a shell.
  local -a agent_cmd_array
  read -ra agent_cmd_array <<<"$AGENT_CMD"

  set +e
  agent_output="$(cd "$REPO_ROOT" && "${agent_cmd_array[@]}" "$prompt" 2>&1)"
  exit_code=$?
  set -e

  {
    echo "# Incident: $alertname"
    echo
    echo "- Fingerprint: \`$fingerprint\`"
    echo "- Detected: $timestamp"
    echo "- Agent command: \`$AGENT_CMD\`"
    echo "- Agent exit code: $exit_code"
    echo
    echo "## Agent findings"
    echo
    if result=$(jq -r '.result // empty' <<<"$agent_output" 2>/dev/null) && [ -n "$result" ]; then
      echo "$result"
    else
      echo '```'
      echo "$agent_output"
      echo '```'
    fi
    echo
    echo "## Alert payload"
    echo
    echo '```json'
    jq '.' <<<"$alert_json"
    echo '```'
  } > "$incident_file"

  log "Incident report written to $incident_file"
}

# One poll cycle: fetch active alerts, notify on any fingerprint not
# already known (edge-triggered — a still-firing alert isn't re-notified
# on every poll), and drop resolved fingerprints from state so the same
# alert firing again later is treated as a new incident.
poll_once() {
  local active_json known_json new_fingerprints fp alert
  active_json="$(fetch_active_alerts)"
  known_json="$(cat "$STATE_FILE")"

  new_fingerprints="$(jq -r --argjson known "$known_json" '
    [.[] | .fingerprint] - ($known | keys) | .[]
  ' <<<"$active_json")"

  if [ -n "$new_fingerprints" ]; then
    while IFS= read -r fp; do
      alert="$(jq -c --arg fp "$fp" '.[] | select(.fingerprint == $fp)' <<<"$active_json")"
      handle_new_alert "$alert"
    done <<<"$new_fingerprints"
  fi

  # New state = active alerts only (resolved ones fall out automatically,
  # so the same alert firing again later is treated as a new incident).
  # Keeps each fingerprint's original notifiedAt rather than refreshing it
  # every poll, so it actually reflects "when this incident was first seen".
  jq --argjson known "$known_json" '
    map({
      key: .fingerprint,
      value: {startsAt, notifiedAt: ($known[.fingerprint].notifiedAt // (now | todate))}
    }) | from_entries
  ' <<<"$active_json" > "$STATE_FILE.tmp"
  mv "$STATE_FILE.tmp" "$STATE_FILE"
}

main() {
  if [ "${1:-}" = "--once" ]; then
    poll_once
    exit 0
  fi

  log "Polling $GRAFANA_URL every ${POLL_INTERVAL_SECONDS}s (Ctrl+C to stop)"
  while true; do
    poll_once || log "::warning:: poll cycle failed, will retry next interval"
    sleep "$POLL_INTERVAL_SECONDS"
  done
}

main "$@"
