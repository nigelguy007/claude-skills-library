import pytest

from verified_journalist.llm import LLMError, complete_json
from verified_journalist.models import ResearchPlan
from verified_journalist.style import lint


class Replies:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def complete(self, system, prompt, **kw):
        self.prompts.append(prompt)
        return self.replies.pop(0)

    def usage(self):
        return {}


def test_complete_json_retries_with_error_feedback():
    llm = Replies("sure! here it is", '{"angle": "a", "queries": ["q1"]}')
    plan = complete_json(llm, "sys", "topic", ResearchPlan)
    assert plan.queries == ["q1"]
    assert "not valid" in llm.prompts[1]


def test_complete_json_gives_up():
    llm = Replies("x", "y", "z")
    with pytest.raises(LLMError):
        complete_json(llm, "sys", "topic", ResearchPlan, retries=2)


def test_style_lint_flags_ai_isms():
    hits = {
        h.phrase
        for h in lint(
            "This pivotal moment underscores a robust, ever-evolving "
            "landscape. Moreover, experts believe it will delve deeper."
        )
    }
    assert {
        "pivotal",
        "underscores",
        "robust",
        "ever-evolving",
        "moreover",
        "experts believe",
        "delve",
    } <= hits
    assert lint("The council voted 7 to 2 on Tuesday.") == []
