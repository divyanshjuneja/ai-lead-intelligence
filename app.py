"""Streamlit interface for the AI Lead Intelligence & Qualification System.

This file is UI only. It reads user input, hands it to the business logic in
`lead_intel`, and renders the results. All scoring, persistence, and export
logic lives elsewhere so it can be tested without a running interface.
"""

import streamlit as st

from lead_intel import ai_summary, export, storage
from lead_intel.models import CompanyInput, IcpCriteria
from lead_intel.scoring import AssessmentResult, assess_lead

st.set_page_config(page_title="AI Lead Intelligence", page_icon=":books:")
st.title("AI Lead Intelligence & Qualification")
st.caption("Rule-based fit assessment against your ideal customer profile.")


def _parse_list(raw: str) -> list[str]:
    """Turn a comma-separated user string into a clean list."""
    return [item.strip() for item in raw.split(",") if item.strip()]


def _render_history() -> None:
    """Show every saved assessment and offer a CSV download."""
    rows = storage.list_assessments()
    if not rows:
        st.info("No assessments saved yet. Submit one in the 'New assessment' tab.")
        return

    st.dataframe(
        rows,
        column_config={
            "employee_count": st.column_config.NumberColumn("Employees"),
            "score": st.column_config.ProgressColumn(
                "Score", max_value=100, format="%d"
            ),
            "classification": st.column_config.TextColumn("Verdict"),
        },
        hide_index=True,
    )
    st.download_button(
        "Download all as CSV",
        data=export.export_csv(),
        file_name="lead_assessments.csv",
        mime="text/csv",
        type="primary",
    )


def _render_summary(company: CompanyInput, result) -> None:
    """Optional AI commentary. Fails soft: any problem is a warning, never a crash."""
    api_key = ai_summary.get_api_key()
    if not api_key:
        st.warning(
            "AI commentary skipped: no GEMINI_API_KEY found. "
            "Create one at aistudio.google.com/apikey and add it to .env "
            "as GEMINI_API_KEY=...(.env is gitignored)."
        )
        return
    try:
        summary = ai_summary.generate_summary(company, result, api_key)
    except ai_summary.AiSummaryError as error:
        st.warning(f"AI commentary unavailable: {error}")
        return
    st.subheader("AI commentary")
    st.write(summary)
    st.caption(
        "⚠️ AI-generated commentary. The score above is purely rule-based "
        "and was not produced or altered by the AI."
    )


def _render_result(
    result: AssessmentResult, assessment_id: int
) -> None:
    """Display one assessment: verdict, rule breakdown, missing info."""
    st.success(
        f"Saved as assessment #{assessment_id}. "
        "This is a rule-based fit score, not an AI prediction."
    )

    st.subheader(f"Result: {result.classification}")
    st.metric(
        "Fit score",
        f"{result.total_score}/{result.max_possible}",
        help="Maximum possible reflects only the rules we could evaluate.",
    )

    st.subheader("How the score was built")
    for criterion in result.criteria:
        icon = "✅" if criterion.status == "matched" else (
            "❓" if criterion.status == "unknown" else "🚫"
        )
        st.markdown(
            f"{icon} **{criterion.name}** — {criterion.points}/"
            f"{criterion.max_points} pts: {criterion.explanation}"
        )

    if result.missing_info:
        st.subheader("Missing information")
        for item in result.missing_info:
            st.info(item)


company_tab, history_tab = st.tabs(["New assessment", "History"])

with company_tab:
    with st.form("lead_form"):
        st.subheader("Company under assessment")
        company_name = st.text_input("Company name", max_chars=200)
        industry = st.text_input("Industry", max_chars=100)
        employee_count = st.number_input(
            "Employee count", min_value=1, max_value=10_000_000, step=1, value=50
        )
        description = st.text_area(
            "Company description (optional, but more detail = better assessment)",
            height=120,
        )

        st.subheader("Your ideal customer profile (ICP)")
        icp_raw = st.text_input(
            "Target industries (comma-separated)",
            value="software, saas, fintech",
            help="The company matches if its industry is on this list.",
        )
        icp_min_employees = st.number_input(
            "Minimum employee count", min_value=1, value=50, step=1
        )
        icp_keywords_raw = st.text_input(
            "Target keywords (comma-separated)",
            value="api, platform",
            help="Matches are case-insensitive substring searches in the description.",
        )
        ai_commentary = st.checkbox(
            "Also generate AI commentary (Gemini Flash)",
            value=False,
            help="Optional. The AI only comments on the rule-based result; "
            "it never computes the score. Uses your GEMINI_API_KEY from .env.",
        )

        submitted = st.form_submit_button("Evaluate", type="primary")

    if submitted:
        try:
            icp = IcpCriteria(
                icp_industries=_parse_list(icp_raw),
                icp_min_employees=int(icp_min_employees),
                icp_keywords=_parse_list(icp_keywords_raw),
            )
            company = CompanyInput(
                company_name=company_name,
                industry=industry,
                employee_count=int(employee_count),
                description=description if description.strip() else None,
            )
        except Exception as error:  # pydantic errors (and blank lists) surface here
            st.error(f"Input problem: {error}")
        else:
            try:
                result = assess_lead(company, icp)
                assessment_id = storage.save_assessment(company, result)
            except Exception as error:
                st.error(f"Something went wrong while assessing or saving: {error}")
            else:
                _render_result(result, assessment_id)
                if ai_commentary:
                    _render_summary(company, result)

with history_tab:
    _render_history()
