# Fundraising Intelligence skill pack

Twenty-one focused Claude-compatible Agent Skills for running an evidence-led venture raise: define the round, build a qualified fund universe, verify actual investment behavior, find the right partner, and manage outreach through diligence and close.

Start with `fundraise-run`. It coordinates the other twenty skills, but every specialist can also run independently.

The pack deliberately produces a smaller qualified target list instead of a scraped directory. It separates sourced facts, reasoned inferences, and unknowns; keeps evidence dates and URLs; and never infers private contact details, signing authority, or investment intent.

## Included skills

| Phase | Skills |
| --- | --- |
| Position | `round-definition`, `fundraising-narrative`, `evidence-room-audit`, `investor-fit-thesis` |
| Map | `fund-universe-builder`, `fund-mandate-verifier`, `cheque-fit-analyzer`, `fund-behavior-profiler`, `portfolio-conflict-check`, `partner-fit-mapper`, `warm-path-mapper` |
| Engage | `outreach-sequencer`, `intro-request-writer`, `vc-outreach-writer`, `investor-meeting-brief`, `partner-question-builder` |
| Run | `fundraising-crm-review`, `term-sheet-comparator`, `diligence-room-manager`, `fundraising-close-plan` |
| Coordinate | `fundraise-run` |

## Method sources

- Official fund websites, team biographies, portfolio pages, fund-close announcements, and founder/company announcements are the primary evidence for mandate, partner ownership, cheque patterns, and recent activity.
- SEC Investment Adviser Public Disclosure and Form ADV data: https://adviserinfo.sec.gov/ and https://www.sec.gov/foia-services/frequently-requested-documents/form-adv-data
- SEC EDGAR company and filing search: https://www.sec.gov/edgar/search/
- UK Companies House register guidance: https://www.gov.uk/guidance/searching-the-companies-house-register
- NVCA model venture-financing documents: https://nvca.org/model-legal-documents/
- Y Combinator's seed fundraising guide: https://www.ycombinator.com/library/4A-a-guide-to-seed-fundraising
- OpenAI Skills API: https://developers.openai.com/api/reference/resources/skills

These sources support a research method, not a prediction that a fund will invest. Regulatory registers identify firms and filings; they do not prove current appetite or partner interest. Legal documents are starting points, not legal advice.

## License

MIT. See `LICENSE`.
