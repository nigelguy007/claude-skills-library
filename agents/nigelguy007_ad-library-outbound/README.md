# ad-library-outbound

Four subagents that sell to companies already paying for ads, plus the `ad-library-outbound` skill
that runs them (`skills/nigelguy007_ad-library-outbound/ad-library-outbound`). Built from the
"sell to companies that already pay for ads" LinkedIn Ad Library guide, then corrected against live
ad-library data.

| Agent | Guide step | Produces |
|---|---|---|
| `ad-library-scout` | 1. Find them | Pulls ads by keyword, country and date from the LinkedIn or Meta ad library and ranks the advertisers |
| `ad-lead-qualifier` | 2. Pick the best | Judges fit, proves the company is the one that ran the ad, sizes it, picks the exact ad line, names the right person |
| `ad-outreach-writer` | 3. Write the email | The 2-line email that quotes the ad, follow-ups, a LinkedIn note and, on request, the eight other plays |
| `outreach-test-analyst` | 4. Send and test | Builds the send sheet, plans the test, reads the replies and says what the numbers support |

Install (skills first, the agents call its scripts):

```bash
./install.sh --source nigelguy007_ad-library-outbound
./install.sh --agents --source nigelguy007_ad-library-outbound
```

Then run `/ad-library-outbound` in Claude Code. The orchestrator is a skill, not an agent, because
subagents can't start other subagents.

Needs a [Scrape Creators](https://scrapecreators.com) API key in `SCRAPECREATORS_API_KEY` (one credit
per page of ads). In a Claude cloud session with that service connected, no key is needed. Without
either, the scout works from ad links and text you paste into the run's `inbox/`.

Ground rules built into every agent:
- Nothing is sent, posted or connected. The output is a CSV for your sending tool and text for you
  to send by hand.
- The quoted ad line is word for word from the ad that was pulled. A script checks it.
- No invented names, titles, emails, numbers or results. Every fact about a prospect has a source
  link or is left blank.
- A company is only emailed when it is proven to be the one that ran the ad. Two companies can share
  a name.
- A lead is only put on a send sheet when you have approved its draft (`batch.py approve` records it), and an edit after that cancels the approval.
- Opt-outs and bounces go on a never-contact list that fails closed: a list that cannot be read stops the batch instead of passing as empty.
