"""Deterministic, rule-based lead qualification engine.

Design decisions:
- Pure functions: same input always produces the same score. No randomness,
  no network calls, no hidden state. This makes the engine fully unit-testable
  without a database or a running UI.
- Three rule outcomes instead of two: `matched`, `not_matched`, and
  `unknown`. `unknown` means the rule could not be evaluated because input is
  missing (e.g. no description). Unknown rules contribute 0 points and are
  excluded from the maximum possible score, so a company is never penalised
  for data it was never asked to provide — the app instead reports the gap
  under "missing information".
- The score is explicitly a RULE-BASED fit score, not an AI prediction.
  Nothing here claims intelligence; it is arithmetic over user-defined rules.

Scoring weights (highest influence first):
    Industry match ....... 35  (selling outside your market rarely converts)
    Company size ......... 30  (size is usually the second-biggest filter)
    Keyword in description 25  (signals the company actually does relevant work)
    Description depth ..... 10  (rich descriptions correlate with real fit)

    Total maximum ....... 100
"""

from dataclasses import dataclass, field

from lead_intel.models import CompanyInput, IcpCriteria

WEIGHT_INDUSTRY = 35
WEIGHT_SIZE = 30
WEIGHT_KEYWORDS = 25
WEIGHT_DEPTH = 10

MIN_DEPTH_CHARS = 100

# Classification cut-offs, applied to score / maximum_evaluable_points.
STRONG_FIT_RATIO = 0.75
QUALIFIED_RATIO = 0.45

UNKNOWN = "unknown"


@dataclass
class CriterionResult:
    """The outcome of evaluating ONE scoring rule.

    status is one of "matched", "not_matched", or "unknown".
    """

    name: str
    status: str
    points: int
    max_points: int
    explanation: str


@dataclass
class AssessmentResult:
    """The complete, explainable output of the engine for one company."""

    total_score: int
    max_possible: int            # only rules we could actually evaluate
    classification: str
    criteria: list[CriterionResult] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)


def evaluate_industry(company: CompanyInput, icp: IcpCriteria) -> CriterionResult:
    """Rule 1: does the company's industry match the target industries?

    Matching is case-insensitive exact comparison between the requested
    industry and each target industry.
    """
    if not icp.icp_industries:
        return CriterionResult(
            "Industry match", UNKNOWN, 0, WEIGHT_INDUSTRY,
            "No target industries were provided, so this rule cannot be evaluated.",
        )
    target = {value.lower() for value in icp.icp_industries}
    requested = company.industry.lower()
    if requested in target:
        return CriterionResult(
            "Industry match", "matched", WEIGHT_INDUSTRY, WEIGHT_INDUSTRY,
            f"Industry '{company.industry}' is one of the target industries.",
        )
    return CriterionResult(
        "Industry match", "not_matched", 0, WEIGHT_INDUSTRY,
        f"Industry '{company.industry}' is not in the target list "
        f"{sorted(target)}.",
    )


def evaluate_size(company: CompanyInput, icp: IcpCriteria) -> CriterionResult:
    """Rule 2: employee count at or above the ideal customer's minimum."""
    if company.employee_count >= icp.icp_min_employees:
        return CriterionResult(
            "Company size", "matched", WEIGHT_SIZE, WEIGHT_SIZE,
            f"{company.employee_count} employees meets the minimum of "
            f"{icp.icp_min_employees}.",
        )
    return CriterionResult(
        "Company size", "not_matched", 0, WEIGHT_SIZE,
        f"{company.employee_count} employees is below the preferred "
        f"minimum of {icp.icp_min_employees}.",
    )


def evaluate_keywords(company: CompanyInput, icp: IcpCriteria) -> CriterionResult:
    """Rule 3: does the description mention any target keyword?

    Without a description the rule is `unknown`, not failed — we simply do
    not know whether the keywords appear.
    """
    if company.description is None:
        return CriterionResult(
            "Relevant keywords", UNKNOWN, 0, WEIGHT_KEYWORDS,
            "No description was provided, so keywords cannot be checked.",
        )
    text = company.description.lower()
    found = [keyword for keyword in icp.icp_keywords if keyword.lower() in text]
    if found:
        return CriterionResult(
            "Relevant keywords", "matched", WEIGHT_KEYWORDS, WEIGHT_KEYWORDS,
            f"Description mentions target keyword(s): {found}.",
        )
    return CriterionResult(
        "Relevant keywords", "not_matched", 0, WEIGHT_KEYWORDS,
        f"None of the target keywords {icp.icp_keywords} appear in the "
        f"description.",
    )


def evaluate_depth(company: CompanyInput) -> CriterionResult:
    """Rule 4: is the description detailed enough to judge fit?

    A short one-line description (below MIN_DEPTH_CHARS) is flagged so the
    user knows the assessment is based on thin information.
    """
    if company.description is None:
        return CriterionResult(
            "Description depth", UNKNOWN, 0, WEIGHT_DEPTH,
            "No description was provided, so description quality cannot be judged.",
        )
    if len(company.description) < MIN_DEPTH_CHARS:
        return CriterionResult(
            "Description depth", "not_matched", 0, WEIGHT_DEPTH,
            f"Description is only {len(company.description)} characters; at least "
            f"{MIN_DEPTH_CHARS} gives a more reliable assessment.",
        )
    return CriterionResult(
        "Description depth", "matched", WEIGHT_DEPTH, WEIGHT_DEPTH,
        f"Description is detailed ({len(company.description)} characters).",
    )


def classify(ratio: float) -> str:
    """Map the earned/possible ratio to a plain-language label."""
    if ratio >= STRONG_FIT_RATIO:
        return "Strong fit"
    if ratio >= QUALIFIED_RATIO:
        return "Qualified"
    return "Poor fit"


def assess_lead(company: CompanyInput, icp: IcpCriteria) -> AssessmentResult:
    """Evaluate every rule and assemble the full result.

    This is the single entry point the UI (and future milestones, such as
    batch evaluation) should call.
    """
    criteria = [
        evaluate_industry(company, icp),
        evaluate_size(company, icp),
        evaluate_keywords(company, icp),
        evaluate_depth(company),
    ]

    total = sum(c.points for c in criteria)
    max_possible = sum(c.max_points for c in criteria if c.status != UNKNOWN)
    ratio = total / max_possible if max_possible else 0.0

    missing_info = [
        c.explanation for c in criteria if c.status == UNKNOWN
    ]

    return AssessmentResult(
        total_score=total,
        max_possible=max_possible,
        classification=classify(ratio),
        criteria=criteria,
        missing_info=missing_info,
    )
