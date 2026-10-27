"""Tests for SQLite persistence, run against a throwaway database."""

from lead_intel import storage
from lead_intel.models import CompanyInput
from lead_intel.scoring import assess_lead
from lead_intel.models import IcpCriteria


def test_save_and_list_roundtrip(tmp_path):
    db = tmp_path / "test.db"
    company = CompanyInput(
        company_name="Acme Corp",
        industry="Software",
        employee_count=200,
        description="Builds an api platform.",
    )
    icp = IcpCriteria(icp_industries=["Software"], icp_min_employees=50)
    result = assess_lead(company, icp)

    storage.save_assessment(company, result, db_path=db)
    rows = storage.list_assessments(db_path=db)

    assert len(rows) == 1
    row = rows[0]
    assert row["company_name"] == "Acme Corp"
    assert row["industry"] == "Software"
    assert row["employee_count"] == 200
    assert row["score"] == result.total_score
    assert row["classification"] == result.classification

def test_saves_are_isolated_per_database(tmp_path):
    db_one = tmp_path / "one.db"
    db_two = tmp_path / "two.db"
    company = CompanyInput(
        company_name="Acme Corp", industry="Software", employee_count=10
    )
    icp = IcpCriteria(icp_industries=["Software"])
    storage.save_assessment(company, assess_lead(company, icp), db_path=db_one)
    storage.save_assessment(company, assess_lead(company, icp), db_path=db_two)
    assert len(storage.list_assessments(db_path=db_one)) == 1
    assert len(storage.list_assessments(db_path=db_two)) == 1
