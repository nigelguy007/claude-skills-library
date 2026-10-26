---
name: selfhost-nocodb-app
description: Turn a client's messy spreadsheets into a database-backed app with NocoDB (views, forms, permissions) on Postgres - licence check, Docker deploy, data migration, handover. Use when the user says "NocoDB", "Airtable alternative", "spreadsheets into an app", or "deploy NocoDB for a client".
---

# NocoDB: spreadsheets into an app

Run `selfhost-vps-base` first.

## Licence: stop and read this first

**From 9 January 2026, NocoDB moved from AGPL-3.0 to a Sustainable Use License (SUL).** Per nocodb.com/docs/self-hosting/license, you need a **commercial licence** if you:
- offer NocoDB as a hosted or managed service,
- provide direct NocoDB access to external customers, or
- resell or redistribute it as part of a paid offering.

"I host NocoDB for you for $X/month" falls squarely in that. Options:
1. **The client self-hosts on their own account and pays NocoDB for any licence needed.** You bill only for consulting and setup labour. Confirm with NocoDB that this structure is covered.
2. **Buy a NocoDB commercial or self-hosted licence** and build its cost into your price.
3. **Use a permissively licensed alternative** for the managed-hosting model, such as Baserow (check its current licence) or Teable, and re-check that licence too.

Do not deploy a paid managed-hosting NocoDB setup without settling this. Re-read the licence page at deploy time, because it may change again.

## Deploy (Postgres, not SQLite)

```yaml
# /srv/nocodb/docker-compose.yml
services:
  nocodb:
    image: nocodb/nocodb:<pinned-version>
    restart: unless-stopped
    ports: ["127.0.0.1:8080:8080"]
    environment:
      NC_DB: "pg://db:5432?u=nocodb&p=${PG_PASS}&d=nocodb"
      NC_AUTH_JWT_SECRET: "${JWT_SECRET}"
      NC_PUBLIC_URL: "https://app.clientdomain.com"
      NC_DISABLE_TELE: "true"
    volumes: ["./data:/usr/app/data"]
    depends_on: [db]
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: nocodb
      POSTGRES_PASSWORD: "${PG_PASS}"
      POSTGRES_DB: nocodb
    volumes: ["./pg:/var/lib/postgresql/data"]
```

Check the NocoDB docs for the current environment variable names before deploying.

## Migration: this is where the setup fee goes

1. **Audit the sheets:** which columns are really the same entity (candidates, properties, clients)? Find the merged cells, the free-text "status" columns, and the duplicate rows.
2. **Design tables and links** before importing. Put a link field where people currently copy and paste names between tabs.
3. **Clean in a copy:** dedupe, normalise dates, phone numbers and status values into single-selects.
4. **Import** with NocoDB's CSV or Excel import, or Airtable import if they're coming from Airtable.
5. **Build what they'll actually use:** filtered views per role, forms for intake, and a kanban for pipeline stages.
6. **Permissions:** give each person their own account and the lowest role that works. No shared logins.
7. **Run parallel for 1-2 weeks,** then freeze the old sheet as read-only.

## Handover

- Write a one-page "how to add a candidate / property / deal" guide with screenshots.
- Back up Postgres nightly (see base skill) and test the restore.
- Retainer scope: new views, fields and automations; upgrades; user admin.
