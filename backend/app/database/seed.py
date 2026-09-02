"""Reference dataset.

The figures are synthetic but the behaviour is not invented: each company is
generated from one of a handful of declaration patterns that inspection teams
actually see, and the anomalies the engine is supposed to catch are planted
deliberately rather than sprinkled at random. Anything a real feed would
sometimes be missing is missing here too, for a realistic share of companies,
because a platform that has only ever seen complete records is untested.

Run directly to rebuild:

    python -m app.database.seed --reset
"""

from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.database import Base, SessionLocal, create_all, engine
from app.models import (
    AuditReview,
    CollectorProgram,
    Company,
    Declaration,
    FieldObservation,
    GtipLine,
)
from app.reference import (
    REGIONS,
    SECTOR_ORDER,
    SECTORS,
    SIZE_PRODUCTION_RANGE,
)
from app.services.audit_chain import append_event, new_decision_id

PERIODS = [
    "2024Q1", "2024Q2", "2024Q3", "2024Q4",
    "2025Q1", "2025Q2", "2025Q3", "2025Q4",
    "2026Q1", "2026Q2",
]

COMPANY_COUNT = 224

# Antalya is over-weighted because it carries the pilot.
REGION_WEIGHTS = {
    "Antalya": 24,
    "İstanbul": 16,
    "İzmir": 10,
    "Bursa": 8,
    "Kocaeli": 7,
    "Ankara": 7,
    "Konya": 5,
    "Gaziantep": 5,
    "Adana": 4,
    "Mersin": 4,
    "Denizli": 3,
    "Manisa": 3,
    "Kayseri": 2,
    "Tekirdağ": 1,
    "Samsun": 1,
}

NAME_PREFIX = [
    "Akdeniz", "Ege", "Marmara", "Anadolu", "Toros", "Karadeniz", "Trakya",
    "Çukurova", "Kapadokya", "Boğaziçi", "Yıldız", "Birlik", "Zirve", "Altın",
    "Güneş", "Deniz", "Beyaz", "Mavi", "Kristal", "Sedef", "Duru", "Berrak",
    "Özgür", "Safir", "Meridyen", "Tunca", "Pamir", "Aksu", "Lidya", "Efes",
    "Bereket", "Şelale", "Karya", "Nar", "Zeytin", "Sirius", "Arven", "Kübra",
]

NAME_CORE = {
    "beverage": ["İçecek", "Meşrubat", "Su", "Meyve Suyu"],
    "food": ["Gıda", "Un Mamulleri", "Süt", "Konserve"],
    "cosmetics": ["Kozmetik", "Kişisel Bakım", "Parfümeri"],
    "cleaning": ["Temizlik", "Deterjan", "Hijyen"],
    "pharma": ["İlaç", "Medikal", "Farma"],
    "electronics": ["Elektronik", "Elektrik", "Beyaz Eşya"],
    "textile": ["Tekstil", "Konfeksiyon", "Dokuma"],
    "chemicals": ["Kimya", "Boya", "Endüstri"],
    "agriculture": ["Tarım", "Sera", "Zirai Ürün"],
    "construction": ["Yapı", "İnşaat Malzemeleri", "Seramik"],
}

NAME_SUFFIX = [
    "Sanayi ve Ticaret A.Ş.",
    "San. Tic. Ltd. Şti.",
    "A.Ş.",
    "Üretim ve Pazarlama A.Ş.",
    "Ltd. Şti.",
    "Sanayi A.Ş.",
]

AUDITORS = [
    ("aydin.m", "M. Aydın"),
    ("korkmaz.s", "S. Korkmaz"),
    ("demir.e", "E. Demir"),
    ("yilmaz.b", "B. Yılmaz"),
    ("cetin.o", "O. Çetin"),
]

FIELD_NOTES_LOW = [
    "Warehouse pallet count did not match the quarterly filing.",
    "Filling line records showed a higher output than the amount declared.",
    "Two packaging suppliers invoiced volumes absent from the filing.",
    "Stock movement records covered material not present in the declaration.",
]

