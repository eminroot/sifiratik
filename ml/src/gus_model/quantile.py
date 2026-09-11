"""Katman 3 - beklenen beyan araligi.

Iki ayri quantile baslik uydurulur (ARCHITECTURE.md 2. bolum):

    QuantileHead("hist")   firmanin kendi gecmisi + faaliyet buyuklugu
    QuantileHead("peer")   emsal grup + faaliyet buyuklugu (kendi gecmisi YOK)

Her baslik q05 / q50 / q95 icin ayri bir LightGBM modelidir. Hedef
`log1p(beyan_tonaji)`dir: quantile'lar monoton donusum altinda esdegisken
oldugu icin log uzayindaki q05 geri cevrildiginde yine q05'tir; kazanci,
araligin CARPANSAL olmasidir - mikro firmada 2 ton, buyuk firmada 200 ton
genislik ayni oransal belirsizligi ifade eder.

Iki baslik `BlendedExpectation` icinde harmanlanir; harman agirligi valid_a
bolumunde pinball kaybi en kucuk olacak sekilde secilir, kalibrasyon ise
`conformal.py` icinde yapilir.

CAPRAZ UYDURMA
--------------
Konformal kalibrasyonun gecerli olmasi icin artiklarin ORNEKLEM DISI olmasi
gerekir. `fit_cross_fitted` egitim bolumunu FIRMA bazinda K kata boler ve her
katin tahminini o kati gormeyen modelden alir; boylece egitim bolumu de
kalibrasyon havuzuna girebilir.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd

from .config import ModelConfig
from .featureset import (
    HIST_FEATURES,
    PEER_FEATURES,
    TARGET_COLUMN,
    categorical_names,
    log_target,
    prepare_matrix,
    unlog,
)

QUANTILES: Tuple[float, ...] = (0.05, 0.50, 0.95)
QUANTILE_NAMES: Tuple[str, ...] = ("q05", "q50", "q95")

HEAD_FEATURES: Dict[str, Tuple[str, ...]] = {
    "hist": HIST_FEATURES,
    "peer": PEER_FEATURES,
}

# Her baslik icin YAPISAL CAPA: "yogunluk x faaliyet" carpimi. Booster bu
# capanin uzerine yalnizca DUZELTME ogrenir (LightGBM `init_score`).
#
# Nedeni: beklenen tonaj esas olarak bir CARPIMDIR - birim uretim basina
# ambalaj yogunlugu carpi uretim miktari. Karar agaci carpma yapamaz; capa
# olmadan bu iliskiyi yuzlerce basamakli bir merdivenle yaklasik olarak kurar
# ve mikro ile buyuk firma arasinda birkac kat hata verir. Capa log uzayinda
# toplama donustugu icin booster'in isi yalnizca oransal sapmayi ogrenmektir.
ANCHOR_SOURCES: Dict[str, Tuple[Tuple[str, Optional[str]], ...]] = {
    # (yogunluk sutunu, carpilacak faaliyet sutunu) - None ise dogrudan tonaj
    "hist": (
        ("f_s1_ratio_hist_median", "production_qty"),
        ("f_s5_dpd_hist_median", "f_s5_domestic_derived"),
        ("f_s1_hist_median", None),
    ),
    "peer": (
        ("f_s2_peer_median_prev", "production_qty"),
        ("f_s2_peer_p10_prev", "production_qty"),
    ),
}


def anchor_log(frame: pd.DataFrame, head: str, fallback_log: float) -> np.ndarray:
    """Baslik icin log uzayinda yapisal capa.

    Kaynaklar sirayla denenir; ilk gecerli (sonlu ve pozitif) deger kullanilir.
    Hicbiri yoksa `fallback_log` (egitim penceresinin ortanca log beyani) kalir.
    """
    out = np.full(len(frame), np.nan)
    for density_col, activity_col in ANCHOR_SOURCES[head]:
        if density_col not in frame.columns:
            continue
        value = frame[density_col].astype(float).to_numpy()
        if activity_col is not None:
            if activity_col not in frame.columns:
                continue
            value = value * frame[activity_col].astype(float).to_numpy()
        usable = np.isnan(out) & np.isfinite(value) & (value > 0)
        out[usable] = value[usable]
    log_anchor = np.log1p(np.clip(out, 0.0, None))
    return np.where(np.isfinite(log_anchor), log_anchor, fallback_log)


def pinball_loss(y: np.ndarray, pred: np.ndarray, alpha: float) -> float:
    diff = np.asarray(y, dtype=float) - np.asarray(pred, dtype=float)
    return float(np.mean(np.maximum(alpha * diff, (alpha - 1.0) * diff)))


def _fold_of(firm_id: str, seed: int, folds: int) -> int:
    digest = hashlib.sha256(f"{seed}:cv:{firm_id}".encode()).hexdigest()
    return int(digest[:8], 16) % folds


@dataclass
class QuantileHead:
    """Bir baslik: uc quantile icin uc booster."""

    name: str
    features: Tuple[str, ...]
    boosters: Dict[str, lgb.Booster] = field(default_factory=dict)
    categories: Dict[str, List[str]] = field(default_factory=dict)
    best_iteration: Dict[str, int] = field(default_factory=dict)
    fallback_log: float = 0.0

    # ------------------------------------------------------------------ fit --

    def fit(
        self,
        cfg: ModelConfig,
        train: pd.DataFrame,
        valid: Optional[pd.DataFrame] = None,
    ) -> "QuantileHead":
        x_train, categories = prepare_matrix(train, self.features)
        self.categories = categories
        y_train = log_target(train[TARGET_COLUMN])
        self.fallback_log = float(np.median(y_train))
        base_train = anchor_log(train, self.name, self.fallback_log)

        if valid is not None and len(valid):
            x_valid, _ = prepare_matrix(valid, self.features, categories)
            y_valid = log_target(valid[TARGET_COLUMN])
            base_valid = anchor_log(valid, self.name, self.fallback_log)
        else:
            x_valid = y_valid = base_valid = None

        cats = categorical_names(self.features)
        for alpha, qname in zip(QUANTILES, QUANTILE_NAMES):
            params = dict(cfg.q_params)
            params["alpha"] = alpha
            params["seed"] = cfg.seed + int(alpha * 1000)
            params["metric"] = "quantile"

            dtrain = lgb.Dataset(
                x_train, label=y_train, categorical_feature=cats,
                init_score=base_train, free_raw_data=False,
            )
            callbacks = [lgb.log_evaluation(period=0)]
            valid_sets = None
            if x_valid is not None:
                valid_sets = [
                    lgb.Dataset(
                        x_valid,
                        label=y_valid,
                        categorical_feature=cats,
                        init_score=base_valid,
                        reference=dtrain,
                        free_raw_data=False,
                    )
                ]
                callbacks.append(
                    lgb.early_stopping(cfg.q_early_stopping, verbose=False)
                )

            booster = lgb.train(
                params,
                dtrain,
                num_boost_round=cfg.q_rounds,
                valid_sets=valid_sets,
                callbacks=callbacks,
            )
            self.boosters[qname] = booster
            self.best_iteration[qname] = int(booster.best_iteration or cfg.q_rounds)

        return self

    # -------------------------------------------------------------- predict --

    def predict_log(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Log uzayinda q05/q50/q95. Sutunlar monoton siraya zorlanir."""
        x, _ = prepare_matrix(frame, self.features, self.categories)
        base = anchor_log(frame, self.name, self.fallback_log)
        out = pd.DataFrame(index=frame.index)
        for qname in QUANTILE_NAMES:
            booster = self.boosters[qname]
            raw = booster.predict(x, num_iteration=booster.best_iteration or None)
            out[qname] = np.asarray(raw, dtype=float) + base
        return _enforce_monotone(out)

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        log_pred = self.predict_log(frame)
        return pd.DataFrame(
            {name: unlog(log_pred[name].to_numpy()) for name in QUANTILE_NAMES},
            index=frame.index,
        )

    # ----------------------------------------------------------------- io ----

    def save(self, directory: Path) -> Dict[str, str]:
        directory.mkdir(parents=True, exist_ok=True)
        written: Dict[str, str] = {}
        for qname, booster in self.boosters.items():
            path = directory / f"quantile_{self.name}_{qname}.txt"
            booster.save_model(str(path), num_iteration=booster.best_iteration or None)
            written[qname] = path.name
        return written

    @classmethod
    def load(cls, directory: Path, name: str, features: Sequence[str],
             categories: Dict[str, List[str]], fallback_log: float = 0.0) -> "QuantileHead":
        head = cls(
            name=name, features=tuple(features), categories=categories,
            fallback_log=float(fallback_log),
        )
        for qname in QUANTILE_NAMES:
            path = directory / f"quantile_{name}_{qname}.txt"
            head.boosters[qname] = lgb.Booster(model_file=str(path))
        return head


