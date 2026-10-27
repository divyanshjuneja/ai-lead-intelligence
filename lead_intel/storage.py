"""SQLite persistence for company assessments.

Design decisions:
- The built-in `sqlite3` module only: no ORM, no extra dependency.
- SQL statements are constants and every query is parameterized with `?`
  placeholders. We never build SQL strings from user input with f-strings,
  which is how SQL injection bugs happen.
- The database connection is opened per call (short-lived connections) and
  always closed. For a local single-user app this is the simplest correct
  approach and avoids passing connections around.
- Rule results are stored as JSON text so the full explanation survives
  storage and can be re-displayed in the history view later.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lead_intel.models import CompanyInput
from lead_intel.scoring import AssessmentResult

DEFAULT_DB_PATH = Path("data") / "assessments.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name    TEXT    NOT NULL,
    industry        TEXT    NOT NULL,
    employee_count  INTEGER NOT NULL,
    description     TEXT,
    score           INTEGER NOT NULL,
    max_possible    INTEGER NOT NULL,
    classification  TEXT    NOT NULL,
    criteria_json   TEXT    NOT NULL,
    missing_json    TEXT    NOT NULL,
    created_at      TEXT    NOT NULL
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection, creating the parent folder and schema if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.execute(_SCHEMA)
    connection.commit()
    return connection


def save_assessment(
    company: CompanyInput,
    result: AssessmentResult,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """Store one assessment and return its database id."""
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO assessments
                (company_name, industry, employee_count, description,
                 score, max_possible, classification,
                 criteria_json, missing_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company.company_name,
                company.industry,
                company.employee_count,
                company.description,
                result.total_score,
                result.max_possible,
                result.classification,
                json.dumps([vars(c) for c in result.criteria]),
                json.dumps(result.missing_info),
                created_at,
            ),
        )
        return int(cursor.lastrowid)


def list_assessments(
    db_path: Path = DEFAULT_DB_PATH,
    limit: int = 100,
) -> list[dict]:
    """Return saved assessments, newest first, as plain dictionaries."""
    with _connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT id, company_name, industry, employee_count, description,
                   score, max_possible, classification, created_at
            FROM assessments
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
