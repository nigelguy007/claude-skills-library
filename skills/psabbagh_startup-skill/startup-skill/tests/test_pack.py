import json
import os
import re
import unittest

from _paths import PACK, ROOT, load, skill

EM_DASH = chr(0x2014)  # built from its code point so this file does not trip its own check
PUBLIC_URL = "https://github.com/psabbagh/startup-skill"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(name):
    text = read(skill(name, "SKILL.md"))
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return (m.group(1) if m else ""), text


def pack_files():
    for name in PACK:
        for base, dirs, files in os.walk(skill(name)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if f.endswith((".md", ".py", ".json", ".yaml", ".txt")) or f == "LICENSE":
                    yield os.path.join(base, f)


def advisors():
    return re.findall(r"^## The (.+?) advisor$", read(skill("startup-board", "advisors.md")), re.M)


class Skills(unittest.TestCase):
    def test_each_skill_has_a_skill_file(self):
        for name in PACK:
            self.assertTrue(os.path.isfile(skill(name, "SKILL.md")), name)

    def test_frontmatter(self):
        for name in PACK:
            fm, text = frontmatter(name)
            self.assertIn("name: %s\n" % name, fm + "\n", name)
            self.assertRegex(fm, r"description: ", name)
            self.assertGreater(len(fm), 350, "%s: description is too thin" % name)
            if "$ARGUMENTS" in text:
                self.assertIn("argument-hint:", fm, name)

    def test_codex_validator_rules(self):
        # The same rules as Codex's quick_validate.py, which needs PyYAML; argument-hint is allowed
        # here because both hosts load it (see the repository README).
        allowed = {"name", "description", "argument-hint", "license", "allowed-tools", "metadata"}
        for name in PACK:
            fm, _ = frontmatter(name)
            keys = set(re.findall(r"^([\w-]+):", fm, re.M))
            self.assertLessEqual(keys, allowed, name)
            self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
            self.assertLessEqual(len(name), 64)
            m = re.search(r"^description: >-\n((?:  .*\n?)+)", fm, re.M)
            self.assertIsNotNone(m, "%s: description should be a folded block" % name)
            description = " ".join(line.strip() for line in m.group(1).splitlines())
            self.assertLessEqual(len(description), 1024, name)
            self.assertNotRegex(description, r"[<>]", name)

    def test_files_the_skills_name_exist(self):
        for name in PACK:
            _, text = frontmatter(name)
            for rel in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w.\-/]+\.(?:py|md|json))", text):
                self.assertTrue(os.path.exists(skill(name, rel)), "%s names %s" % (name, rel))
            for rel in re.findall(r"`((?:references/|example|customer\.example|pitch\.example)[\w.\-/]*)`", text):
                self.assertTrue(os.path.exists(skill(name, rel)), "%s names %s" % (name, rel))

    def test_codex_interface(self):
        for name in PACK:
            text = read(skill(name, "agents", "openai.yaml"))
            short = re.search(r'short_description: "(.*)"', text).group(1)
            self.assertTrue(25 <= len(short) <= 64, "%s short_description is %d chars" % (name, len(short)))
            self.assertIn("$%s" % name, re.search(r'default_prompt: "(.*)"', text).group(1), name)


class Board(unittest.TestCase):
    def test_the_people_the_reel_names_are_on_the_board(self):
        # The Reel's voice-over says the board uses the playbooks of these three; keep it true.
        found = re.findall(r"^\*\*Playbook:\*\*.*(?:\n(?!\n).*)*", read(skill("startup-board", "advisors.md")), re.M)
        playbooks = " ".join(" ".join(found).split())
        for person in ("Alex Hormozi", "Naval Ravikant", "Paul Graham"):
            self.assertIn(person, playbooks)

    def test_every_advisor_has_every_part(self):
        sections = re.split(r"^## ", read(skill("startup-board", "advisors.md")), flags=re.M)[1:]
        self.assertEqual(len(sections), len(advisors()))
        for section in sections:
            for part in ("**Playbook:**", "**What it looks for**", "**Questions it asks:**", "**Votes pass when**"):
                self.assertIn(part, section, section.splitlines()[0])

    def test_the_board_size_is_stated_correctly(self):
        words = {3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
                 11: "eleven", 12: "twelve"}
        word = words[len(advisors())]
        self.assertIn("There are %s." % word, read(skill("startup-board", "SKILL.md")))
        self.assertIn("board of %s advisors" % word, frontmatter("startup-board")[0])
        self.assertIn("board of %s advisors" % word, read(skill("startup-skill", "README.md")))
        self.assertLessEqual(len(advisors()), 10, "one wave of sub-agents runs about 10 at once")

    def test_the_chair_answers_the_five_questions(self):
        text = read(skill("startup-board", "SKILL.md"))
        self.assertIn("**The five questions.**", text)
        for phrase in ("What one problem does it fix", "expensive version first", "first ten customers",
                       "more than one habit", "many customers, or from one or two big ones"):
            self.assertIn(phrase, text)

    def test_readme_names_every_advisor_book(self):
        readme = read(skill("startup-skill", "README.md"))
        text = read(skill("startup-board", "advisors.md"))
        for book in re.findall(r"\*\*Playbook:\*\* \*(.+?)\*", text):
            self.assertIn(book, readme)


