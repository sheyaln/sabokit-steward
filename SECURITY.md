# Security policy

Steward manages identity. A bug here can let someone create, modify, or
deactivate Authentik users and groups, or tamper with the audit trail.
I take that seriously, but I'm one person -- response times will reflect
that.

## Reporting

Email **shey.alnasrawi@id.me**. Please don't open a public issue for a
security bug.

Include:

- what you found,
- how to reproduce it (PoC or steps),
- the commit / version you found it on.

I'll get back to you as soon as I realistically can. If something is
actively exploitable, say so loudly in the subject line so I prioritize.

Once I've confirmed it, I'll agree a disclosure window with you. Default
is 90 days from acknowledgement, sooner if a fix is ready.

## In scope

- Login bypass (e.g. getting into Steward without being in the configured
  admin group).
- Privilege escalation (a Steward admin gaining more authority over
  Authentik than Steward needs).
- Audit-log integrity (mutations that don't produce a row, or a way to
  alter past rows).
- SSRF, command injection, SQLi, deserialization holes, especially in
  the CSV import pipeline.
- Data leaks via error pages, logs, or audit-log payloads.

## Out of scope

- Issues requiring an attacker who is already an Authentik admin or
  already on the host -- those are platform bugs, report them to
  whoever owns your Authentik install.
- DoS / rate-limiting against the public OIDC endpoints -- Authentik's
  problem.
- Vulnerabilities in third-party deps that don't actually affect
  Steward as configured. Mention them anyway so I can pin or patch.

## Hardening notes

- The dev compose ships with known-weak credentials. Never run
  `--profile authentik` outside an isolated dev environment, and never
  expose port 9000 publicly.
- The federated-commons bundle places Steward's Authentik service account
  in the built-in `authentik Admins` group. That's more authority than
  Steward strictly needs (it only touches users + groups); narrowing
  this to a custom role is on the roadmap.
