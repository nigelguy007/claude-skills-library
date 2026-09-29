from verified_journalist import cli


def test_cli_reports_missing_keys(monkeypatch, capsys):
    for var in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "TAVILY_API_KEY",
        "BRAVE_API_KEY",
        "SERPAPI_API_KEY",
        "VJ_LLM_PROVIDER",
    ):
        monkeypatch.delenv(var, raising=False)
    assert cli.main(["some topic", "--no-cache"]) == 2
    err = capsys.readouterr().err
    assert "LLM key" in err and "search key" in err


def test_cli_rejects_bad_source_bounds(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert cli.main(["t", "--min-sources", "9", "--max-sources", "3"]) == 2
