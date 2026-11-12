# Ways to open, beyond the 2-line email

Every play starts from the same lead file: a company that is paying for ads, the exact line from
its ad, and a named person. The writer adds a play to a draft only when the brief asks for it, as
its own `## Section`. All of them are written for the user to send or post by hand.

## Pick the angle from what you sell

Use the row that matches `angle` in `offer.md`. These are starting points for line one, not text to
paste. The claim in each row is only usable when the note beside it is true for this prospect.

| You sell (`angle`) | Open with | Only if |
|---|---|---|
| Lead lists or lead gen (`lead-gen`) | Their ad reaches people scrolling; you can put them in front of buyers who need this now. | You can name who those buyers are for this company. |
| Design or video (`design-video`) | The offer is strong but the creative buries it; here is a version that puts it first. | You looked at the ad creative, not just its text. |
| Websites or landing pages (`web-landing`) | The page the ad sends people to loses clicks they paid for. | You opened the page and can say what you saw. A speed claim needs a measurement. |
| SEO or content (`seo-content`) | Ads stop the day they stop paying; content keeps bringing people in. | Always true, so make line two specific to them. |
| Automation or AI (`automation-ai`) | They pay for every click. How fast does a new lead get a reply? | Ask it as a question. You do not know their reply time. |
| Sales help (`sales-help`) | Ads bring the leads; you turn them into booked calls. | The ad asks for a demo, call or form fill. |

Do not knock the thing they are paying for. "Great offer, but ads reach browsers, not buyers" tells
a founder their spend is wasted in the first line. Point at what the ad leaves unsolved.

## The eight plays

### 1. LinkedIn note (`## LinkedIn note`)
A connection note that mentions the ad and asks permission to share one idea.
- Free accounts get 200 characters and a small number of notes a month; paid accounts get 300.
  Write for 200.
- No pitch in the note. The pitch comes after they accept.
- The user sends it by hand. Tools that send connection requests for you break LinkedIn's terms
  and get accounts restricted.

### 2. Free mini-review of their ad (`## Ad review`)
Three specific ideas to make the ad work better: a clearer offer, a stronger number, a better
button. Give before you ask.
- Format: three numbered ideas, one or two sentences each, written as the user would say them. Start with one line saying what you looked at.
- Each idea must point at something in the ad text you were given. No generic advice.
- If you have only the ad's text (LinkedIn gives no image through the API), review the words and
  say so. Do not comment on a creative you have not seen.

### 3. A 60-second video (`## Video script`)
A script for the user to record their screen on the ad and the website.
- About 130 words. Say their name and company in the first five seconds, show the ad, give one
  idea, ask one question.
- List what should be on screen at each beat.

### 4. Fix what happens after the click (`## After the click`)
The ad sends people to a page, a form or a demo. If that step is slow or confusing, ad money is
wasted.
- LinkedIn does not return the landing-page link for US ads. Use the link from the ad's public
  page if it can be read, otherwise the company's home page, and say which one you looked at.
- Meta ads do carry the link (`destination_url` in the ad record).
- Report only what you saw on the page. "Loads slowly on a phone" needs a measured number.

### 5. Offer to follow up their leads (`## Lead follow-up offer`)
Ads bring in leads and many companies answer them late. Offer to reply, book calls or nurture.
- Ask how fast leads get a reply. Do not assert that they are slow.

### 6. Pay only when it works (`## Pay-per-result offer`)
Price per booked call or per lead, so the risk sits with you.
- Only if `offer.md` says the user sells this way. Never invent a price.

### 7. Comment before you pitch (`## Comment plan`)
A five-day plan: follow the company and the founder, leave one useful comment a day on their
posts, then send the note.
- List which posts (with links) if you can read them. Otherwise give the kind of comment to leave.
- A comment adds something: a number, a counter-example, a question. Never "Great post".

### 8. Partner instead of selling (`## Partner pitch`)
If the user's product sits next to theirs, propose a referral or joint offer.
- Only when the fit is real: say in one line why their customers need the user's product.

## Same trick, more places

- **Meta Ad Library** (Facebook and Instagram): better for businesses that sell to consumers.
  `adlib.py search --library meta` pulls it. Meta gives start dates, landing-page links and how many
  copies of an ad are running, so the scout can also see who has been spending for months.
- **Google Ads Transparency Center**: no keyword search, only lookup by advertiser or domain.
  `adlib.py presence --name ... --domain ...` checks a known company.
- **Hiring ads**: a company paying to hire is growing. The scorer tags ads that are job adverts
  (`hiring`). There is no separate jobs library in the API this pack uses.

A company found in two or three of these places usually has a real marketing budget. Record it in
the lead file under `also_on`, and only when a check confirmed it. A page with a similar name is
not a confirmation.