def _enforce_monotone(frame: pd.DataFrame) -> pd.DataFrame:
    """q05 <= q50 <= q95 garantisi.

    Uc quantile ayri modellerden geldigi icin nadiren capraz gecebilirler
    (quantile crossing). Siralamayi zorlamak, aralik yorumunu korur.
    """
    values = frame[list(QUANTILE_NAMES)].to_numpy(dtype=float)
    values = np.sort(values, axis=1)
    return pd.DataFrame(values, index=frame.index, columns=list(QUANTILE_NAMES))


# --------------------------------------------------------------------------
# Capraz uydurma - ornek disi artiklar icin
# --------------------------------------------------------------------------
def fit_cross_fitted(
    cfg: ModelConfig,
    name: str,
    train: pd.DataFrame,
) -> pd.DataFrame:
    """Egitim bolumu icin ORNEKLEM DISI log-quantile tahminleri uretir.

    Katlar firma bazinda ayrilir: ayni firmanin farkli ceyrekleri ayni katta
    kalir, boylece firma ici zaman korelasyonu katlar arasina sizmaz.
    """
    features = HEAD_FEATURES[name]
    folds = np.array([_fold_of(str(f), cfg.seed, cfg.cv_folds) for f in train["firm_id"]])
    out = pd.DataFrame(index=train.index, columns=list(QUANTILE_NAMES), dtype=float)

    for k in range(cfg.cv_folds):
        in_fold = folds == k
        if not in_fold.any() or in_fold.all():
            continue
        head = QuantileHead(name=name, features=features)
        head.fit(cfg, train.loc[~in_fold])
        out.loc[in_fold, :] = head.predict_log(train.loc[in_fold]).to_numpy()

    return _enforce_monotone(out.astype(float))


