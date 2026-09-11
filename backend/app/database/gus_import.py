"""Loading the GÜS-DEDEKTİV panel into the operational database.

The platform holds no invented records. Every company, declaration, product
tree entry and inspection result comes from the panel the model was trained
and evaluated on, so a figure on any screen can be traced back through the
model card to the row it came from.

    firms.csv               -> companies
    observations.csv        -> declarations, and the field observation on each
    product_packaging.csv   -> the product tree behind each declaration
    audit_labels.csv        -> closed inspections, for the periods that have
                               been worked

What is deliberately *not* imported is the ground truth for the open period.
`audit_labels.csv` knows the answer for every row; an operational system does
not, and a queue built against a table that does would be a demonstration of
nothing. Only inspections that have closed are loaded, and only for periods
before the one being worked. The current period is scored blind.

The panel is synthetic. That is stated on the interface rather than hidden:
these are calibrated records, not real declarations, and no figure computed
from them is evidence about a real company.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.database import Base, SessionLocal, create_all, engine
from app.models import (
    AuditReview,
    Company,
    Declaration,
    FieldObservation,
    GtipLine,
)
from app.reference import MATERIAL_ORDER, region_label
from app.services.audit_chain import append_event, new_decision_id

# The period the queue is worked on. Everything after it is unseen; closed
# inspections are only loaded for periods strictly before it.
CURRENT_PERIOD = "2026Q2"

# Inspectors who signed the closed inspections. Names are labels on a
# synthetic record, not people.
AUDITORS = [
    ("aydin.m", "Aydın M."),
    ("kaya.s", "Kaya S."),
    ("demir.e", "Demir E."),
    ("yilmaz.b", "Yılmaz B."),
    ("ozturk.f", "Öztürk F."),
]

# How the panel's inspection outcome maps onto the workflow the interface
# shows. Only closed outcomes appear: the panel records what an inspection
# found, which is knowledge a team only has once it has been there.
OUTCOME_STATUS = {
    "dogrulandi_eksik_beyan": "INSPECTION_COMPLETED",
    "kismi_dogrulandi": "INSPECTION_COMPLETED",
    "aciklandi_uygun": "NO_ACTION_REQUIRED",
    "bulgu_yok": "NO_ACTION_REQUIRED",
    "veri_incelemesi_gerekli": "INFORMATION_REQUESTED",
}

OUTCOME_NOTE = {
    "dogrulandi_eksik_beyan": "Inspection confirmed an under-declaration. Corrected tonnage recorded.",
    "kismi_dogrulandi": "Inspection confirmed part of the shortfall. Corrected tonnage recorded.",
    "aciklandi_uygun": "The company explained the movement and the explanation held. No further action.",
    "bulgu_yok": "Inspection found nothing to correct.",
    "veri_incelemesi_gerekli": "Critical fields were missing. Information requested before any assessment.",
}


class PanelMissing(RuntimeError):
    """The GÜS panel could not be found."""


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


def _panel_dir() -> Path:
    directory = Path(get_settings().panel_dir)
    if not directory.is_absolute():
        # app/database/gus_import.py -> app -> backend -> repository root
        directory = (Path(__file__).resolve().parents[3] / directory).resolve()
    if not (directory / "observations.csv").exists():
        raise PanelMissing(
            f"The GÜS panel is not at {directory}. Generate it with "
            "`python src/generate_dataset.py` in the model repository, or point "
            "PANEL_DIR at the directory holding observations.csv."
        )
    return directory


def _read(directory: Path, name: str) -> list[dict[str, str]]:
    with (directory / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def _float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _int(value: str | None) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "evet"}


def _period_end(period: str) -> datetime:
    year, quarter = int(period[:4]), int(period[5:])
    month = quarter * 3
    day = 30 if month in (6, 9) else 31
    return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)


def _before(period: str, limit: str) -> bool:
    return period < limit


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


def import_panel(db: Session, *, verbose: bool = True) -> dict[str, int]:
    directory = _panel_dir()
    firms = _read(directory, "firms.csv")
    observations = _read(directory, "observations.csv")
    packaging = _read(directory, "product_packaging.csv")
    labels = {row["observation_id"]: row for row in _read(directory, "audit_labels.csv")}

    by_firm: dict[str, list[dict]] = defaultdict(list)
    for row in observations:
        by_firm[row["firm_id"]].append(row)
    for rows in by_firm.values():
        rows.sort(key=lambda item: item["period"])

    skus: dict[str, list[dict]] = defaultdict(list)
    for row in packaging:
        skus[row["firm_id"]].append(row)

    counts = {
        "companies": 0,
        "declarations": 0,
        "product_tree_lines": 0,
        "field_observations": 0,
        "closed_inspections": 0,
    }
    company_ids: dict[str, int] = {}

    for firm in firms:
        firm_id = firm["firm_id"]
        rows = by_firm.get(firm_id, [])
        if not rows:
            continue

        company = _company(firm, rows)
        db.add(company)
        db.flush()
        company_ids[firm_id] = company.id
        counts["companies"] += 1

        for row in rows:
            db.add(_declaration(company.id, row))
            counts["declarations"] += 1

            observed = _float(row.get("external_evidence_tonnage"))
            if observed is not None:
                db.add(_field_observation(company.id, row, observed))
                counts["field_observations"] += 1

            counts["product_tree_lines"] += _add_product_tree(
                db, company.id, row, skus.get(firm_id, [])
            )

    db.commit()
    if verbose:
        print(f"  {counts['companies']} companies, {counts['declarations']} declarations")

    counts["closed_inspections"] = _import_closed_inspections(
        db, observations, labels, company_ids, verbose=verbose
    )
    return counts


def _company(firm: dict, rows: list[dict]) -> Company:
    coverage = _float(firm.get("bom_coverage_ratio")) or 0.0
    has_production = any(_float(r.get("production_qty")) is not None for r in rows)
    has_import = any(_float(r.get("import_qty")) is not None for r in rows)
    has_field = any(_float(r.get("external_evidence_tonnage")) is not None for r in rows)
    latest = rows[-1]

    # A registered sector code that does not match what the company actually
    # makes is a known cause of a wrong peer comparison, so it is carried as a
    # registry state rather than silently corrected.
    registry_status = "SECTOR_MISMATCH" if _bool(firm.get("sector_code_error_flag")) else "MATCHED"

    return Company(
        # Identity stays tokenised. The panel's firm token is the identifier,
        # and it is also what the interface displays: there is no real name to
        # show and inventing one would put a fiction on every screen.
        company_name=firm["firm_id"],
        tax_identifier=firm["firm_id"],
        sector=firm["sector"],
        region=region_label(firm["province"]),
        company_size=firm["size_band"],
        nace_code=firm.get("nace_code"),
        main_product_group=firm.get("main_product_group"),
        primary_packaging_material=firm.get("primary_packaging_material"),
        operating_since=_int(firm.get("operating_since")),
        weight_matrix_vintage_year=_int(firm.get("bom_matrix_vintage_year")),
        data_maturity_score=_float(firm.get("data_maturity_score")),
        registry_status=registry_status,
        has_production_data=has_production,
        has_import_data=has_import,
        has_gtip_data=coverage > 0.05,
        has_field_data=has_field,
        gtip_coverage=coverage,
        last_data_update=_period_end(latest["period"])
        - timedelta(days=_int(latest.get("data_freshness_days")) or 0),
    )


def _declaration(company_id: int, row: dict) -> Declaration:
    breakdown = {
        material: _float(row.get(f"declared_ton_{material}")) or 0.0
        for material in MATERIAL_ORDER
    }
    return Declaration(
        company_id=company_id,
        period=row["period"],
        declared_packaging_tonnage=_float(row.get("declared_packaging_tonnage")),
        production_volume=_float(row.get("production_qty")),
        import_volume=_float(row.get("import_qty")),
        export_volume=_float(row.get("export_qty")),
        return_volume=_float(row.get("return_qty")),
        material_breakdown={k: v for k, v in breakdown.items() if v > 0} or None,
        correction_volume=_float(row.get("correction_qty")),
        exemption_flag=_bool(row.get("exemption_flag")),
        exempt_share=_float(row.get("exempt_share")),
        bom_expected_tonnage=_float(row.get("bom_expected_tonnage_observable")),
        bom_coverage_ratio=_float(row.get("bom_coverage_ratio")),
        gekap_amount_try=_float(row.get("gekap_amount_try")),
        gekap_rate_status=row.get("gekap_rate_status") or None,
        data_quality_score=_float(row.get("data_quality_score")),
        data_freshness_days=_int(row.get("data_freshness_days")),
        missing_fields=row.get("missing_fields") or None,
        submitted_at=_period_end(row["period"]) + timedelta(days=28),
    )


def _field_observation(company_id: int, row: dict, observed: float) -> FieldObservation:
    source = row.get("external_evidence_source") or "External verification record"
    return FieldObservation(
        company_id=company_id,
        period=row["period"],
        observed_packaging_tonnage=round(observed, 3),
        observation=source,
        inspector=AUDITORS[hash(row["firm_id"]) % len(AUDITORS)][1],
        observed_at=_period_end(row["period"]),
    )


def _add_product_tree(
    db: Session, company_id: int, row: dict, skus: list[dict]
) -> int:
    """One line per SKU, scaled so the lines sum to the registered expectation.

    The panel records the tonnage the product tree implies for the part of the
    range that is registered. The per-SKU weights carry the shape of that
    figure; scaling them to the recorded total keeps both, so the interface can
    show which entries drive the expectation without the total drifting from
    what the register actually says.
    """
    expected = _float(row.get("bom_expected_tonnage_observable"))
    production = _float(row.get("production_qty"))
    if expected is None or not production or not skus:
        return 0

    weights = []
    for sku in skus:
        share = _float(sku.get("sku_volume_share")) or 0.0
        grams = _float(sku.get("unit_pack_weight_g_recorded")) or 0.0
        weights.append(share * grams)
    total = sum(weights)
    if total <= 0:
        return 0

    written = 0
    for sku, weight in zip(skus, weights):
        if weight <= 0:
            continue
        share = _float(sku.get("sku_volume_share")) or 0.0
        quantity = production * share
        if quantity <= 0:
            continue
        # Coefficient is packaging tonnes per unit of this product line.
        coefficient = expected * (weight / total) / quantity
        db.add(
            GtipLine(
                company_id=company_id,
                period=row["period"],
                gtip_code=str(sku.get("gtip6_context") or "")[:12],
                description=(
                    f"{sku.get('pack_format') or sku.get('product_group') or 'Packaging line'}"
                )[:160],
                quantity_tonnes=round(quantity, 3),
                packaging_coefficient=round(coefficient, 9),
            )
        )
        written += 1
    return written


def _import_closed_inspections(
    db: Session,
    observations: list[dict],
    labels: dict[str, dict],
    company_ids: dict[str, int],
    *,
    verbose: bool = True,
) -> int:
    """Inspections that have already closed, for periods already worked.

    A company's standing is its most recent closed inspection. Nothing is
    loaded for the current period: that is the queue, and its answers are not
    known yet.
    """
    latest: dict[int, tuple[str, dict, dict]] = {}
    for row in observations:
        if not _before(row["period"], CURRENT_PERIOD):
            continue
        company_id = company_ids.get(row["firm_id"])
        label = labels.get(row["observation_id"])
        if company_id is None or label is None:
            continue
        if label["audit_outcome"] not in OUTCOME_STATUS:
            continue
        # Only a share of past filings were ever inspected; the panel marks
        # those by recording an outcome other than "nothing found" or by the
        # record having been queued for missing data.
        if label["audit_outcome"] == "bulgu_yok" and label["truth_anomaly_flag"] != "1":
            if hash(row["observation_id"]) % 100 >= 12:
                continue
        current = latest.get(company_id)
        if current is None or row["period"] > current[0]:
            latest[company_id] = (row["period"], row, label)

    written = 0
    for company_id, (period, row, label) in sorted(latest.items()):
        status = OUTCOME_STATUS[label["audit_outcome"]]
        auditor_id, _ = AUDITORS[company_id % len(AUDITORS)]
        confirmed = _float(label.get("confirmed_correction_tonnage")) or 0.0
        closed_at = _period_end(period) + timedelta(days=_int(label.get("inspection_duration_days")) or 10)

        note = OUTCOME_NOTE[label["audit_outcome"]]
        cause = label.get("legitimate_cause")
        if cause:
            note = f"{note} Recorded cause: {cause}."

        decision_id = new_decision_id()
        db.add(
            AuditReview(
                company_id=company_id,
                period=period,
                status=status,
                auditor_id=auditor_id,
                notes=note,
                decision_id=decision_id,
                confirmed_additional_tonnage=round(confirmed, 3) if confirmed > 0 else None,
                created_at=closed_at,
                updated_at=closed_at,
            )
        )
        append_event(
            db,
            company_id=company_id,
            user_id=auditor_id,
            action="REVIEW_CLOSED",
            previous_status="UNDER_REVIEW",
            new_status=status,
            notes=note,
            decision_id=decision_id,
            event_data={
                "period": period,
                "outcome": label["audit_outcome"],
                "confirmed_additional_tonnage": round(confirmed, 3),
                "inspection_duration_days": _int(label.get("inspection_duration_days")),
                "label_confidence": label.get("label_confidence"),
            },
            created_at=closed_at,
        )
        written += 1

    db.commit()
    if verbose:
        print(f"  {written} closed inspections")
    return written


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #


def database_is_empty(db: Session) -> bool:
    return db.execute(select(Company.id).limit(1)).scalar_one_or_none() is None


def bootstrap(reset: bool = False, verbose: bool = True) -> None:
    """Build the database from the panel, then score every period."""
    if reset:
        Base.metadata.drop_all(bind=engine)
    create_all()

    db = SessionLocal()
    try:
        if not database_is_empty(db) and not reset:
            return
        if verbose:
            print(f"Importing the GÜS panel from {_panel_dir()}")
        counts = import_panel(db, verbose=verbose)

        from app.services.scoring_service import all_periods, run_scoring

        periods = all_periods(db)
        if verbose:
            print(f"Scoring {len(periods)} periods")
        for period in periods:
            summary = run_scoring(db, period)
            if verbose:
                print(
                    f"  {period}: {summary.companies_scored} scored by "
                    f"{summary.engine} in {summary.duration_ms} ms"
                )
        if verbose:
            print(
                "Done. "
                + ", ".join(f"{value} {key}" for key, value in counts.items())
            )
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import the GÜS panel")
    parser.add_argument("--reset", action="store_true", help="drop every table first")
    args = parser.parse_args()
    bootstrap(reset=args.reset, verbose=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
