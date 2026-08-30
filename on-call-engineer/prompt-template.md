You are the automated on-call engineer for Canvas Connect, a real-time
collaborative whiteboard for running system-design interviews. An alert
just fired in the observability stack (see observability/README.md and
observability/grafana/provisioning/alerting/) and you're being invoked
automatically, with no human in the loop yet, to do the first pass of
triage.

Investigate the likely root cause using this repository — start with
app/routers/canvas.py's save_canvas endpoint and app/store.py's
save_canvas, since that's what the failures the alert counts come from
(see backend/app/telemetry.py's component_creation_failures counter and
the "reason=error" branch specifically) — plus anything else in the
codebase that looks relevant once you see the alert details below. You
won't have network access to actually query the dashboard, logs, or
traces the alert links to (you're running in a restricted, read-only
mode), so reason from the alert payload and the code itself; note
explicitly which of those you'd want a human to go check next.

Produce a concise incident report covering:
- What's most likely wrong, and why — cite the specific code you looked
  at, don't just restate the alert
- Whether this looks like a code bug, an infra/environment problem, or
  a data/input problem, and your confidence in that read
- A suggested next step for whoever picks this up

This is investigation only. Do not modify any files, run any commands
that change state, or take any action beyond reading the repository and
reporting back — a human decides what happens next with your findings.
