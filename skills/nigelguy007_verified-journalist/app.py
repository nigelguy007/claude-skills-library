"""Streamlit front end. Run with: streamlit run app.py"""

from __future__ import annotations

import streamlit as st

from verified_journalist import InsufficientSourcesError, Journalist, Settings
from verified_journalist.config import ARTICLE_STYLES

st.set_page_config(page_title="Verified Journalist", page_icon="🗞️", layout="wide")
st.title("Verified Journalist")
st.caption(
    "Researches a topic, writes an article, then checks every quote and citation against the "
    "fetched sources. Anything it can't verify is flagged, not published."
)

env = Settings()
with st.sidebar:
    st.header("Keys")
    st.caption("Read from environment variables when set. Keys typed here stay in this session.")
    provider = st.radio(
        "LLM provider",
        ["anthropic", "openai"],
        index=0 if env.llm_provider != "openai" else 1,
        horizontal=True,
    )
    env_llm_key = env.anthropic_api_key if provider == "anthropic" else env.openai_api_key
    llm_key = st.text_input(
        f"{provider.title()} API key",
        type="password",
        placeholder="set in environment" if env_llm_key else "",
    )
    tavily = st.text_input(
        "Tavily API key",
        type="password",
        placeholder="set in environment" if env.tavily_api_key else "",
    )
    brave = st.text_input(
        "Brave Search API key",
        type="password",
        placeholder="set in environment" if env.brave_api_key else "",
    )
    serpapi = st.text_input(
        "SerpAPI key",
        type="password",
        placeholder="set in environment" if env.serpapi_api_key else "",
    )

    st.header("Article")
    style = st.selectbox(
        "Style", sorted(ARTICLE_STYLES), index=sorted(ARTICLE_STYLES).index("news")
    )
    words = st.slider("Target words", 400, 3000, 1200, step=100)
    max_sources = st.slider("Max sources", 3, 15, 8)
    recency = st.number_input("Prefer sources newer than N days (0 = off)", 0, 3650, 0)

topic = st.text_input(
    "What should the article cover?",
    placeholder="e.g. How the EU AI Act's general-purpose model rules apply",
)
go = st.button("Write article", type="primary", disabled=not topic.strip())

if go:
    overrides = {
        k: v
        for k, v in {
            f"{provider}_api_key": llm_key.strip(),
            "tavily_api_key": tavily.strip(),
            "brave_api_key": brave.strip(),
            "serpapi_api_key": serpapi.strip(),
        }.items()
        if v
    }
    try:
        settings = Settings(
            llm_provider=provider,
            style=style,
            target_words=words,
            max_sources=max_sources,
            recency_days=recency or None,
            **overrides,
        )
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    if missing := settings.missing():
        st.error("Missing " + " and ".join(missing) + ".")
        st.stop()

    with st.status("Working…", expanded=True) as status:
        try:
            article = Journalist(settings).run(
                topic, on_progress=lambda stage, detail: st.write(f"**{stage}** · {detail}")
            )
        except InsufficientSourcesError as exc:
            status.update(label="Not enough usable sources", state="error")
            st.error(str(exc))
            st.stop()
        except Exception as exc:  # surface provider/API errors without a stack trace
            status.update(label="Failed", state="error")
            st.error(f"{type(exc).__name__}: {exc}")
            st.stop()
        status.update(label="Done", state="complete", expanded=False)
    st.session_state["article"] = article

article = st.session_state.get("article")
if article:
    critical = [i for i in article.issues if i.severity == "critical"]
    warnings = [i for i in article.issues if i.severity == "warning"]
    if article.status == "ready":
        st.success(f"Ready: every quote and citation checked · {len(warnings)} warning(s)")
    else:
        st.error(
            f"Needs human review: {len(critical)} critical issue(s). See the Verification tab."
        )

    tab_article, tab_verify, tab_sources = st.tabs(["Article", "Verification", "Sources"])
    with tab_article:
        st.markdown(article.markdown)
    with tab_verify:
        for issue in article.issues:
            icon = {"critical": "🔴", "warning": "🟡", "info": "⚪"}[issue.severity]
            st.markdown(f"{icon} **{issue.kind}**: {issue.detail}")
        if not article.issues:
            st.write("No issues found.")
        st.subheader("Sentence-level fact check")
        st.dataframe(
            [
                {"verdict": c.verdict, "sentence": c.sentence, "cites": c.citations, "note": c.note}
                for c in article.fact_checks
            ],
            use_container_width=True,
        )
        st.caption(f"Revisions: {article.revisions} · Token usage: {article.usage}")
    with tab_sources:
        for s in article.sources:
            st.markdown(
                f"**[{s.id}]** [{s.title}]({s.url}) · {s.domain} · tier: {s.tier}"
                f" · {s.published or 'date unknown'}"
            )

    c1, c2 = st.columns(2)
    c1.download_button("Download Markdown", article.markdown, "article.md", "text/markdown")
    c2.download_button(
        "Download full report (JSON)",
        article.model_dump_json(indent=2),
        "report.json",
        "application/json",
    )