class Wording(unittest.TestCase):
    def test_no_em_dashes(self):
        for path in pack_files():
            self.assertNotIn(EM_DASH, read(path), os.path.relpath(path, ROOT))

    def test_advisors_never_speak_as_the_authors(self):
        pattern = re.compile(r"\b(Hormozi|Thiel|Jobs|Isaacson|Masters)\s+(says|said|would say|thinks|believes)\b")
        for path in pack_files():
            self.assertIsNone(pattern.search(read(path)), os.path.relpath(path, ROOT))

    def test_written_fresh(self):
        # Guards for the rewrite: no credit to, or distinctive wording from, the pack it replaced.
        banned = ["Schincariol", "opusjake", "founder-skill", "founder-board", "founder-consumer", "founder/",
                  "The craziest part", "Competition destroys profit", "Focus means saying no",
                  "Pick the market first", "Simplicity is the hard part", "Own the whole experience"]
        for path in pack_files():
            if os.path.basename(path) == "test_pack.py":
                continue
            text = read(path)
            for phrase in banned:
                self.assertNotIn(phrase, text, "%s contains %r" % (os.path.relpath(path, ROOT), phrase))


class Examples(unittest.TestCase):
    def test_examples_load_and_run(self):
        buyers = load("startup-buyers", "buyers")
        numbers = load("startup-numbers", "numbers")
        competitors = load("startup-competitors", "competitors")
        funnel = load("startup-marketing", "funnel")
        with open(skill("startup-buyers", "customer.example.json"), encoding="utf-8") as fh:
            buyers.check_customer(json.load(fh))
        for name in ("example-subscription.json", "example-one-time.json"):
            with open(skill("startup-numbers", name), encoding="utf-8") as fh:
                numbers.analyse(json.load(fh))
        self.assertEqual(competitors.problems(competitors.read(skill("startup-competitors", "competitors.example.csv"))), [])
        with open(skill("startup-marketing", "marketing.example.json"), encoding="utf-8") as fh:
            funnel.forecast(json.load(fh))

    def test_example_competitors_are_clearly_made_up(self):
        competitors = load("startup-competitors", "competitors")
        for row in competitors.read(skill("startup-competitors", "competitors.example.csv")):
            self.assertTrue(row["url"].startswith("https://example.com/"), row["name"])


class Order(unittest.TestCase):
    STEPS = ["startup-board", "startup-competitors", "startup-buyers", "startup-marketing", "startup-numbers",
             "startup-plan"]

    def test_run_all_lists_the_six_steps_in_order(self):
        text = read(skill("startup-skill", "SKILL.md"))
        self.assertIn("Six steps", text)
        for i, step in enumerate(self.STEPS, start=1):
            self.assertIn("**Step %d, `%s`" % (i, step), text)

    def test_each_step_points_to_the_next(self):
        for here, nxt in zip(self.STEPS, self.STEPS[1:]):
            self.assertIn("/%s" % nxt, read(skill(here, "SKILL.md")), "%s should point to %s" % (here, nxt))

    def test_competitors_never_from_memory(self):
        text = read(skill("startup-competitors", "SKILL.md"))
        for phrase in ("never fill the table from memory", "codex --search", "Never invent"):
            self.assertIn(phrase, text)


class Release(unittest.TestCase):
    def test_license(self):
        text = read(skill("startup-skill", "LICENSE"))
        self.assertTrue(text.startswith("MIT License"))
        self.assertIn("Copyright (c) 2026 Pierre Sabbagh", text)

    def test_readme(self):
        readme = read(skill("startup-skill", "README.md"))
        self.assertIn(PUBLIC_URL, readme)
        self.assertIn("install skill", readme)
        self.assertIn("lean agreeable", readme)
        self.assertIn("Profitable, or Not yet", readme)
        for name in PACK:
            self.assertIn("`/%s`" % name, readme)

    def test_the_pitch_can_be_improved_and_retested(self):
        buyers_skill = read(skill("startup-buyers", "SKILL.md"))
        self.assertIn("## Improve the pitch and re-test", buyers_skill)
        for phrase in ("mv startup/buyers startup/buyers-v1", "--seed <the seed from startup/buyers-v1/results.md>",
                       "Stop after two rounds", "never invent a\ncustomer result"):
            self.assertIn(phrase, buyers_skill)
        self.assertIn("Improve the pitch and re-test", read(skill("startup-skill", "SKILL.md")))
        self.assertIn("re-test it on the same buyers", read(skill("startup-skill", "README.md")))
        for name in PACK:
            self.assertNotIn("--dir startup/buyers-v2", read(skill(name, "SKILL.md")), name)

    def test_readme_covers_codex(self):
        readme = read(skill("startup-skill", "README.md"))
        for phrase in ("### For Codex: how to install", "cp -R /tmp/startup-skill-install/startup-* ~/.codex/skills/",
                       "multi_agent = true", "$startup-skill a booking app", "codex --full-auto"):
            self.assertIn(phrase, readme)
        hosts = read(skill("startup-buyers", "references", "hosts.md"))
        self.assertIn("Codex, multi-agent on", hosts)


if __name__ == "__main__":
    unittest.main()
