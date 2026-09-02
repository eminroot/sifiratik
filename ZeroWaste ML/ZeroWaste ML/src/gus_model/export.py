"""Backend teslim paketi.

Yazilan dosyalar `backend/app/scoring/ml_scorer.py` tarafindan okunur. Paket
kendi kendine yeterlidir: backend'in calismasi icin bu depodaki hicbir Python
moduluene ihtiyac yoktur, yalnizca lightgbm ve numpy gerekir.

    quantile_hist_q05.txt   tarihsel baslik, 5. yuzdelik
    quantile_hist_q50.txt   tarihsel baslik, ortanca
    quantile_hist_q95.txt   tarihsel baslik, 95. yuzdelik
    quantile_peer_q05.txt   emsal baslik, 5. yuzdelik
    quantile_peer_q50.txt   emsal baslik, ortanca
    quantile_peer_q95.txt   emsal baslik, 95. yuzdelik
    risk_model.txt          sinyal birlestirme (fusion) modeli
    conformal.json          Mondrian CQR genisletme paylari
    signals.json            sinyal rampa capalari + kullanilabilirlik kurallari
    calibration.json        harman agirligi, izotonik kalibrasyon, puan haritasi
    manifest.json           surum, tarih, ozellik sirasi, kategoriler, metrikler

`manifest.json` icindeki `feature_order` ve `categories` alanlari BAGLAYICIDIR:
backend ozellik matrisini bu siraya ve bu kategori duzeylerine gore kurar.
Aksi halde LightGBM sessizce yanlis sutunu okur.
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import lightgbm
import numpy as np
import pandas as pd

from .config import (
    POLICY_WEIGHTS,
    PRIORITY_BANDS,
    SIGNAL_ACTIVE_THRESHOLD,
    SIGNAL_SPECS,
    STRONGEST_SIGNAL_SHARE,
    ARTIFACT_SCHEMA_VERSION,
)
from .featureset import CATEGORICAL, LOG1P_COLUMNS, RISK_FEATURES
from .pipeline import GusModel
from .signals import STALE_MATRIX_MULTIPLIER

# Backend'in var olmasini bekledigi dosyalar. Fusion bir tohum toplulugu
# oldugu icin ek uyeler `risk_model_2.txt` ... olarak yazilir; kac uye
# oldugunu `manifest.json` icindeki `risk_members` soyler.
REQUIRED = (
    "quantile_hist_q05.txt", "quantile_hist_q50.txt", "quantile_hist_q95.txt",
    "quantile_peer_q05.txt", "quantile_peer_q50.txt", "quantile_peer_q95.txt",
    "risk_model.txt", "conformal.json", "signals.json", "calibration.json",
    "manifest.json",
)


def export(
    model: GusModel,
    directory: Path,
    metrics: Optional[Dict] = None,
    notes: Optional[List[str]] = None,
) -> Dict[str, str]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    if model.hist is None or model.peer is None or model.risk is None or model.conformal is None:
        raise RuntimeError("Egitilmemis model disa aktarilamaz.")

    model.hist.save(directory)
    model.peer.save(directory)
    risk_files = model.risk.save(directory / "risk_model.txt")
    model.conformal.save(directory / "conformal.json")
    model.scaler.save(directory / "signals.json")

    (directory / "calibration.json").write_text(
        json.dumps({
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "blend": {
                "weight_hist": round(model.blend.weight, 4),
                "space": "log1p",
                "chosen_by": model.blend.chosen_by,
                "pinball": model.blend.per_quantile_loss,
            },
            "probability": model.probability.to_dict(),
            "score_map": model.score_map.to_dict(),
            "priority_bands": [
                {"level": level, "lower": lower, "upper": upper}
                for level, lower, upper in PRIORITY_BANDS
            ],
            "policy_fusion": {
                "weights": POLICY_WEIGHTS,
                "strongest_signal_share": STRONGEST_SIGNAL_SHARE,
            },
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "version": model.cfg.model_version,
        "data_version": model.data_version,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": model.cfg.seed,
        "target_coverage": model.cfg.target_coverage,
        "environment": {
            "python": platform.python_version(),
            "lightgbm": lightgbm.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "risk_members": [path.name for path in risk_files],
        "anchor_fallback_log": {
            "hist": model.hist.fallback_log,
            "peer": model.peer.fallback_log,
        },
        "feature_order": {
            "hist": list(model.hist.features),
            "peer": list(model.peer.features),
            "risk": list(RISK_FEATURES),
        },
        "categories": {
            "hist": model.hist.categories,
            "peer": model.peer.categories,
            "risk": model.risk.categories,
        },
        "transforms": {
            "target": "log1p(declared_packaging_tonnage)",
            "log1p_columns": list(LOG1P_COLUMNS),
            "categorical_columns": list(CATEGORICAL),
            "stale_matrix_multiplier": STALE_MATRIX_MULTIPLIER,
            "signal_active_threshold": SIGNAL_ACTIVE_THRESHOLD,
        },
        "signals": [
            {
                "code": spec["code"],
                "key": spec["key"],
                "name": spec["ad"],
                "question": spec["soru"],
                "availability_feature": spec["avail"],
                "unavailable_reason": spec["avail_reason"],
            }
            for spec in SIGNAL_SPECS
        ],
        "iterations": model.metadata(),
        "metrics": metrics or {},
        "notes": notes or [],
        "disclaimer": (
            "Oncelik puani operasyonel inceleme onceligidir. Suc veya usulsuzluk "
            "olasiligi DEGILDIR. Model tek basina ceza veya olumsuz idari karar "
            "uretemez. Bu surum SENTETIK veri uzerinde egitilmistir."
        ),
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    missing = [name for name in REQUIRED if not (directory / name).exists()]
    if missing:
        raise RuntimeError("Teslim paketinde eksik dosya: " + ", ".join(missing))

    return {name: str((directory / name).resolve()) for name in REQUIRED}


__all__ = ["export", "REQUIRED"]
