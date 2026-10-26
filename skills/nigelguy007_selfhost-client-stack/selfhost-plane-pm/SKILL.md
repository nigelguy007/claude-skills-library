---
name: selfhost-plane-pm
description: Self-host Plane Community Edition as a flat-cost replacement for Jira/Asana/Monday for a 10-30 person team - edition choice (Community vs Commercial Free seat cap), Docker deploy, SMTP, import, upgrades. Use when the user says "Plane", "self-hosted Jira alternative", "project management without per-seat fees", or "deploy Plane for a client".
---

# Plane project management

Run `selfhost-vps-base` first. Needs at least 2 vCPU / 4 GB. Plane runs about ten containers (web, api, workers, Postgres, Redis/Valkey, RabbitMQ, MinIO, proxy).

## Pick the right edition. This decides whether the pitch is true.

Plane ships two different free self-hosted products:
- **Community Edition:** AGPL-3.0, installed with `setup.sh` from GitHub releases. **No seat limit.** This is what makes "flat cost instead of per-seat" true.
- **Commercial Edition, Free tier:** closed source, installed through `prime.plane.so`, **capped at 12 seats**. A 20-person agency on this hits the cap.

For the flat-cost pitch, use **Community Edition**. Some features (certain integrations, advanced workflows, some AI features) are Commercial-only. Check that the client's must-haves exist in CE before selling. Re-verify on Plane's pricing page and in GitHub issue #9086, since Plane's own docs have contradicted each other on this.

## Deploy (Community Edition)

```bash
mkdir -p /srv/plane && cd /srv/plane
curl -fsSL -o setup.sh https://github.com/makeplane/plane/releases/latest/download/setup.sh
chmod +x setup.sh
./setup.sh          # menu: 1) Install, then edit plane-app/plane.env
```

In `plane.env`, set `WEB_URL` / `CORS_ALLOWED_ORIGINS` to `https://pm.clientdomain.com`, set strong DB, RabbitMQ and MinIO passwords, and set `LISTEN_HTTP_PORT` to a local port. Then run `./setup.sh` again and choose Start. Put Caddy in front, or use Plane's built-in proxy with your TLS, but not both on 443.

Open `/god-mode` to create the instance admin straight away, configure SMTP so invites and notifications send, and turn off open sign-up.

## Migration

- Plane has importers for Jira, Linear, Asana and GitHub, and their availability differs by edition. Check what CE ships with at your version. If an importer isn't available, migrate through CSV or the API and budget the hours.
- Don't move everything. Move active projects only and archive the rest as a read-only export.
- Run one team on Plane for 2 weeks before moving the whole company.

## The per-seat math, done honestly

`their per-seat price x headcount x 12` against `(VPS + backups + your retainer) x 12 + setup fee`. On 10-15 seats of a cheap Asana or Monday tier the saving can be thin. It gets strong at 20-30+ seats or on premium tiers. The real cost of switching is retraining and lost integrations, so ask which integrations they rely on (Slack, GitHub, time tracking) before quoting.

## Maintenance

- Upgrade with `./setup.sh` -> Upgrade, after a backup (Postgres dump plus the MinIO uploads volume). Read the release notes, because Plane makes breaking changes between majors.
- Monthly: check the workers and the disk, since MinIO uploads grow. Do user admin as people join and leave.