FIELD_NOTES_OK = [
    "Stock records reconciled with the filing for the period.",
    "Supplier invoices matched the declared amount.",
    "No discrepancy found between line output and the filing.",
]

# Declaration patterns. Shares are approximate, the generator draws against them.
PROFILES = [
    ("compliant", 0.50),
    ("drifting", 0.15),
    ("frozen", 0.11),
    ("under", 0.13),
    ("lapsed", 0.025),
    ("unregistered", 0.025),
    ("over", 0.06),
]


def _weighted_choice(rng: random.Random, options: dict[str, int]) -> str:
    total = sum(options.values())
    pick = rng.uniform(0, total)
    upto = 0.0
    for key, weight in options.items():
        upto += weight
        if pick <= upto:
            return key
    return next(iter(options))


def _profile(rng: random.Random) -> str:
    pick = rng.random()
    upto = 0.0
    for name, share in PROFILES:
        upto += share
        if pick <= upto:
            return name
    return "compliant"


def _company_name(rng: random.Random, sector: str, used: set[str]) -> str:
    for _ in range(60):
        name = f"{rng.choice(NAME_PREFIX)} {rng.choice(NAME_CORE[sector])} {rng.choice(NAME_SUFFIX)}"
        if name not in used:
            used.add(name)
            return name
    name = f"{rng.choice(NAME_PREFIX)} {rng.choice(NAME_CORE[sector])} {len(used)}"
    used.add(name)
    return name


def _quarter_index(period: str) -> int:
    return int(period[5]) - 1


def _period_end(period: str) -> datetime:
    year = int(period[:4])
    quarter = int(period[5])
    month = quarter * 3
    day = 31 if month in (3, 12) else 30
    return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #


def _build_company(rng: random.Random, index: int, used_names: set[str]) -> dict:
    sector = rng.choice(SECTOR_ORDER)
    region = _weighted_choice(rng, REGION_WEIGHTS)
    size = rng.choices(["MICRO", "SMALL", "MEDIUM", "LARGE"], weights=[16, 34, 33, 17])[0]
    profile = _profile(rng)

    low, high = SIZE_PRODUCTION_RANGE[size]
    quarterly_base = rng.uniform(low, high) / 4.0

    # Companies that freeze their filing are given real growth, so the gap
    # between output and declaration is the thing that opens up.
    if profile in ("frozen", "drifting"):
        trend = rng.uniform(0.035, 0.095)
    else:
        trend = rng.uniform(-0.015, 0.045)

    importer = rng.random() < 0.38
    import_ratio = rng.uniform(0.18, 0.95) if importer else rng.uniform(0.0, 0.06)

    has_import_data = rng.random() > 0.12
    has_gtip_data = rng.random() > 0.14
    gtip_coverage = rng.choice([1.0, 0.92, 0.84, 0.71, 0.58, 0.42, 0.28]) if has_gtip_data else 0.0
    has_field_data = rng.random() < 0.24

    history_length = len(PERIODS)
    if rng.random() < 0.10:
        history_length = rng.choice([3, 4, 5])

    return {
        "index": index,
        "sector": sector,
        "region": region,
        "size": size,
        "profile": profile,
        "name": _company_name(rng, sector, used_names),
        "tax_identifier": f"{rng.randint(1000000000, 9999999999)}",
        "quarterly_base": quarterly_base,
        "trend": trend,
        "import_ratio": import_ratio,
        "design_factor": rng.uniform(0.86, 1.16),
        "has_import_data": has_import_data,
        "has_gtip_data": has_gtip_data,
        "gtip_coverage": gtip_coverage,
        "has_field_data": has_field_data,
        "history_length": history_length,
        "rounds_numbers": rng.random() < 0.15,
        "repeats_figure": rng.random() < 0.09,
        "under_factor": rng.uniform(0.36, 0.62),
        "freshness_days": rng.choice([3, 9, 14, 21, 34, 48, 70, 120, 190, 260, 340]),
        "seasonal_amplitude": rng.uniform(0.03, 0.14),
    }


