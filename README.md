# GÜS-DEDEKTİV

Inspection prioritisation for GEKAP packaging declarations.

The platform ranks companies by how strongly the available evidence suggests
that a human should look at them, and states what that evidence was. It is a
decision-support tool for auditors, not a declaration portal for companies, and
it does not decide whether anyone has broken the law.

```
Backend    FastAPI · SQLAlchemy 2.0 · Pydantic v2 · SQLite by default, PostgreSQL ready
Frontend   React 19 · Vite · react-router · framer-motion · lucide
Scoring    Eight independent signals behind one interface, rule engine in service
```

---

## Running it

Two processes. The API seeds itself on first boot.

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

The interface is at `http://localhost:5173`, the API at `http://localhost:8000`,
and the generated API reference at `http://localhost:8000/docs`.

Rebuild the dataset from scratch at any point:

```bash
cd backend && python -m app.database.seed --reset
```

Run the tests:

```bash
cd backend && python -m pytest
```

### PostgreSQL

Set `DATABASE_URL` and apply the migrations. Nothing else changes; every column
type in the models exists on both backends.

```bash
export DATABASE_URL=postgresql+psycopg://gus:gus@localhost:5432/gus_dedektiv
alembic upgrade head
python -m app.database.seed
```

---

## What the scoring does

Each company is compared against four independent references: its own filing
history, the volume its output implies, the companies it resembles, and the
customs lines matched to it. Eight checks come out of that, and each one reports
one of three states.

| | Check | Compares |
| --- | --- | --- |
| E1 | Historical shortfall | the declaration against this company's own pattern |
| E2 | Structural shortfall | the declaration against the volume its output implies |
| E3 | Peer deviation | packaging intensity against the same sector and size class |
| E4 | Production mismatch | movement in output against movement in the declaration |
| E5 | Temporal inconsistency | stability of intensity across reporting periods |
| E6 | Numerical pattern | rounding, repetition and threshold behaviour |
| E7 | Field contradiction | site observations against what was filed |
| E8 | Customs tariff evidence | packaging implied by GTIP lines against the filing |

**Firing**, **quiet**, and **unavailable** are three different results. A check
that could not run has its weight removed from the calculation rather than
counted as a zero, so missing data never reads as a clean bill of health. What
it produces instead is a lower *evidence coverage* figure next to the score.

The final number is the weighted mean of the checks that ran, blended with the
single strongest finding at a fixed share. Without that blend a company that is
consistently wrong in one way ranks below a company that is slightly wrong in
four, which is not how a team triages.

The expected range is anchored on what the company's own output implies,
adjusted within bounds by its own filing behaviour, and **widened as data
quality falls**. A tight interval on a poorly evidenced company is the failure
mode that sends inspectors to the wrong door. Shortfall is measured against the
bottom of the range, never its middle.

Thresholds, signal weights and the blend are policy, not code:
`GET`/`PUT /api/scoring/policy`.

---

## Handing over to the model

The engine is an interface with two implementations. `MockScoringEngine` is in
service; `MLScoringEngine` is the seat the trained model takes.

```
app/scoring/base.py          the contract: dataclasses in, ScoreOutcome out
app/scoring/mock_scorer.py   deterministic rules, in service today
app/scoring/ml_scorer.py     quantile models plus conformal calibration
app/scoring/registry.py      selection, and fallback when an engine cannot serve
```

The engine never sees the ORM. It receives `ScoringContext` — plain dataclasses
holding the company, its declaration history, its peer cohort, its site visits,
its customs lines and its data quality — and returns `ScoreOutcome`. The API
serialises that same shape whichever engine produced it, so **replacing the
engine requires no frontend change**.

To switch over: drop the artefacts into `backend/models/` and set
`SCORING_ENGINE=ml`. Until they are present, `resolve_engine` falls back to the
rule engine and every response says which engine actually produced it.

Two rules the implementation has to keep, and the current engine keeps:

1. A feature that cannot be computed makes the checks that depend on it
   unavailable. It is not imputed to a neutral value and scored as observed.
2. The conformal interval widens for groups with thin calibration data.

---

## Layout

```
backend/
  app/
    main.py            application, CORS, router mounting
    config.py          settings, and the scoring policy an authority can tune
    reference.py       GEKAP tariffs, sector coefficients, signal catalogue
    routers/           dashboard, companies, inspections, impact, transparency
    schemas/           the wire contract
    services/          queries, workflow, audit chain, impact, pilot
    scoring/           the engine interface and its implementations
    models/            SQLAlchemy tables
    database/          engine, session, seed
  tests/               engine properties and the API contract
  alembic/             migrations, for the PostgreSQL deployment

frontend/
  src/
    pages/             the nine screens
    components/        dock, tables, charts, the review sheet
    lib/               API client, formatting, domain vocabulary
    styles/            tokens, components, dock, app
```

---

## API

```
GET  /api/dashboard                      where the period stands
GET  /api/inspection-queue               the operational queue, filtered and paged
GET  /api/companies/{id}                 score, interval, signals, evidence
GET  /api/companies/{id}/history          every period, with the range expected at the time
GET  /api/companies/{id}/signals
POST /api/companies/{id}/review          record a decision
GET  /api/companies/{id}/reviews
GET  /api/companies/{id}/audit-history
GET  /api/data-quality                   what the platform can and cannot see
GET  /api/climate-impact                 tonnage, contribution, emissions, collectors
GET  /api/cop31/pilot                    the pilot as configured
POST /api/cop31/pilot/run                execute and record a run
GET  /api/transparency                   scope, principles, policy, engines
POST /api/scoring/run                    rescore a period
GET  /api/scoring/engines
GET  /api/scoring/policy    PUT to change thresholds and weights
GET  /api/audit/events                   the decision log
GET  /api/audit/verify                   recompute every link in the chain
GET  /api/meta/reference                 filter values and labels
```

---

## The audit trail

Decisions are appended, never edited. Each event carries the SHA-256 digest of
the event before it, over the company, the auditor, the action, the statuses
either side of it, the note and the timestamp. Altering or removing a past
decision changes its digest and every link after it, and `/api/audit/verify`
reports the first sequence number where the chain stops agreeing with itself.

---

## The dataset

The seed is synthetic but the behaviour is not invented. Every company is
generated from one of a handful of filing patterns inspection teams actually
see — compliant, drifting, frozen, consistently under, lapsed, unregistered —
and the inputs a real feed would sometimes be missing are missing here too, for
a realistic share of companies. A platform that has only ever seen complete
records is untested.

224 companies, ten quarters, all of them scored, so the history view can show a
declaration against the range that was expected of it at the time.
"# gussourcecode" 
