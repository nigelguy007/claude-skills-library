---
name: selfhost-vps-base
description: Prepare a client VPS for a managed self-hosted app (Pipecat, Dify, NocoDB, Listmonk, Plane) - Docker, firewall, Caddy HTTPS reverse proxy, off-server backups, uptime monitoring and an update routine. Use before any selfhost-* deploy skill, or when the user says "set up a server for a client", "harden the VPS", "add backups/monitoring to a client box".
---

# Self-hosted client VPS: base setup

Every selfhost-* skill assumes this base. Do it once per client server.

## Ground rules

- **One client per VPS (or per isolated stack).** Never mix two clients' data in one app instance. Dify's licence forbids multi-tenant use outright; for the rest it is still the safest default.
- **Run it on a real server, not a Claude session.** Claude Code cloud containers are ephemeral and not publicly reachable. Use Hetzner, DigitalOcean, Vultr, Lightsail or similar.
- **The client owns the domain and pays for the API keys where possible.** Then if they leave you, nothing of theirs is held hostage, and you aren't fronting their usage bills.

## Sizing

| App | Minimum | Comfortable |
|---|---|---|
| Listmonk, NocoDB | 1 vCPU / 1-2 GB | 2 vCPU / 2 GB |
| Pipecat bot | 2 vCPU / 2 GB per ~5-10 concurrent calls | scale out |
| Dify, Plane | 2 vCPU / 4 GB | 4 vCPU / 8 GB |

## Steps (Ubuntu 24.04 LTS)

```bash
# 1. Non-root sudo user + SSH keys only
adduser ops && usermod -aG sudo ops
# copy your key to /home/ops/.ssh/authorized_keys, then in /etc/ssh/sshd_config:
#   PermitRootLogin no
#   PasswordAuthentication no
systemctl restart ssh

# 2. Updates + firewall
apt update && apt -y upgrade && apt -y install ufw unattended-upgrades fail2ban
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable
dpkg-reconfigure -plow unattended-upgrades

# 3. Docker (official script)
curl -fsSL https://get.docker.com | sh
usermod -aG docker ops
```

**Docker bypasses ufw for published ports.** In compose files, bind app ports to localhost (`"127.0.0.1:8080:8080"`) and let Caddy be the only thing on 80/443.

## HTTPS with Caddy

```bash
apt -y install caddy
cat >/etc/caddy/Caddyfile <<'EOF'
app.clientdomain.com {
    reverse_proxy 127.0.0.1:8080
}
EOF
systemctl reload caddy
```

Point an A record at the server first. Caddy fetches and renews the certificate itself.

## Backups (not optional)

A backup that only lives on the same VPS isn't a backup. Use restic to S3-compatible storage (Backblaze B2, Wasabi, R2):

```bash
apt -y install restic
export RESTIC_REPOSITORY=s3:https://<endpoint>/<bucket>/<client>
export RESTIC_PASSWORD=...   # store in your password manager
restic init
```

Nightly cron: `pg_dump` each Postgres container to `/srv/backups`, then `restic backup /srv/backups /srv/<app>`, then `restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune`.

**Test a restore before you invoice.** Restore onto a scratch VPS once per client and write down how long it took.

## Monitoring

- Uptime: UptimeRobot or Better Stack checking the HTTPS URL every 1-5 minutes, with alerts to you, not the client.
- Disk: alert at 80%. Docker images and logs fill disks quietly. Set `"log-opts": {"max-size": "10m", "max-file": "3"}` in `/etc/docker/daemon.json`.

## Update routine (what the retainer pays for)

Monthly, or sooner for security releases:
1. Read the upstream release notes for breaking changes and migrations.
2. Back up and confirm the backup ran.
3. Pin the new version tag, then run `docker compose pull && docker compose up -d`.
4. Smoke-test the client's real workflow, not just the login page.
5. Log the date, the old and new versions, and the result in the client's runbook.

Never run `:latest` in production. Pin versions so updates happen when you choose to make them.

## Client handover doc (per client)

Record the server IP and provider, domains and DNS host, where the credentials live, which API keys are billed to whom, where backups go, how to restore, and the version currently running.