def _series(rng: random.Random, spec: dict) -> list[dict]:
    """Ten quarters of output, and the amount the company chose to declare."""
    sector = SECTORS[spec["sector"]]
    coefficient = sector["packaging_per_production"]
    import_coefficient = sector["packaging_per_import"]
    periods = PERIODS[-spec["history_length"] :]

    rows: list[dict] = []
    frozen_value: float | None = None
    repeat_value: float | None = None

    for offset, period in enumerate(periods):
        age = len(periods) - 1 - offset
        seasonal = 1 + spec["seasonal_amplitude"] * math.sin((_quarter_index(period) / 4) * 2 * math.pi)
        production = (
            spec["quarterly_base"]
            * ((1 + spec["trend"]) ** offset)
            * seasonal
            * rng.uniform(0.965, 1.035)
        )
        imports = production * spec["import_ratio"] * rng.uniform(0.9, 1.1)
        exports = production * rng.uniform(0.0, 0.28)

        true_packaging = (
            production * coefficient + imports * import_coefficient
        ) * spec["design_factor"]

        profile = spec["profile"]
        declared: float | None

        if profile == "unregistered":
            declared = None
        elif profile == "lapsed" and age < 2:
            declared = None
        elif profile == "compliant":
            declared = true_packaging * rng.uniform(0.95, 1.05)
        elif profile == "over":
            declared = true_packaging * rng.uniform(1.06, 1.24)
        elif profile == "under":
            declared = true_packaging * spec["under_factor"] * rng.uniform(0.96, 1.04)
        elif profile == "drifting":
            decay = max(0.42, 1.0 - 0.055 * offset)
            declared = true_packaging * decay * rng.uniform(0.97, 1.03)
        elif profile == "frozen":
            if frozen_value is None:
                frozen_value = true_packaging * rng.uniform(0.96, 1.02)
            declared = frozen_value * rng.uniform(0.985, 1.015)
        else:
            declared = true_packaging

        if declared is not None:
            if spec["repeats_figure"]:
                if repeat_value is None:
                    repeat_value = round(declared / 5) * 5
                if rng.random() < 0.55:
                    declared = repeat_value
            if spec["rounds_numbers"]:
                declared = max(5.0, round(declared / 5) * 5)

        rows.append(
            {
                "period": period,
                "production": round(production, 2),
                "imports": round(imports, 2) if spec["has_import_data"] else None,
                "exports": round(exports, 2),
                "declared": round(declared, 2) if declared is not None else None,
                "true_packaging": round(true_packaging, 2),
            }
        )

    return rows


def _material_breakdown(sector_key: str, tonnage: float) -> dict[str, float]:
    return {
        material: round(tonnage * share, 2)
        for material, share in SECTORS[sector_key]["material_mix"].items()
    }


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #


