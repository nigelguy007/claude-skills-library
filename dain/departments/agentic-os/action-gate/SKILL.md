---
name: dain-action-gate
description: The only path to the outside world. Publishes an approved post or sends an approved reply only with a single-use approval token bound to the exact content hash, at most once per idempotency key, reconciling with the external system after a crash. Use for every publish, send or share.
component: AG
department: agentic-os
archetype: publisher
owner: TL
---

# Action Gate + publishers

## Purpose
- **Role:** the map's Publisher, built as code with a human on the trigger.
- **Goal:** an approved post cannot be published twice, published after edits, or published without a named human.
- **Success:** 0 external actions without a valid token; 0 duplicates in the chaos test.

## 1 · Name and trigger
Called by C0 after `review.approve` returns a token (content → LinkedIn; enquiry → email).

## 2 · When to use
Every external write. Nothing else may hold LinkedIn or email credentials.

## 3 · Inputs
Item id, the exact content, token id, idempotency key (`publish:<item>` or `send:<enquiry>`).

## 4 · Steps
1. Validate the token: right item, not voided, not expired (72 h), content hash matches.
2. Mark the token used and record the intent (`pending`) **before** calling out.
3. Call the adapter. Record the result (`done`).
4. On retry: `done` returns the stored result. `pending` asks the adapter's `findExisting(key)` whether the action already happened; if the adapter has no lookup, stop and escalate rather than risk a duplicate.

## 5 · Handoffs
`action.executed` event; C0 moves the item to PUBLISHED / SENT; the published text becomes a voice sample.

## Rules
- Any edit after approval voids the token. A newer approval supersedes an older one.
- The LinkedIn adapter must implement `findExisting` (list the member's recent posts and match a hash marker); otherwise every crash mid-publish becomes a human check.

## Tools
LinkedIn Posts API (`w_member_social`); transactional email. Confirm current LinkedIn scopes before the build.

## Test
`tests/gate.test.ts`: wrong hash, expiry, reuse, voiding by edit, and 20 injected crashes with zero duplicates.

## Workflows and autonomy
Publishing and sending can never be promoted to fully autonomous: the speaker approves everything that goes out in their name.

| Workflow | Autonomy | Writes outside Dain |
|---|---|---|
| Publish an approved post | human-assisted | yes |
| Send an approved reply | human-assisted | yes |
