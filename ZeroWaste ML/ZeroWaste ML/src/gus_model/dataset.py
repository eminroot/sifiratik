"""Dataset yukleme, bolumleme ve sizinti nobeti.

Bu modul `gus_generator.anomalies` modulunu ITHAL ETMEZ. Etiketlere yalnizca
uretilmis `audit_labels` tablosu uzerinden, yalnizca `truth_anomaly_flag` ve
degerlendirme alanlari icin erisir; hicbir etiket alani ozellik matrisine
girmez. Bu kural `assert_no_label_leakage` ile calisma aninda dogrulanir.

BOLUMLEME
---------
    history  2023Q1-2023Q4   ozellik burn-in; varsayilan olarak EGITIME GIRMEZ
    train    2024Q1-2025Q2   model uydurma
    valid    2025Q3-2025Q4   -> firma bazinda ikiye ayrilir
        valid_a             erken durdurma, harman agirligi, model secimi
        valid_b             konformal kalibrasyon, olasilik kalibrasyonu, puan haritasi
    test     2026Q1-2026Q2   BIR KEZ raporlanir

valid'in firma bazinda ikiye ayrilmasinin nedeni: ayni 1200 satiri hem erken
durdurma hem kalibrasyon icin kullanmak kalibrasyonu iyimser gosterir. Ayrim
donem bazinda degil FIRMA bazinda yapilir; boylece her iki yarida da iki
ceyrek birden temsil edilir.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config import ModelConfig

# Etiket tablosundan ozellik matrisine gecmesi YASAK olan her sey.
LABEL_COLUMNS = (
    "truth_anomaly_flag",
    "anomaly_type",
    "anomaly_type_aciklama",
    "legitimate_cause",
    "true_expected_tonnage",
    "true_deficit_ratio",
    "true_gap_tonnage",
    "confirmed_correction_tonnage",
    "audit_outcome",
    "audit_cost_try",
    "inspection_duration_days",
    "label_confidence",
)

TARGET = "truth_anomaly_flag"


@dataclass
class Splits:
    """Kayit kimliklerinin bolumlere dagilimi."""

    history: pd.Index
    train: pd.Index
    valid_a: pd.Index
    valid_b: pd.Index
    test: pd.Index

    @property
    def valid(self) -> pd.Index:
        return self.valid_a.union(self.valid_b)

    def summary(self) -> Dict[str, int]:
        return {
            "history": len(self.history),
            "train": len(self.train),
            "valid_a": len(self.valid_a),
            "valid_b": len(self.valid_b),
            "test": len(self.test),
        }


@dataclass
class Bundle:
    """Model katmanina giren her sey."""

    model_ready: pd.DataFrame          # ozellikler (ground truth ICERMEZ)
    labels: pd.DataFrame               # degerlendirme icin ground truth
    observations: pd.DataFrame         # denetciye gorunen ham gozlem
    firms: pd.DataFrame
    splits: Splits
    data_version: str

    @property
    def y(self) -> pd.Series:
        return self.labels[TARGET].astype(int)

    def rows(self, index: pd.Index) -> pd.DataFrame:
        return self.model_ready.loc[index]

    def target(self, index: pd.Index) -> np.ndarray:
        return self.y.loc[index].to_numpy()


def _read(data_dir: Path, name: str) -> pd.DataFrame:
    parquet = data_dir / f"{name}.parquet"
    if parquet.exists():
        return pd.read_parquet(parquet)
    csv = data_dir.parent / "csv" / f"{name}.csv"
    if csv.exists():
        return pd.read_csv(csv, sep=";", encoding="utf-8-sig")
    raise FileNotFoundError(
        f"{name} tablosu bulunamadi. Once `python src/generate_dataset.py` calistirin. "
        f"Bakilan yerler: {parquet}, {csv}"
    )


def _firm_half(firm_id: str, seed: int) -> int:
    """Firma kimligini deterministik olarak 0/1 yarisina atar."""
    digest = hashlib.sha256(f"{seed}:{firm_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 2


def _valid_halves(
    valid_rows: pd.DataFrame,
    labels: Optional[pd.DataFrame],
    seed: int,
) -> pd.Series:
    """valid bolumunu FIRMA bazinda, pozitif sayisi dengeli ikiye ayirir.

    Duz hash ile bolmek 1200 satirda pozitifleri 25/67 gibi dagitabiliyor;
    25 pozitifle erken durdurma karari gurultuden ibaret olur. Bu nedenle
    firmalar once "valid penceresinde pozitifi var mi" katmanina ayrilir,
    her katman kendi icinde hash sirasina gore donusumlu dagitilir.

    Bu, TEST bolumune dokunmayan bir DOGRULAMA kumesi tasarim karari olarak
    alinmistir; model secimi yine yalnizca valid uzerinde yapilir.
    """
    firms = valid_rows["firm_id"].astype(str)
    if labels is None:
        return firms.map(lambda f: _firm_half(f, seed))

    positive = (
        labels.reindex(valid_rows.index)[TARGET].fillna(0).astype(int)
        .groupby(firms.to_numpy()).max()
    )
    assignment: Dict[str, int] = {}
    for stratum in (1, 0):
        members = sorted(
            positive.index[positive == stratum],
            key=lambda f: hashlib.sha256(f"{seed}:{f}".encode()).hexdigest(),
        )
        for position, firm in enumerate(members):
            assignment[str(firm)] = position % 2
    return firms.map(lambda f: assignment.get(f, _firm_half(f, seed)))


def load_bundle(cfg: Optional[ModelConfig] = None, root: Optional[Path] = None) -> Bundle:
    cfg = cfg or ModelConfig()
    root = Path(root or Path.cwd())
    data_dir = root / cfg.data_dir

    model_ready = _read(data_dir, "model_ready")
    labels = _read(data_dir, "audit_labels")
    observations = _read(data_dir, "observations")
    firms = _read(data_dir, "firms")

    for frame in (model_ready, labels, observations):
        frame.set_index("observation_id", inplace=True, drop=False)

    if not model_ready.index.equals(labels.index):
        labels = labels.reindex(model_ready.index)
    if labels[TARGET].isna().any():
        raise ValueError("Bazi gozlemlerin denetim etiketi yok.")

    assert_no_label_leakage(model_ready)

    splits = build_splits(model_ready, cfg, labels)

    manifest = root / "data" / "output" / "manifest.json"
    data_version = "unknown"
    if manifest.exists():
        import json

        data_version = json.loads(manifest.read_text(encoding="utf-8")).get(
            "dataset_version", "unknown"
        )

    return Bundle(
        model_ready=model_ready,
        labels=labels,
        observations=observations,
        firms=firms,
        splits=splits,
        data_version=data_version,
    )


def build_splits(
    model_ready: pd.DataFrame,
    cfg: ModelConfig,
    labels: Optional[pd.DataFrame] = None,
) -> Splits:
    split = model_ready["split"].astype(str)

    history = model_ready.index[split == "history"]
    train = model_ready.index[split == "train"]
    test = model_ready.index[split == "test"]

    valid_rows = model_ready.loc[split == "valid"]
    halves = _valid_halves(valid_rows, labels, cfg.seed)
    valid_a = valid_rows.index[halves == 0]
    valid_b = valid_rows.index[halves == 1]

    if cfg.train_on_history:
        usable = model_ready.loc[history]
        keep = usable.index[
            usable["f_active_signal_count"].fillna(0) >= cfg.history_min_signal_count
        ]
        train = train.union(keep).sort_values()

    return Splits(history=history, train=train, valid_a=valid_a, valid_b=valid_b, test=test)


def assert_no_label_leakage(model_ready: pd.DataFrame) -> None:
    """Ozellik tablosunda etiket kaynakli sutun olmadigini dogrular.

    `gus_generator.features` ayni kontrolu uretim aninda yapar; burada
    TEKRAR yapilir cunku model, dataset'i uretenden bagimsiz bir dosyadan
    da yuklenebilir.
    """
    present = [c for c in LABEL_COLUMNS if c in model_ready.columns]
    if present:
        raise AssertionError(
            "Ozellik tablosunda denetim etiketi sutunu bulundu: " + ", ".join(present)
        )
    forbidden = ("truth", "audit", "confirmed_", "legitimate", "true_")
    suspicious = [
        c for c in model_ready.columns if any(p in c.lower() for p in forbidden)
    ]
    if suspicious:
        raise AssertionError(
            "Ozellik tablosunda sizinti suphesi tasiyan sutun(lar): " + ", ".join(suspicious)
        )


def split_report(bundle: Bundle) -> pd.DataFrame:
    """Her bolumun buyuklugu, donemleri ve prevalansi."""
    rows: List[Dict] = []
    mapping = {
        "history": bundle.splits.history,
        "train": bundle.splits.train,
        "valid_a": bundle.splits.valid_a,
        "valid_b": bundle.splits.valid_b,
        "test": bundle.splits.test,
    }
    for name, index in mapping.items():
        if len(index) == 0:
            continue
        sub = bundle.model_ready.loc[index]
        y = bundle.target(index)
        rows.append({
            "bolum": name,
            "kayit": len(index),
            "firma": int(sub["firm_id"].nunique()),
            "donemler": ", ".join(sorted(sub["period"].astype(str).unique())),
            "pozitif": int(y.sum()),
            "prevalans": round(float(y.mean()), 4),
        })
    return pd.DataFrame(rows)


__all__ = [
    "Bundle",
    "Splits",
    "TARGET",
    "LABEL_COLUMNS",
    "load_bundle",
    "build_splits",
    "assert_no_label_leakage",
    "split_report",
]
