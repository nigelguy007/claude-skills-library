# Sending rules

This is a working checklist, not legal advice. Rules change; check the current law for any country
you email before the first send.

## Before the first email

- **Send from a second domain**, not your everyday one (`getyourbrand.com` beside `yourbrand.com`).
  The point is to protect your everyday mail if the sending domain's reputation drops. It is not a
  way to hide who you are: the email still names you, your company and your address.
- **Set up SPF, DKIM and DMARC** on the sending domain. Gmail and Yahoo reject or junk mail from
  domains without them.
- **Warm the inbox up.** A new inbox that sends 50 cold emails on day one goes to spam. A common
  ramp, per inbox: 5 a day in week one, 10 in week two, 20 in week three, and stay under 30-50 a day
  after that. These are rules of thumb. Your sending tool's own warm-up settings come first.
- **Verify addresses before sending.** A bounce rate above about 5% damages the domain.
  `batch.py stats` raises an alarm at that level.
- **Read every email.** `batch.py build` only includes drafts approved with `batch.py approve`, and an edit to the draft or to the address after that cancels the approval.

## What every email must carry

`batch.py build` adds these under the two lines and refuses to build if `offer.md` lacks them.

- Who it is from: your real name and company. No fake names, no "Re:" on a first email.
- A real postal address where you can receive mail.
- A plain way to say no, and you must honour it. `batch.py record --event optout` puts the address
  on the suppression list at once, and nothing on that list is ever put on a send sheet again. A
  suppressed domain covers its subdomains. The list does not catch the same person writing from a
  different address or a `+tag` variant: suppress those too when you see them.

## By country

| Country | Cold B2B email | What that means here |
|---|---|---|
| United States | Allowed under CAN-SPAM, which covers business email too. | Truthful sender and subject, a postal address, a working opt-out honoured within 10 business days, and the message must not hide that it is a solicitation. Penalties are per email. |
| Canada | CASL needs consent, express or implied. | Implied consent can come from an address the person published without a "no solicitation" note, if the email is relevant to their role. Record where you found the address. |
| United Kingdom | Limited companies and LLPs can be emailed without prior consent. Sole traders and most partnerships cannot. | Check what kind of business it is. Data protection law still applies to a named person: say who you are and stop when asked. |
| EU | Set country by country. Several, Germany among them, require prior consent even for business addresses. | Do not add an EU country to `offer.md` until you have checked that country's rule. |
| Australia | The Spam Act needs consent, express or inferred. | Inferred consent can come from a published business address relevant to the person's role. |

`offer.md` lists the countries you will email (`countries: US` by default). A lead whose country is
not on that list, or is unknown, is left off the send sheet.

## LinkedIn

Connection notes, messages and comments are written for you to send by hand. Software that sends
them for you breaks LinkedIn's terms and gets accounts restricted.

## Testing

- **Count replies, not opens.** Open tracking is unreliable and adds a tracking pixel that hurts
  delivery.
- **One change at a time.** Email B may differ from Email A in one line only. The lint enforces it.
- **Split inside the batch, not between batches.** `batch.py build` sends half the batch version A
  and half version B, so both go to the same kind of company in the same week. Comparing this
  week's batch with last week's compares two lists and two weeks, not two emails.
- **A 20-30 email batch cannot pick a winner.** At a typical 2-5% reply rate that is 0-1 replies per
  version. `batch.py stats` will not name a leader until each version has at least 50 sends and the
  gap is unlikely to be chance. Keep the test running across batches. A leader named after one look
  still has to hold on the next batch: checking after every batch makes a false winner more likely.
- **Follow up once or twice**, a few days apart, one line each. Then stop.
- **Positive replies are the real score.** "Not interested" and "remove me" are replies too. Log a
  good one with `--event positive`.
