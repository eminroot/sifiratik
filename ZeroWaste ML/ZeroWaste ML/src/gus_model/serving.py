"""Teslim paketinden model yukleme.

Egitim kodu CALISTIRILMADAN, yalnizca `models/` altindaki dosyalardan calisan
bir model kurar. Iki isi var:

1. Paketin KENDINE YETERLI oldugunu kanitlar. `score_dataset.py` bu yolla
   skorlar ve sonuclarin egitim ici skorlarla ayni ciktigini dogrular; boyle
   bir tur-donus testi olmadan "backend ayni sonucu uretir" bir varsayimdir.
2. Backend'in `ml_scorer.py` icinde uyguladigi okuma sirasinin REFERANS
   uygulamasidir. Bir alan degisirse once burasi kirilir.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from .config import ModelConfig
from .conformal import ConformalCalibrator
from .pipeline import GusModel
from .quantile import BlendedExpectation, QuantileHead
from .risk import ProbabilityCalibrator, RiskModel, ScoreMap
from .signals import SignalScaler


def _read_json(path: Path) -> Dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_model(directory: Path) -> GusModel:
    directory = Path(directory)
    manifest = _read_json(directory / "manifest.json")
    calibration = _read_json(directory / "calibration.json")

    cfg = ModelConfig(
        seed=int(manifest.get("seed", 0)),
        model_version=str(manifest.get("version", "unknown")),
        target_coverage=float(manifest.get("target_coverage", 0.90)),
    )

    order = manifest["feature_order"]
    categories = manifest["categories"]
    fallback = manifest.get("anchor_fallback_log", {})

    model = GusModel(cfg)
    model.hist = QuantileHead.load(
        directory, "hist", order["hist"], categories["hist"], float(fallback.get("hist", 0.0))
    )
    model.peer = QuantileHead.load(
        directory, "peer", order["peer"], categories["peer"], float(fallback.get("peer", 0.0))
    )
    model.blend = BlendedExpectation(weight=float(calibration["blend"]["weight_hist"]))
    model.conformal = ConformalCalibrator.load(directory / "conformal.json")
    model.scaler = SignalScaler.load(directory / "signals.json")
    model.risk = RiskModel.load(
        directory / "risk_model.txt",
        order["risk"],
        categories["risk"],
        members=len(manifest.get("risk_members", ["risk_model.txt"])),
    )
    model.probability = ProbabilityCalibrator.from_dict(calibration["probability"])
    model.score_map = ScoreMap.from_dict(calibration["score_map"])
    model.data_version = str(manifest.get("data_version", "unknown"))
    return model


__all__ = ["load_model"]
