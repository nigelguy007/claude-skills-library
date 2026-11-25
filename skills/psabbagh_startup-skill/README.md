# startup-skill

Test your startup idea in Claude before you spend a dollar on it. Free, MIT, no
signup, no API key, nothing to connect.

Seven Claude skills that work together:

- **A board of eight advisors** that scores your idea using the playbooks of Alex
  Hormozi, Naval Ravikant, Paul Graham, Peter Thiel, Seth Godin, Lenny Rachitsky and
  Tobi Lütke, each advisor voting fund, fund if, or pass.
- **Your real competitors**, researched on the web with a link for every fact: who
  already solves the problem, what they charge, what their own customers complain
  about, and the gap nobody fills.
- **100 simulated buyers** drawn from your target customer, each with their own
  budget, habits, doubts and current way of doing things. They tell you who would pay
  now, why the rest won't, what would change their mind, and the price range they
  would accept. When they say no, it turns their objections into a better offer and
  tests it on the same buyers.
- **Where your customers will come from**: two or three channels, every step from
  reaching someone to getting paid, what it costs and how much of your time it takes,
  turned into a forecast of new customers per month.
- **The numbers**: what each sale or customer leaves you, what it costs to win a
  customer, break-even, the cash you need, and when your money comes back. Works for
  subscriptions and one-off sales.
- **A business plan with one verdict**, computed from the numbers, never written by
  hand: Profitable, or Not yet.

## Why I made this

I built a B2B SaaS company, and it took me over a year to find out what customers
would actually pay for. We built a mobile app before we knew how hard it would be. We
were early in AI and thought customers would pay for the AI, when what they pay for is
one problem fixed. This pack looks for those holes before you spend the money. The
board's chair always answers five questions I wish someone had asked me on day one.

## Install

Paste this link into Claude and say `install skill`:

```
https://github.com/psabbagh/startup-skill

install skill
```

It runs in **Claude Code** (the Code tab of the Claude desktop app, or `claude` in a
terminal) and in **Codex** (the Codex app or the `codex` command). The skills are
free; Claude Code needs a paid Claude plan and Codex a ChatGPT plan that includes
it. The number tools need Python 3.8 or newer, and nothing else.

### For Claude: how to install

Copy the seven `startup-*` folders into the user's personal skills folder, so the
commands work in every project:

```bash
git clone --depth 1 https://github.com/psabbagh/startup-skill.git /tmp/startup-skill-install
mkdir -p ~/.claude/skills
cp -R /tmp/startup-skill-install/startup-* ~/.claude/skills/
rm -rf /tmp/startup-skill-install
python3 --version
```

