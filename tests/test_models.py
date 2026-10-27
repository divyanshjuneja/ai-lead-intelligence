"""Unit tests for the Pydantic input models."""

import pytest
from pydantic import ValidationError

from lead_intel.models import CompanyInput, IcpCriteria


class TestCompanyInput:
    def test_valid_input_is_accepted(self):
        company = CompanyInput(
            company_name="Acme Corp",
            industry="Software",
            employee_count=200,
            description="Builds developer tools.",
        )
        assert company.company_name == "Acme Corp"
        assert company.employee_count == 200

    def test_blank_company_name_is_rejected(self):
        with pytest.raises(ValidationError):
            CompanyInput(company_name="   ", industry="Software", employee_count=10)

    def test_input_is_trimmed(self):
        company = CompanyInput(
            company_name="  Acme Corp  ", industry=" Software ", employee_count=10
        )
        assert company.company_name == "Acme Corp"
        assert company.industry == "Software"

    def test_zero_employees_is_rejected(self):
        with pytest.raises(ValidationError):
            CompanyInput(company_name="Acme", industry="Software", employee_count=0)

    def test_negative_employees_is_rejected(self):
        with pytest.raises(ValidationError):
            CompanyInput(company_name="Acme", industry="Software", employee_count=-5)

    def test_employees_must_be_an_integer(self):
        with pytest.raises(ValidationError):
            CompanyInput(company_name="Acme", industry="Software", employee_count="many")

    def test_empty_description_becomes_none(self):
        company = CompanyInput(
            company_name="Acme", industry="Software", employee_count=10, description="  "
        )
        assert company.description is None

    def test_description_is_trimmed(self):
        company = CompanyInput(
            company_name="Acme", industry="Software", employee_count=10,
            description="  Builds developer tools.  ",
        )
        assert company.description == "Builds developer tools."

    def test_company_name_max_length(self):
        with pytest.raises(ValidationError):
            CompanyInput(company_name="A" * 201, industry="Software", employee_count=10)


class TestIcpCriteria:
    def test_valid_icp_is_accepted(self):
        icp = IcpCriteria(
            icp_industries=["Software", "SaaS"],
            icp_min_employees=25,
            icp_keywords=["api"],
        )
        assert icp.icp_industries == ["Software", "SaaS"]

    def test_icp_industries_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            IcpCriteria(icp_industries=[])

    def test_blank_entries_are_dropped(self):
        icp = IcpCriteria(icp_industries=["  Software  ", "   "])
        assert icp.icp_industries == ["Software"]

    def test_min_employees_cannot_be_below_one(self):
        with pytest.raises(ValidationError):
            IcpCriteria(icp_industries=["Software"], icp_min_employees=0)

    def test_min_employee_count_default(self):
        icp = IcpCriteria(icp_industries=["Software"])
        assert icp.icp_min_employees == 50

    def test_keywords_optionally_provided(self):
        icp = IcpCriteria(icp_industries=["Software"])
        assert icp.icp_keywords == []
