---
# What you sell, in one plain line. This is the line the writer builds every email from.
sell:
# One of: lead-gen, design-video, web-landing, seo-content, automation-ai, sales-help, other
angle:
# Countries you will email, 2-letter codes. Start with US. Other countries have stricter rules:
# read references/sending-rules.md before you add one.
countries: US

# Who the email is from. All of this goes under every email, so it must be true.
sender_name:
sender_company:
# A real postal address where you can receive mail. US law requires one in every commercial email.
postal_address:
# One plain sentence that tells people how to make you stop.
opt_out_line: Not relevant? Reply "no" and I won't email again.

# The domain you send cold email from, and your everyday domain. They should differ:
# if cold email hurts the sending domain's reputation, your everyday mail keeps working.
sending_domain:
main_domain:

# Limits. Change them only if you have a reason.
max_words: 35
# At or below this many employees, write to the founder. Above it, the head of marketing or sales.
founder_led_max: 50
# Above this many employees the company is skipped as too big to reach cold.
max_employees: 500
---

## Who buys
<!-- Who is the buyer? Industry, company size, the role who says yes, the problem they have when they
     are ready to buy. Two or three lines. The qualifier judges every advertiser against this. -->

## Who never to contact
<!-- Competitors, current customers, anyone who asked you to stop. Names or domains, one per line.
     Add the domains to suppression.csv too: `batch.py suppress --value rival.com --reason competitor`. -->

## Proof I can back up
<!-- Every number and claim the emails are allowed to use, and what you can actually deliver.
     Example: "50 free verified emails as a sample", "delivered in 48 hours", "12 clients in SaaS".
     If it is not written here or in the prospect's own ad, the writer may not say it. -->

## Never say
<!-- Promises you cannot keep, guarantees, anything about results you have not produced. -->

## Search words
<!-- Words to search the ad library with. Prefer the industry you sell TO, or the words your buyers
     use in their own ads. Searching for what YOU sell mostly finds your competitors. -->