On Windows, copy the same seven folders into `%USERPROFILE%\.claude\skills\`. Then
tell the user to type `/startup-skill` followed by their idea. If the commands do
not show up, they should start a new session.

### For Codex: how to install

Same folders, into Codex's skills folder:

```bash
git clone --depth 1 https://github.com/psabbagh/startup-skill.git /tmp/startup-skill-install
mkdir -p ~/.codex/skills
cp -R /tmp/startup-skill-install/startup-* ~/.codex/skills/
rm -rf /tmp/startup-skill-install
python3 --version
```

The board and the buyers run as separate agents, which in Codex needs its
multi-agent feature. If it is not already on, add this to `~/.codex/config.toml`:

```toml
[features]
multi_agent = true
```

Then tell the user to start a new Codex session and type `$startup-skill` followed by
their idea.

## Use it

Open Claude Code or Codex in any folder (a new, empty one is fine) and type your
idea. In Claude Code:

```
/startup-skill a booking app for hair salons, $29 a month
```

In Codex, skills start with `$` instead of `/`:

```
$startup-skill a booking app for hair salons, $29 a month
```

It runs the six steps in order, asks you for what only you know, and ends with the
verdict. Add `--quick` for 20 buyers instead of 100 on a first try. The buyer step
runs one sub-agent per buyer, so it is the longest and uses the most of your plan.
Each buyer writes one small file, so let it write without asking first: in Claude
Code, switch to accept-edits mode (Shift+Tab) before it starts; in Codex, start with
`codex --full-auto` or choose the auto approval mode.

Or run any step on its own (in Codex, type `$` instead of `/`):

| command | what it does |
| --- | --- |
| `/startup-skill` | Runs everything below, in order. |
| `/startup-board` | The board of advisors scores the idea, names what would kill it and the assumption it rests on, and votes. |
| `/startup-competitors` | Researches the real alternatives on the web, with a link and a date for every fact: prices, headlines, what their customers complain about, and the gap. Needs web search (in Codex, `codex --search`). |
| `/startup-buyers` | 100 simulated buyers (20 with `--quick`) see your pitch and say whether they would pay now, and why. Then it can turn their objections into a better offer and re-test it on the same buyers. |
| `/startup-marketing` | Plans where the first customers come from: the first audience, two or three channels with every step from reached to paid, the first 30 days, and messages that answer the buyers' objections. Turns it into new customers per month and the cost to win each. |
| `/startup-numbers` | Margins, the cost of winning a customer, break-even, 24 months month by month, cash needed, payback, and what-ifs. |
| `/startup-plan` | The business plan, the verdict, and the cheapest real-world test to run next. |

Everything is written to a `startup/` folder in your project. The steps read each
other's files.

## The board

Each advisor is a separate sub-agent applying one published playbook, so they judge
your idea independently before the chair sums up.

| advisor | the playbook it applies |
| --- | --- |
| Offer | *$100M Offers*, Alex Hormozi |
| Leads | *$100M Leads*, Alex Hormozi |
| Monopoly | *Zero to One*, Peter Thiel with Blake Masters |
| Marketing | *This Is Marketing* and *Purple Cow*, Seth Godin |
| Leverage | *How to Get Rich (without getting lucky)* and *The Almanack of Naval Ravikant* |
| AI-native | *Reflexive AI usage is now a baseline expectation at Shopify*, Tobi Lütke's 2025 memo |
| Traction | *Lenny's Newsletter*, Lenny Rachitsky |
| Startup | *How to Get Startup Ideas*, *Do Things That Don't Scale* and other essays, Paul Graham |

The chair then answers five questions every founder should face: what one problem it
fixes, whether you are building the expensive version first, how the first ten
customers find you, how many habits a customer has to change, and whether demand comes
from many customers or just one.

## What "Profitable" means

The verdict is Profitable only when every check passes:

1. Each sale, or each customer each month, leaves money after its own costs.
2. For subscriptions, a customer brings in more than it costs to win them.
3. By month 12, the business makes money every month.
4. The money you put in (startup spend plus the early losses) comes back within 24
   months.
5. Break-even fits within what you can handle, if you gave a capacity.
6. At least 20% of the simulated buyers would pay now (or, if your offer starts with
   a free trial, would start it today and expect to pay after it).
7. The buyers were shown the same price the numbers use.
8. If there is a marketing plan, the numbers use its forecast of new customers.

Otherwise it is Not yet, with the numbers that fail. It is Incomplete until both the
numbers and the buyer panel exist. The plan also warns when a Profitable result would
not survive 20% fewer sales.

## Fine print

**Simulated buyers are not customers.** They are a fast, cheap way to find
objections, segments and wording before you spend. They are not a forecast: language
models lean agreeable, so read the buy rate as the best case. Only "would pay now"
counts as a buy, buyers are never told what to object to, and each has a budget and a
current way of doing things they would have to give up. Confirm the big calls with
real people; the plan ends with exactly that test. Never use a buyer's words as a
testimonial.

**The board applies published playbooks. It is not those people.** Each advisor is a
short summary, in our own words, of the ideas in a published book. The advisors never
speak as the authors, quote them or claim they endorse anything. This project is not
affiliated with any of them.

**The competitor research uses public pages only.** Every competitor, price and
complaint links to the page it came from, with the date it was read; the tool refuses
a row without both. Nothing is scraped in bulk or invented.

**The numbers are only as good as the inputs.** Every estimate is marked and listed
so you know what to replace with a real quote. Check costs with suppliers, and the
structure, payroll and tax with an accountant.

**Not financial, legal or tax advice.**

## The tools

Five small Python programs, standard library only. None of them touch the network.

```bash
python3 startup-competitors/competitors.py check startup/competitors.csv
python3 startup-buyers/buyers.py init --customer startup/buyers/customer.json --pitch startup/buyers/pitch.md
python3 startup-marketing/funnel.py startup/marketing.json --apply startup/numbers.json
python3 startup-numbers/numbers.py startup/numbers.json --out startup/numbers.md
python3 startup-plan/plan.py --dir startup
```

The tests:

```bash
python3 -m unittest discover -s startup-skill/tests
```

## License

MIT. Made by Pierre Sabbagh.
