"""CSV export of stored assessments using pandas.

Kept separate from `storage.py` on purpose: storage knows how to read rows
from SQLite, this module knows how to turn rows into a CSV text file. Each
file does one job.
"""

import pandas as pd

from lead_intel import storage

# Column order for the exported file. "description" is excluded: it holds
# long free text the CSV reader mainly skips, and the scoring columns are
# what the user filters on. Add it to the list if you want it exported.
CSV_COLUMNS = [
    "id",
    "company_name",
    "industry",
    "employee_count",
    "score",
    "max_possible",
    "classification",
    "created_at",
]


def export_csv(db_path=storage.DEFAULT_DB_PATH) -> str:
    """Return every stored assessment as one in-memory CSV string."""
    df = pd.DataFrame(storage.list_assessments(db_path=db_path))
    if df.empty:
        return ",".join(CSV_COLUMNS) + "\n"
    df = df.reindex(columns=CSV_COLUMNS)
    return df.to_csv(index=False)
