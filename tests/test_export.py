"""Tests for CSV export."""

import csv
import io

from lead_intel import export, storage
from lead_intel.models import CompanyInput, IcpCriteria
from lead_intel.scoring import assess_lead


def save_one_assessment(db) -> None:
    company = CompanyInput(
        company_name="Acme Corp",
        industry="Software",
        employee_count=200,
        description="Builds an api platform for developer teams.",
    )
    icp = IcpCriteria(
        icp_industries=["Software"],
        icp_min_employees=50,
        icp_keywords=["api", "platform"],
    )
    storage.save_assessment(company, assess_lead(company, icp), db_path=db)


def test_export_contains_header_and_saved_row(tmp_path):
    db = tmp_path / "test.db"
    save_one_assessment(db)

    csv_text = export.export_csv(db_path=db)
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    assert len(rows) == 1
    row = rows[0]
    assert row["company_name"] == "Acme Corp"
    assert row["industry"] == "Software"
    assert row["employee_count"] == "200"
    assert row["score"] == "90"
    assert row["classification"] == "Strong fit"

def test_export_header_matches_expected_columns(tmp_path):
    db = tmp_path / "empty.db"
    header = export.export_csv(db_path=db).splitlines()[0]
    assert header.split(",") == export.CSV_COLUMNS


def test_export_columns_are_ordered(tmp_path):
    db = tmp_path / "test.db"
    save_one_assessment(db)
    header = export.export_csv(db_path=db).splitlines()[0]
    assert header.split(",")[:3] == ["id", "company_name", "industry"]
