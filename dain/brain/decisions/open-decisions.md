# Open decisions

From Sheet 08 of the spec, plus what came up while building. Each has a default so the build doesn't wait.

| Decision | Default used in the build | Needed by |
|---|---|---|
| Who runs the booker interviews; will bureau partners introduce bookers? | Product lead; 3 partner bureaus × 2 introductions | Day 1 |
| Accept notification-forward + paste/share as the LinkedIn route, and change the copy? | Yes. P1 never reads a LinkedIn inbox | Day 3 |
| Internal booking board or each speaker's CRM? | Internal board for the pilot | Day 3 |
| Pilot segment (R11) | £5k–£15k, 10+ paid talks, ≥ 1 bureau, speaking is main income, goal = more bookings (`screen()` in `src/conductor/commands.ts`) | Day 3 |
| Market capabilities instead of "nine agents"? | Yes in customer materials | Day 5 |
| Referral model and consent wording | Goodwill in the pilot; wording in `canon/referral-consent.md` awaiting legal | Day 14 |
| Confirm R10 thresholds (support ≥ 50%, partial 25–49%, reject < 25%) | Accepted as proposed | Day 15 |
| Allow risk-based specialist review after week 4? | Built but **off** until approved (`specialistMustReview`) | Day 25 |
| One named specialist for the pilot, logging review time | Required for the R8 cap | Day 1 |

## Raised during the build
1. **Onboarding cap: 65, not 81.** F8 says one specialist covers about 81 speakers (30 h ÷ 22 min). R8's formula reserves 20% for escalations and onboarding, which gives 65. Use 65 for planning until measured minutes replace the 22-minute assumption; at 10 min/post it falls to about 36, not 45.
2. **The spec's v1 LLM list omits P2's cover-note prompt.** Built as a template instead, keeping five LLM components.
3. **The deck's "Jarvis-style" conductor promise.** If sales material shows a chat-style conductor, it must not imply an LLM decides what gets published. C0 is fixed routes.
4. **LinkedIn publish reconciliation.** The Action Gate needs the LinkedIn adapter to find an existing post by idempotency marker after a crash; otherwise every mid-publish crash becomes a manual check. Confirm what the current Posts API allows before Day 10.
5. **Model prices.** Cost per approved post uses placeholder prices (`DAIN_GBP_PER_MTOK_IN/OUT`). Set real ones before reading that dashboard number.
