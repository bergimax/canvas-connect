# On-call engineer

`poll.sh` polls Grafana's alert API every minute and, when an alert
**fires** (not just goes Pending), hands its full details to a headless
coding agent to do a first-pass investigation — so by the time a human
looks at it, there's already a triage report in `incidents/` grounded in
the actual code, not just the alert text.

Today there's one alert to react to: [`observability/grafana/provisioning/alerting/component-creation-failures.yml`](../observability/grafana/provisioning/alerting/component-creation-failures.yml). This isn't specific to that alert, though — any alert Grafana fires gets the same treatment.

## Run it

```
GRAFANA_URL=http://localhost:3001 ./poll.sh
```

Loops forever, polling every 60s (`Ctrl+C` to stop). Or run a single cycle — for cron/systemd-timer setups that already provide the "every minute" part:

```
./poll.sh --once
```

Needs `curl`, `jq`, and whatever `AGENT_CMD` points at (`claude` by default) on `PATH`.

## What happens when an alert fires

1. `poll.sh` calls Grafana's Alertmanager-compatible API (`/api/alertmanager/grafana/api/v2/alerts`) — this only ever lists alerts that have actually fired (past their rule's `for` duration), never ones merely Pending, matching "when an alert fires" rather than "when a threshold is momentarily crossed".
2. Each alert's `fingerprint` is checked against `.state.json` (gitignored, local runtime state). A fingerprint not seen before is a **new incident** — its fingerprint gets recorded so it isn't re-notified on every subsequent poll while still firing, and gets dropped from state (so it starts over as "new") once it resolves.
3. For each new incident, `poll.sh` builds a prompt — `prompt-template.md`'s static instructions, followed by the alert's labels/annotations in both human-readable and raw-JSON form — and runs `$AGENT_CMD` with that prompt as its argument.
4. The agent's response is written to `incidents/<timestamp>-<fingerprint>.md` alongside the raw alert payload.

## The agent only investigates — it can't act

`AGENT_CMD` defaults to `claude -p --restricted --output-format json`:

- `-p` — headless: print the result and exit, no interactive session.
- `--restricted` — removes Bash/code-execution tools and WebFetch, confines file access to the working directory, and ignores project/user settings files that might otherwise grant broader permissions. The agent can read and grep the repo; it cannot run commands, edit files, deploy anything, or fetch the dashboard/logs the alert links to (no network access in this mode) — it reasons from the code and the alert payload it's given, and says so explicitly when it needs a human to go check something it can't reach.
- `--output-format json` — so `poll.sh` can pull out `.result` (the actual findings) for the incident report; the full JSON (cost, session id, etc.) is discarded, only the text is kept today.

This is a deliberate default, not a limitation to work around: an unattended process triggered by production alerts should not be able to take action on its own. If you want it to also propose or apply a fix, that's a real decision to make explicitly — e.g. pointing `AGENT_CMD` at an agent invocation with broader tool access, running in an isolated worktree, with its own review step before anything merges. Nothing here does that.

## Config (env vars)

| Variable | Default | Purpose |
| --- | --- | --- |
| `GRAFANA_URL` | `http://localhost:3001` | Grafana instance to poll |
| `GRAFANA_API_TOKEN` | unset | Preferred auth — a Grafana service account token (Bearer). A `Viewer` role is enough; this only ever reads. |
| `GRAFANA_USER` / `GRAFANA_PASSWORD` | `admin` / `admin` | Fallback basic auth if no token is set — fine for local dev, not for a real deployment. |
| `POLL_INTERVAL_SECONDS` | `60` | Loop mode only (not `--once`) |
| `AGENT_CMD` | `claude -p --restricted --output-format json` | How to invoke the headless agent; the built prompt is appended as its final argument |
| `STATE_FILE` | `on-call-engineer/.state.json` | Tracks already-notified fingerprints |
| `INCIDENTS_DIR` | `on-call-engineer/incidents` | Where reports get written |
| `PROMPT_TEMPLATE` | `on-call-engineer/prompt-template.md` | Static instructions prepended to every alert's details |
| `REPO_ROOT` | this repo's root | Working directory the agent runs in |

## Verified

Ran end-to-end against the real stack, not just read for shape: brought `observability/docker-compose.yml` up, tripped the `component-creation-failures` alert for real (see its own file for how), watched it reach `Alerting`, then ran `poll.sh --once` against the live Grafana API with `AGENT_CMD` pointed at the real `claude` CLI. It correctly detected the new fingerprint, invoked the agent, and got back a genuine, code-grounded investigation (it traced the failure path through `app/routers/canvas.py`/`app/store.py` and flagged a real latent bug — a shared, process-lifetime SQLAlchemy session that's never rolled back on error). A second `--once` run against the still-firing alert correctly did **not** re-invoke the agent; after the alert resolved, its fingerprint dropped out of state on the next poll. Also checked `GRAFANA_API_TOKEN` auth against a real `Viewer`-role service account — 200s all round, no silent auth failure.