def seed(db: Session, *, verbose: bool = True) -> dict[str, int]:
    settings = get_settings()
    rng = random.Random(settings.seed_random_state)
    now = datetime.now(timezone.utc)

    used_names: set[str] = set()
    counts = {"companies": 0, "declarations": 0, "gtip_lines": 0, "observations": 0, "reviews": 0}

    for index in range(COMPANY_COUNT):
        spec = _build_company(rng, index, used_names)
        rows = _series(rng, spec)
        sector = SECTORS[spec["sector"]]

        registry_status = "UNREGISTERED" if spec["profile"] == "unregistered" else (
            "PARTIAL" if rng.random() < 0.06 else "MATCHED"
        )

        company = Company(
            company_name=spec["name"],
            tax_identifier=spec["tax_identifier"],
            sector=spec["sector"],
            region=spec["region"],
            company_size=spec["size"],
            registry_status=registry_status,
            has_production_data=True,
            has_import_data=spec["has_import_data"],
            has_gtip_data=spec["has_gtip_data"],
            has_field_data=spec["has_field_data"],
            gtip_coverage=spec["gtip_coverage"],
            last_data_update=now - timedelta(days=spec["freshness_days"]),
        )
        db.add(company)
        db.flush()
        counts["companies"] += 1

        for row in rows:
            declared = row["declared"]
            db.add(
                Declaration(
                    company_id=company.id,
                    period=row["period"],
                    declared_packaging_tonnage=declared,
                    production_volume=row["production"],
                    import_volume=row["imports"],
                    export_volume=row["exports"],
                    material_breakdown=_material_breakdown(spec["sector"], declared) if declared else None,
                    submitted_at=_period_end(row["period"]) + timedelta(days=rng.randint(12, 40))
                    if declared is not None
                    else None,
                )
            )
            counts["declarations"] += 1

            if spec["has_gtip_data"] and spec["gtip_coverage"] > 0:
                families = sector["gtip_families"]
                line_count = min(len(families), rng.randint(2, 4))
                covered = row["production"] * spec["gtip_coverage"]
                shares = [rng.uniform(0.5, 1.5) for _ in range(line_count)]
                total_share = sum(shares)
                for family, share in zip(families[:line_count], shares):
                    db.add(
                        GtipLine(
                            company_id=company.id,
                            period=row["period"],
                            gtip_code=f"{family}.{rng.randint(10, 99)}.{rng.randint(10, 99)}",
                            description=f"{sector['name']} line {family}",
                            quantity_tonnes=round(covered * share / total_share, 2),
                            packaging_coefficient=round(
                                sector["packaging_per_production"]
                                * spec["design_factor"]
                                * rng.uniform(0.94, 1.06),
                                5,
                            ),
                        )
                    )
                    counts["gtip_lines"] += 1

        if spec["has_field_data"]:
            visits = rng.randint(1, 2)
            for row in rng.sample(rows[-4:], min(visits, len(rows[-4:]))):
                if row["declared"] is None:
                    observed = row["true_packaging"] * rng.uniform(0.92, 1.05)
                    note = "No filing on record for the period covered by the visit."
                elif row["declared"] < row["true_packaging"] * 0.8:
                    observed = row["true_packaging"] * rng.uniform(0.88, 1.04)
                    note = rng.choice(FIELD_NOTES_LOW)
                else:
                    observed = row["declared"] * rng.uniform(0.97, 1.07)
                    note = rng.choice(FIELD_NOTES_OK)
                db.add(
                    FieldObservation(
                        company_id=company.id,
                        period=row["period"],
                        observed_packaging_tonnage=round(observed, 2),
                        observation=note,
                        inspector=rng.choice(AUDITORS)[1],
                        observed_at=_period_end(row["period"]) + timedelta(days=rng.randint(20, 90)),
                    )
                )
                counts["observations"] += 1

    db.commit()
    if verbose:
        print(f"  companies      {counts['companies']}")
        print(f"  declarations   {counts['declarations']}")
        print(f"  gtip lines     {counts['gtip_lines']}")
        print(f"  observations   {counts['observations']}")
    return counts


def seed_reviews(db: Session, *, verbose: bool = True) -> int:
    """Give the queue a history, so the workflow is not starting from empty."""
    settings = get_settings()
    rng = random.Random(settings.seed_random_state + 7)
    now = datetime.now(timezone.utc)

    from app.models import ScoreResult

    ranked = db.execute(
        select(Company, ScoreResult)
        .join(ScoreResult, ScoreResult.company_id == Company.id)
        .where(ScoreResult.period == PERIODS[-1])
        .order_by(ScoreResult.priority_score.desc())
    ).all()

    handled = 0
    for position, (company, score) in enumerate(ranked):
        # Teams work the top of the queue, so that is where decisions exist,
        # and that is also where inspections have had time to close.
        chance = 0.76 if position < 60 else 0.34 if position < 130 else 0.10
        if rng.random() > chance:
            continue

        auditor_id, _ = rng.choice(AUDITORS)
        weights = [22, 15, 9, 44, 10] if position < 60 else [28, 21, 13, 24, 14]
        status = rng.choices(
            [
                "MARKED_FOR_INSPECTION",
                "UNDER_REVIEW",
                "INFORMATION_REQUESTED",
                "INSPECTION_COMPLETED",
                "NO_ACTION_REQUIRED",
            ],
            weights=weights,
        )[0]

        confirmed = None
        if status == "INSPECTION_COMPLETED" and score.shortfall_tonnage > 0:
            confirmed = round(score.shortfall_tonnage * rng.uniform(0.55, 1.15), 2)

        opened = now - timedelta(days=rng.randint(4, 120))
        decision_id = new_decision_id()

        db.add(
            AuditReview(
                company_id=company.id,
                status=status,
                auditor_id=auditor_id,
                notes=None,
                decision_id=decision_id,
                confirmed_additional_tonnage=confirmed,
                created_at=opened,
                updated_at=opened + timedelta(days=rng.randint(0, 20)),
            )
        )
        append_event(
            db,
            company_id=company.id,
            user_id=auditor_id,
            action="STATUS_CHANGE",
            previous_status="AWAITING_REVIEW",
            new_status=status,
            notes=None,
            decision_id=decision_id,
            event_data={
                "priority_score": score.priority_score,
                "priority_level": score.priority_level,
                "period": score.period,
                "confirmed_additional_tonnage": confirmed,
            },
            created_at=opened,
        )
        handled += 1

    db.commit()
    if verbose:
        print(f"  reviews        {handled}")
    return handled