# --------------------------------------------------------------------------
# Harman
# --------------------------------------------------------------------------
@dataclass
class BlendedExpectation:
    """Iki basligin log uzayinda agirlikli harmani.

    `weight` tarihsel basligin payidir. Bir baslik hesaplanamadiginda agirlik
    kendiliginden diger basliga gecer; ikisi de yoksa sonuc NaN kalir ve
    ilgili sinyaller kullanilamaz isaretlenir.
    """

    weight: float = 0.5
    grid: Tuple[float, ...] = tuple(np.round(np.arange(0.0, 1.0001, 0.05), 2))
    chosen_by: str = "valid_a pinball"
    per_quantile_loss: Dict[str, float] = field(default_factory=dict)

    def blend_log(self, hist: pd.DataFrame, peer: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=hist.index, columns=list(QUANTILE_NAMES), dtype=float)
        for qname in QUANTILE_NAMES:
            h = hist[qname].to_numpy(dtype=float)
            p = peer[qname].to_numpy(dtype=float)
            w = np.full(len(h), self.weight, dtype=float)
            both = ~np.isnan(h) & ~np.isnan(p)
            only_h = ~np.isnan(h) & np.isnan(p)
            only_p = np.isnan(h) & ~np.isnan(p)
            blended = np.full(len(h), np.nan)
            blended[both] = w[both] * h[both] + (1.0 - w[both]) * p[both]
            blended[only_h] = h[only_h]
            blended[only_p] = p[only_p]
            out[qname] = blended
        return _enforce_monotone(out)

    def fit_weight(
        self,
        hist: pd.DataFrame,
        peer: pd.DataFrame,
        y_log: np.ndarray,
    ) -> "BlendedExpectation":
        best_w, best_loss = self.weight, np.inf
        for w in self.grid:
            candidate = BlendedExpectation(weight=float(w))
            pred = candidate.blend_log(hist, peer)
            loss = float(
                np.mean([
                    pinball_loss(y_log, pred[q].to_numpy(), a)
                    for q, a in zip(QUANTILE_NAMES, QUANTILES)
                ])
            )
            if loss < best_loss:
                best_w, best_loss = float(w), loss
        self.weight = best_w
        pred = self.blend_log(hist, peer)
        self.per_quantile_loss = {
            q: round(pinball_loss(y_log, pred[q].to_numpy(), a), 5)
            for q, a in zip(QUANTILE_NAMES, QUANTILES)
        }
        return self


def head_diagnostics(
    heads: Dict[str, QuantileHead],
    blend: BlendedExpectation,
    frame: pd.DataFrame,
    label: str,
) -> pd.DataFrame:
    """Baslik basina pinball kaybi ve ham kapsama (kalibrasyon ONCESI)."""
    y_log = log_target(frame[TARGET_COLUMN])
    rows: List[Dict] = []

    preds = {name: head.predict_log(frame) for name, head in heads.items()}
    preds["blend"] = blend.blend_log(preds["hist"], preds["peer"])

    for name, pred in preds.items():
        losses = {
            q: pinball_loss(y_log, pred[q].to_numpy(), a)
            for q, a in zip(QUANTILE_NAMES, QUANTILES)
        }
        inside = (y_log >= pred["q05"].to_numpy()) & (y_log <= pred["q95"].to_numpy())
        rows.append({
            "bolum": label,
            "baslik": name,
            "pinball_q05": round(losses["q05"], 5),
            "pinball_q50": round(losses["q50"], 5),
            "pinball_q95": round(losses["q95"], 5),
            "pinball_ort": round(float(np.mean(list(losses.values()))), 5),
            "ham_kapsama": round(float(np.nanmean(inside)), 4),
            "ortanca_genislik_ton": round(
                float(np.nanmedian(unlog(pred["q95"].to_numpy()) - unlog(pred["q05"].to_numpy()))), 3
            ),
        })
    return pd.DataFrame(rows)


__all__ = [
    "QUANTILES",
    "QUANTILE_NAMES",
    "HEAD_FEATURES",
    "QuantileHead",
    "BlendedExpectation",
    "fit_cross_fitted",
    "pinball_loss",
    "head_diagnostics",
]
