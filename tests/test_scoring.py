"""Unit tests for the deterministic qualification engine."""

import pytest

from lead_intel.models import CompanyInput, IcpCriteria
from lead_intel.scoring import (
    WEIGHT_DEPTH,
    WEIGHT_INDUSTRY,
    WEIGHT_KEYWORDS,
    WEIGHT_SIZE,
    UNKNOWN,
    assess_lead,
    classify,
)


def make_lead(**overrides):
    """Helper: a company known to match the default ICP in every rule."""
    defaults = dict(
        company_name="Acme Corp",
        industry="Software",
        employee_count=200,
        description=(
            "Builds an api platform for developers, used by thousands of "
            "engineering teams around the world to ship software faster and "
            "with fewer production incidents."
        ),
    )
    defaults.update(overrides)
    return CompanyInput(**defaults)


def make_icp(**overrides):
    defaults = dict(
        icp_industries=["Software", "SaaS"],
        icp_min_employees=50,
        icp_keywords=["api", "platform"],
    )
    defaults.update(overrides)
    return IcpCriteria(**defaults)


class TestAssessLead:
    def test_perfect_lead_scores_maximum_and_matches_every_rule(self):
        result = assess_lead(make_lead(), make_icp())
        assert result.total_score == 100
        assert result.max_possible == 100
        assert result.classification == "Strong fit"
        assert all(c.status == "matched" for c in result.criteria)
        assert result.missing_info == []

    def test_total_mismatch_scores_zero(self):
        result = assess_lead(
            make_lead(
                industry="Farming",
                employee_count=3,
                description="Grows potatoes near the coast.",
            ),
            make_icp(),
        )
        assert result.total_score == 0
        assert result.classification == "Poor fit"
        statuses = {c.name: c.status for c in result.criteria}
        assert statuses["Industry match"] == "not_matched"
        assert statuses["Company size"] == "not_matched"
        assert statuses["Relevant keywords"] == "not_matched"

    def test_matching_is_case_insensitive(self):
        result = assess_lead(
            make_lead(
                industry="SOFTWARE",
                description=(
                    "A PLATFORM for anything, providing an ApI and tooling "
                    "for teams that build and ship software products at "
                    "scale every single day."
                ),
            ),
            make_icp(),
        )
        assert result.total_score == WEIGHT_INDUSTRY + WEIGHT_SIZE + WEIGHT_KEYWORDS + WEIGHT_DEPTH

    def test_size_boundary_exactly_meets_minimum(self):
        result = assess_lead(make_lead(employee_count=50), make_icp())
        size = next(c for c in result.criteria if c.name == "Company size")
        assert size.status == "matched"

    def test_missing_description_is_unknown_not_failed(self):
        result = assess_lead(make_lead(description=None), make_icp())
        statuses = {c.name: c.status for c in result.criteria}
        assert statuses["Relevant keywords"] == UNKNOWN
        keywords = next(c for c in result.criteria if c.name == "Relevant keywords")
        assert keywords.points == 0
        assert result.missing_info, "missing description should be reported"

    def test_unknown_rules_excluded_from_max_possible(self):
        result = assess_lead(make_lead(description=None), make_icp())
        # Only industry and size are evaluatable without a description.
        assert result.max_possible == WEIGHT_INDUSTRY + WEIGHT_SIZE

    def test_missing_description_scores_perfectly_on_known_rules(self):
        """With industry+size matched, score 65/65; the gap is reported, not punished."""
        result = assess_lead(make_lead(description=None), make_icp())
        assert result.total_score == WEIGHT_INDUSTRY + WEIGHT_SIZE
        assert result.max_possible == WEIGHT_INDUSTRY + WEIGHT_SIZE
        assert len(result.missing_info) == 2

    def test_engine_is_deterministic(self):
        first = assess_lead(make_lead(), make_icp())
        second = assess_lead(make_lead(), make_icp())
        assert first.total_score == second.total_score
        assert [c.status for c in first.criteria] == [
            c.status for c in second.criteria
        ]

    def test_no_empty_icp_industries_possible_via_model(self):
        """The ICP model refuses a target-industry list that is all blanks."""
        with pytest.raises(Exception):
            IcpCriteria(icp_industries=["   "])


class TestClassify:
    @pytest.mark.parametrize(
        "ratio, expected",
        [
            (1.0, "Strong fit"),
            (0.75, "Strong fit"),
            (0.60, "Qualified"),
            (0.45, "Qualified"),
            (0.44, "Poor fit"),
            (0.0, "Poor fit"),
        ],
    )
    def test_thresholds(self, ratio, expected):
        assert classify(ratio) == expected
