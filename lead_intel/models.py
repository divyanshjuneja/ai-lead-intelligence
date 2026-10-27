"""Input models validated with Pydantic.

These models define what a *valid* lead looks like *before* any scoring
happens. The Streamlit UI collects raw strings and numbers; the models here
refuse anything malformed. Business logic (scoring) never sees invalid data.
"""

from pydantic import BaseModel, Field, field_validator, model_validator


class CompanyInput(BaseModel):
    """A company (the potential customer) submitted for assessment.

    Only `description` is optional on purpose: a user can submit a company
    with the basic facts they have, and the scoring engine will report the
    description as *missing information* instead of rejecting the lead.
    """

    company_name: str = Field(min_length=1, max_length=200)
    industry: str = Field(min_length=1, max_length=100)
    employee_count: int = Field(ge=1, le=10_000_000)
    description: str | None = Field(default=None, max_length=5_000)

    @field_validator("company_name", "industry")
    @classmethod
    def strip_and_reject_blank(cls, value: str) -> str:
        """Reject values that are only whitespace, e.g. "   "."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must not be blank")
        return trimmed

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        """Strip whitespace; turn an empty string into None (missing)."""
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class IcpCriteria(BaseModel):
    """The ideal customer profile (ICP) the company is evaluated against.

    The user provides these in the UI — they describe *who they want to sell
    to*, not the company being assessed.
    """

    icp_industries: list[str] = Field(min_length=1)
    icp_min_employees: int = Field(default=50, ge=1)
    icp_keywords: list[str] = Field(default_factory=list)

    @field_validator("icp_industries", "icp_keywords")
    @classmethod
    def strip_values(cls, values: list[str]) -> list[str]:
        """Trim whitespace on every entry and drop empty ones."""
        return [value.strip() for value in values if value.strip()]

    @model_validator(mode="after")
    def require_at_least_one_industry(self) -> "IcpCriteria":
        """After cleanup, at least one target industry must remain.

        A separate model-level check is needed because `min_length=1` runs
        before the strip validator, so a list of blank strings would empty
        the list unnoticed.
        """
        if not self.icp_industries:
            raise ValueError("icp_industries must contain at least one industry")
        return self