MUNICIPALITIES = [
    ("Muratpaşa", "Antalya"),
    ("Kepez", "Antalya"),
    ("Konyaaltı", "Antalya"),
    ("Alanya", "Antalya"),
    ("Manavgat", "Antalya"),
    ("Kartal", "İstanbul"),
    ("Bornova", "İzmir"),
    ("Nilüfer", "Bursa"),
    ("Gebze", "Kocaeli"),
    ("Seyhan", "Adana"),
]


def seed_social(db: Session, *, verbose: bool = True) -> int:
    settings = get_settings()
    rng = random.Random(settings.seed_random_state + 19)
    written = 0

    # A pilot, deliberately: two quarters across the participating districts.
    for period in PERIODS[-2:]:
        for municipality, region in MUNICIPALITIES:
            # Pilot scale on purpose. A quarter of one province's recovered
            # contribution funds a handful of insured posts, not hundreds, and
            # the dashboard is only honest if the seed says so.
            scale = 1.0 if region == "Antalya" else 0.5
            collectors = max(1, int(rng.uniform(2, 7) * scale))
            transitions = int(collectors * rng.uniform(0.3, 0.58))
            insured = transitions
            db.add(
                CollectorProgram(
                    municipality=municipality,
                    region=region,
                    period=period,
                    collectors_supported=collectors,
                    formal_transitions=transitions,
                    insured_workers=insured,
                    insured_days=insured * rng.randint(52, 64),
                    funding_allocated_try=round(transitions * rng.uniform(78_000, 94_000), 2),
                    note=None,
                )
            )
            written += 1

    db.commit()
    if verbose:
        print(f"  social records {written}")
    return written


def database_is_empty(db: Session) -> bool:
    return db.execute(select(func.count(Company.id))).scalar_one() == 0


def bootstrap(reset: bool = False, verbose: bool = True) -> None:
    """Build the database from nothing: schema, records, scores, decisions."""
    from app.services.scoring_service import run_scoring

    if reset:
        Base.metadata.drop_all(bind=engine)
    create_all()

    with SessionLocal() as db:
        if not database_is_empty(db):
            if verbose:
                print("Database already populated, nothing to do.")
            return

        if verbose:
            print("Seeding reference dataset")
        seed(db, verbose=verbose)

        # Every period is scored, not only the newest one: the history view
        # compares a declaration with the range that was expected at the time.
        if verbose:
            print(f"Scoring {len(PERIODS)} periods")
        for period in PERIODS:
            summary = run_scoring(db, period)
            if verbose and period == PERIODS[-1]:
                print(f"  current        {period}, {summary.companies_scored} companies")
                print(f"  levels         {summary.level_counts}")

        seed_reviews(db, verbose=verbose)
        seed_social(db, verbose=verbose)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the GUS-DEDEKTIV database")
    parser.add_argument("--reset", action="store_true", help="drop every table first")
    args = parser.parse_args()
    bootstrap(reset=args.reset)
