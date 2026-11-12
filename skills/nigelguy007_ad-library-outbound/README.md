# ad-library-outbound

One skill, `ad-library-outbound`, that runs the four subagents in
`agents/nigelguy007_ad-library-outbound` to sell to companies that already pay for ads: find them in
the LinkedIn or Meta Ad Library, pick the best, write a 2-line email that quotes their own ad, then
build a send sheet and read the replies.

```
ad-library-outbound/
  SKILL.md                 the orchestrator (/ad-library-outbound)
  scripts/                 adlib.py, score.py, lint_draft.py, batch.py (Python 3.8+, standard library only)
  templates/               offer.md, lead.md, draft.md
  references/              plays.md (the other eight plays), sending-rules.md
tests/                     pytest/unittest suite for the scripts (not installed)
```

Install:

```bash
./install.sh --source nigelguy007_ad-library-outbound
./install.sh --agents --source nigelguy007_ad-library-outbound
```

`adlib.py` calls the [Scrape Creators](https://scrapecreators.com) API (`SCRAPECREATORS_API_KEY`), one
credit per page of ads. Nothing in this pack sends email or messages.

Run the tests:

```bash
python3 -m pytest skills/nigelguy007_ad-library-outbound/tests -q -p no:cacheprovider
# or, without pytest:
python3 -m unittest discover -s skills/nigelguy007_ad-library-outbound/tests
```
