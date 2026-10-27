# AI Lead Intelligence & Qualification System

A local application that takes information about a potential customer
(a "lead"), evaluates it against your **ideal customer profile (ICP)**, stores
the assessment in SQLite, and shows the result with a transparent,
rule-by-rule explanation.

The score is a **deterministic, rule-based fit score** — plain arithmetic over
your ICP rules. It is **not** an AI-generated prediction.

## How the scoring works

Every rule produces one of three outcomes:

| Outcome       | Meaning                                              | Effect on score              |
| ------------- | ---------------------------------------------------- | ---------------------------- |
| `matched`     | The rule is satisfied                                 | Full points                  |
| `not_matched` | The rule was evaluated and failed                     | 0 points                     |
| `unknown`     | Rule could not be evaluated (input is missing)        | 0 points, excluded from max, listed under "Missing information" |

Rules and weights (total 100):

| Rule                                   | Points | Meaning                                            |
| -------------------------------------- | ------ | -------------------------------------------------- |
| Industry match                         | 35     | The company's industry is in your target list       |
| Company size                           | 30     | Employee count is at least the preferred minimum    |
| Relevant keywords                      | 25     | Description mentions one of your keywords           |
| Description depth                      | 10     | Description is at least 100 characters              |

The classification compares the points earned with the points that were
actually evaluatable:

- earn **75%+** → `Strong fit`
- earn **45%+** → `Qualified`
- otherwise → `Poor fit`

## Installation

Requires Python 3.12+. From the project root:

```bash
python3 -m venv .venv                # or: uv venv
uv pip install -r requirements.txt   # or, with a classic venv:
                                     # .venv/bin/pip install -r requirements.txt
```

## Run the app

```bash
.venv/bin/streamlit run app.py
```

Then open http://localhost:8501 in your browser. Submissions are saved to
`data/assessments.db` (created automatically; gitignored).

## Run the tests

```bash
.venv/bin/pytest -v
```

## Project structure

```
app.py                  Streamlit UI only (input form + result display)
lead_intel/
  models.py             Pydantic validation of company and ICP input
  scoring.py            Deterministic qualification engine (pure logic)
  storage.py            SQLite persistence (parameterized queries)
  export.py             CSV export built with pandas
tests/                  Unit tests for validation, scoring, storage, export
data/                   SQLite database lives here (not committed)
```

## Milestones

- [x] M1: input validation, deterministic scoring, SQLite persistence, basic Streamlit UI
- [x] M2: history view, CSV export
- [ ] M3: external AI integration (pending review)
