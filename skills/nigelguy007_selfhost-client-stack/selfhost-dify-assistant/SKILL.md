---
name: selfhost-dify-assistant
description: Self-host Dify for one client and build a front-desk FAQ chatbot trained on their documents (dental, medical, law firm, clinic) - Docker deploy, knowledge base, website embed, guardrails, updates. Use when the user says "Dify", "chatbot trained on their docs", "front-desk assistant", "RAG bot for a clinic/law firm", or "deploy Dify for a client".
---

# Dify front-desk assistant

Dify (github.com/langgenius/dify) is an LLM app platform with a UI: knowledge bases (RAG), chatflows, and embeddable web chat.

Run `selfhost-vps-base` first. Needs at least 2 vCPU / 4 GB.

## Licence: read before selling

Dify uses a **modified Apache 2.0** licence with two extra conditions:
1. **No multi-tenant use** without written permission from Dify. Run **one Dify instance per client**, not one shared instance with a workspace per client.
2. **Don't remove or modify the Dify logo or copyright** in the console or apps.

Re-read `LICENSE` in the repo at the version you deploy.

## Deploy

```bash
git clone https://github.com/langgenius/dify.git
cd dify && git checkout <latest-release-tag>   # pin it; check GitHub releases
cd docker
cp .env.example .env
# edit .env: SECRET_KEY (openssl rand -base64 42), and the URL vars (CONSOLE_*_URL / APP_*_URL / SERVICE_API_URL) to https://bot.clientdomain.com
# set EXPOSE_NGINX_PORT=127.0.0.1:8080 or similar so only Caddy is public
docker compose up -d
```

Open `https://bot.clientdomain.com/install` and create the admin account straight away. An un-claimed install page is an open door.

## Build the assistant

1. **Model provider:** add the client's own API key (OpenAI, Anthropic, Azure and others). Use a small, fast model for FAQ answers.
2. **Knowledge base:** upload hours, services, pricing ranges, insurance accepted, booking policy, location and parking, and new-patient forms. Clean the documents first, because bad source docs produce confident wrong answers. Use one topic per document where possible.
3. **Chatflow:** retrieval -> LLM, with a system prompt that says to answer only from the knowledge base, say "I'll have the team get back to you" when unsure, never give medical or legal advice, and hand off to a human through a contact form or phone number.
4. **Embed:** use Dify's "Embed in website" script on the client's site.
5. **Test set:** 30-50 real questions from the front desk, including ones the bot should refuse. Re-run them after every knowledge or model change.

**"On their phone line"**: Dify is chat-first. Voice needs a telephony layer in front, such as the `selfhost-pipecat-receptionist` skill calling Dify's API. Don't promise phone answering from Dify alone.

## Health data and legal data

- A **dental or medical** bot that collects symptoms, names plus appointments, or insurance details is handling PHI. Under HIPAA you would need a BAA with every vendor in the chain: the LLM provider, the VPS host and you. Most budget VPS hosts won't sign one.
  **Safest scope: FAQ-only, no PHI collected.** Booking goes to their existing compliant scheduler via a link.
- **Law firms:** add a "not legal advice; no attorney-client relationship" disclaimer, and don't take case facts through the bot.
- Outside the US, apply the local equivalent (GDPR, PIPEDA and so on).

## Maintenance (the retainer)

- Dify releases often. Before upgrading, back up `docker/volumes/`, read the release notes, diff `.env.example` against your `.env` for new variables, then `docker compose down && docker compose pull && docker compose up -d`.
- Re-run the test set after each upgrade.
- Monthly: update the knowledge base when their prices, hours or staff change, and review logs for unanswered questions. Those questions become new knowledge-base content.
