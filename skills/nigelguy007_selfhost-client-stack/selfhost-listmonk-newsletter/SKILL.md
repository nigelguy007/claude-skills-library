---
name: selfhost-listmonk-newsletter
description: Move a client off Mailchimp onto self-hosted Listmonk with a proper sending service - Docker deploy, SMTP (SES/Postmark/etc.), SPF/DKIM/DMARC, list import with consent, IP/domain warmup, bounce handling. Use when the user says "Listmonk", "leave Mailchimp", "self-hosted newsletter", "email deliverability setup", or "deploy Listmonk for a client".
---

# Listmonk newsletter (off Mailchimp)

Listmonk (github.com/knadh/listmonk, AGPL-3.0) is a single Go binary plus Postgres. **It doesn't deliver email itself.** It hands mail to an SMTP or API sending service. Deliverability is the actual job.

Run `selfhost-vps-base` first.

## Deploy

```bash
mkdir -p /srv/listmonk && cd /srv/listmonk
curl -LO https://github.com/knadh/listmonk/raw/master/docker-compose.yml
# edit: pin the image tag (not :latest), change the default DB password,
#       bind the app port to 127.0.0.1:9000
LISTMONK_ADMIN_USER=admin LISTMONK_ADMIN_PASSWORD='<strong>' docker compose up -d
```

Put Caddy in front at `https://news.clientdomain.com`. In Settings, set the Root URL to that address so unsubscribe and tracking links work.

## Sending service

Pick one and add it under Settings -> SMTP: Amazon SES (cheapest at volume, sandbox approval required), Postmark (broadcast stream), Mailgun, Brevo, or similar. **Do not send bulk mail from the VPS's own IP.**

## DNS: on the client's domain (use a subdomain such as `news.brand.com` or `mail.brand.com`)

- **SPF:** include the sender's SPF record.
- **DKIM:** the CNAME or TXT records the sending service gives you.
- **DMARC:** start at `p=none` with a `rua` report address, then move to `quarantine` once reports are clean.
- **Custom return-path / MAIL FROM** domain if the sender supports it.
- Gmail and Yahoo bulk-sender rules (in force since 2024) require SPF + DKIM + DMARC, **one-click unsubscribe** (`List-Unsubscribe` + `List-Unsubscribe-Post`), and spam complaints under 0.3%. Confirm Listmonk's headers in a test send to Gmail via "Show original".

## Migrating the list

1. Export from Mailchimp **with consent status**. Import only subscribed contacts. Never import unsubscribed, cleaned or bounced contacts.
2. Keep merge fields as subscriber attributes (JSON).
3. Run the export through a verifier (ZeroBounce, NeverBounce and similar) if the list hasn't been mailed in a while.
4. Recreate the signup form (Listmonk public forms or the API) with double opt-in.

## Warmup

A new domain or sender reputation sending to 50k on day one gets you junked. Ramp up over 2-4 weeks: start with the most engaged segment (opened in the last 30-60 days) at a few hundred to a few thousand a day, roughly double daily while bounces stay under 2% and complaints under 0.1%, then widen to less-engaged segments.

## Bounces and complaints

Enable bounce processing in Listmonk (a webhook from SES/SNS, Postmark and others, or a POP mailbox) and set it to blocklist hard bounces. Without this, reputation decays silently.

## The Mailchimp comparison, done honestly

Total your cost: VPS + sending service at their volume + your retainer. Compare that with their current Mailchimp tier. Below roughly 5-10k contacts the saving can be small or negative once your retainer is included. The pitch gets strong on large lists. Run the numbers per client and don't promise savings up front.

## Retainer scope

Listmonk upgrades (take a DB backup first; the container runs `--upgrade`), a monthly deliverability check (DMARC reports, bounce and complaint rates, blocklist check), template tweaks, and list hygiene.
