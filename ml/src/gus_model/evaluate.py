"""Degerlendirme.

Metrik tanimlari `gus_generator.quality` icinden ITHAL EDILIR. Boylece modelin
tablosu ile dataset'in referans baseline tablosu bit bazinda ayni tanimlari
kullanir; "model baseline'i gecti" iddiasi olcum farkindan gelemez.

Neler olculur:

    siralama        PR-AUC, ROC-AUC (ek gosterge), Precision/Recall/Lift@K
    kalibrasyon     konformal kapsama, olasilik guvenilirlik tablosu, Brier, ECE
    ablation        her sinyal cikarilarak YENIDEN egitim (maskeleme degil)
    alt grup        sektor / olcek / veri guveni / il - adalet ve dayaniklilik
    kayma           A08 mekanizmasi egitimde nadir, testte sik; recall ayrica olculur
    yanlis pozitif  N10 (mesru gorunum) ve N09 (veri eksikligi) Top-K icindeki payi
    fayda           denetim maliyeti karsiliginda dogrulanan duzeltme tonaji

Test bolumu YALNIZCA burada, YALNIZCA bir kez okunur.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gus_generator.quality import (  # noqa: E402
    average_precision,
    bootstrap_ci,
    compute_baseline_scores,
    precision_recall_at_k,
    roc_auc,
)

from .config import SIGNAL_CODES, ModelConfig  # noqa: E402
from .dataset import Bundle  # noqa: E402
from .featureset import RISK_FEATURES  # noqa: E402
from .risk import RiskModel  # noqa: E402


# --------------------------------------------------------------------------
# Siralama metrikleri
# --------------------------------------------------------------------------
def ranking_metrics(
    y: np.ndarray,
    score: np.ndarray,
    ks: Sequence[int],
    name: str,
    split: str,
    bootstrap: int = 0,
    seed: int = 7,
) -> Dict:
    y = np.asarray(y, dtype=int)
    score = np.nan_to_num(np.asarray(score, dtype=float), nan=-1e9)
    row: Dict = {
        "model": name,
        "bolum": split,
        "n": len(y),
        "pozitif": int(y.sum()),
        "prevalans": round(float(y.mean()), 4) if len(y) else float("nan"),
        "PR_AUC": round(average_precision(y, score), 4),
        "ROC_AUC_ek_gosterge": round(roc_auc(y, score), 4),
    }
    for k in ks:
        if k > len(y):
            continue
        metrics = precision_recall_at_k(y, score, k)
        row[f"Precision@{k}"] = round(metrics["precision"], 4)
        row[f"Recall@{k}"] = round(metrics["recall"], 4)
        row[f"Lift@{k}"] = round(metrics["lift"], 3)
    if bootstrap:
        k = min(100, len(y))
        ci = bootstrap_ci(y, score, k, n_boot=bootstrap, seed=seed)
        row["Precision@100_CI_alt"] = round(ci["precision_ci_low"], 4)
        row["Precision@100_CI_ust"] = round(ci["precision_ci_high"], 4)
    return row


def compare_with_baselines(
    bundle: Bundle,
    split_index: pd.Index,
    model_score: pd.Series,
    cfg: ModelConfig,
    split_name: str,
) -> pd.DataFrame:
    """Model ile dataset'in referans baseline'lari ayni tabloda."""
    rng = np.random.default_rng(cfg.seed)
    baselines = compute_baseline_scores(bundle.model_ready, rng).set_index("observation_id")
    y = bundle.target(split_index)

    rows = [
        ranking_metrics(
            y, model_score.loc[split_index].to_numpy(), cfg.eval_ks,
            "GUS-DEDEKTIV (fusion)", split_name, bootstrap=cfg.bootstrap_n, seed=cfg.seed,
        )
    ]
    for column in [c for c in baselines.columns if c.startswith("bl_")]:
        rows.append(
            ranking_metrics(
                y, baselines.loc[split_index, column].to_numpy(), cfg.eval_ks,
                column, split_name, bootstrap=cfg.bootstrap_n, seed=cfg.seed,
            )
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Olasilik kalibrasyonu
# --------------------------------------------------------------------------
def reliability_table(y: np.ndarray, prob: np.ndarray, bins: int = 10) -> pd.DataFrame:
    y = np.asarray(y, dtype=float)
    prob = np.asarray(prob, dtype=float)
    order = np.argsort(prob)
    chunks = np.array_split(order, bins)
    rows: List[Dict] = []
    for i, chunk in enumerate(chunks, start=1):
        if len(chunk) == 0:
            continue
        rows.append({
            "dilim": i,
            "n": len(chunk),
            "tahmin_ortalama": round(float(prob[chunk].mean()), 4),
            "gozlenen_oran": round(float(y[chunk].mean()), 4),
            "fark": round(float(prob[chunk].mean() - y[chunk].mean()), 4),
        })
    return pd.DataFrame(rows)


def calibration_summary(y: np.ndarray, prob: np.ndarray, bins: int = 10) -> Dict[str, float]:
    y = np.asarray(y, dtype=float)
    prob = np.asarray(prob, dtype=float)
    table = reliability_table(y, prob, bins)
    weights = table["n"].to_numpy() / max(len(y), 1)
    ece = float(np.sum(weights * np.abs(table["fark"].to_numpy())))
    return {
        "brier": round(float(np.mean((prob - y) ** 2)), 5),
        "ece": round(ece, 5),
        "ortalama_tahmin": round(float(prob.mean()), 5),
        "gozlenen_prevalans": round(float(y.mean()), 5),
    }


# --------------------------------------------------------------------------
# Ablation - yeniden egitimli
# --------------------------------------------------------------------------
def ablation(
    cfg: ModelConfig,
    train_inputs: pd.DataFrame,
    y_train: np.ndarray,
    valid_inputs: pd.DataFrame,
    y_valid: np.ndarray,
    test_inputs: pd.DataFrame,
    y_test: np.ndarray,
    k: int = 100,
) -> pd.DataFrame:
    """Her sinyal cikarilip model yeniden egitilir.

    Maskeleme degil YENIDEN EGITIM kullanilir: maskeleme yalnizca modelin o
    girdiye ne kadar yaslandigini olcer, sinyalin sisteme kattigi bilgiyi
    olcmez - diger sinyaller bosluğu doldurabilir.
    """
    def _fit_and_score(features: Sequence[str]) -> Tuple[float, float]:
        model = RiskModel(tuple(features)).fit(
            cfg, train_inputs, y_train, valid_inputs, y_valid
        )
        score = model.predict_proba(test_inputs)
        return (
            average_precision(y_test, score),
            precision_recall_at_k(np.asarray(y_test), score, k)["precision"],
        )

    full_ap, full_precision = _fit_and_score(RISK_FEATURES)
    rows: List[Dict] = [{
        "cikarilan": "-",
        "PR_AUC": round(full_ap, 4),
        f"Precision@{k}": round(full_precision, 4),
        "delta_PR_AUC": 0.0,
        f"delta_Precision@{k}": 0.0,
    }]

    for code in SIGNAL_CODES:
        key = code.lower()
        reduced = [
            f for f in RISK_FEATURES
            if f not in (f"raw_{key}", f"sig_{key}", f"avail_{key}")
        ]
        ap, precision = _fit_and_score(reduced)
        rows.append({
            "cikarilan": code,
            "PR_AUC": round(ap, 4),
            f"Precision@{k}": round(precision, 4),
            "delta_PR_AUC": round(ap - full_ap, 4),
            f"delta_Precision@{k}": round(precision - full_precision, 4),
        })

    interval = [f for f in RISK_FEATURES if not f.startswith("interval_")]
    ap, precision = _fit_and_score(interval)
    rows.append({
        "cikarilan": "konformal aralik",
        "PR_AUC": round(ap, 4),
        f"Precision@{k}": round(precision, 4),
        "delta_PR_AUC": round(ap - full_ap, 4),
        f"delta_Precision@{k}": round(precision - full_precision, 4),
    })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Alt grup ve adalet
# --------------------------------------------------------------------------
def subgroup_performance(
    frame: pd.DataFrame,
    y: np.ndarray,
    score: np.ndarray,
    by: str,
    k: int = 100,
    min_n: int = 25,
) -> pd.DataFrame:
    values = frame[by].astype(str).to_numpy()
    order = np.argsort(-np.asarray(score, dtype=float), kind="stable")
    top = np.zeros(len(score), dtype=bool)
    top[order[: min(k, len(score))]] = True

    rows: List[Dict] = []
    for value in sorted(set(values)):
        mask = values == value
        n = int(mask.sum())
        if n < min_n:
            continue
        sub_y = np.asarray(y)[mask]
        sub_score = np.asarray(score)[mask]
        rows.append({
            "boyut": by,
            "grup": value,
            "n": n,
            "pozitif": int(sub_y.sum()),
            "prevalans": round(float(sub_y.mean()), 4),
            "PR_AUC": round(average_precision(sub_y, sub_score), 4),
            "ROC_AUC": round(roc_auc(sub_y, sub_score), 4),
            f"Top{k}_payi": round(float(top[mask].mean()), 4),
            "ortalama_puan": round(float(np.mean(sub_score)), 4),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Mekanizma bazli recall ve kavramsal kayma
# --------------------------------------------------------------------------
def mechanism_recall(
    labels: pd.DataFrame,
    index: pd.Index,
    score: np.ndarray,
    ks: Sequence[int] = (50, 100, 200),
) -> pd.DataFrame:
    sub = labels.loc[index]
    order = np.argsort(-np.asarray(score, dtype=float), kind="stable")
    rows: List[Dict] = []
    for mechanism, group in sub.groupby("anomaly_type"):
        positions = np.array([index.get_loc(i) for i in group.index])
        row: Dict = {
            "mekanizma": mechanism,
            "n": len(group),
            "truth": int(group["truth_anomaly_flag"].sum()),
        }
        for k in ks:
            top = set(order[: min(k, len(order))])
            row[f"Top{k}_icinde"] = int(sum(1 for p in positions if p in top))
            row[f"Top{k}_orani"] = round(row[f"Top{k}_icinde"] / max(len(group), 1), 4)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("mekanizma").reset_index(drop=True)


# --------------------------------------------------------------------------
# Fayda / maliyet
# --------------------------------------------------------------------------
def yield_curve(
    labels: pd.DataFrame,
    index: pd.Index,
    score: np.ndarray,
    ks: Sequence[int] = (25, 50, 100, 200, 400),
) -> pd.DataFrame:
    sub = labels.loc[index]
    order = np.argsort(-np.asarray(score, dtype=float), kind="stable")
    ordered = sub.iloc[order]
    total_correction = float(sub["confirmed_correction_tonnage"].sum())

    rows: List[Dict] = []
    for k in ks:
        if k > len(ordered):
            continue
        head = ordered.iloc[:k]
        confirmed = float(head["confirmed_correction_tonnage"].sum())
        cost = float(head["audit_cost_try"].sum())
        rows.append({
            "K": k,
            "dogrulanan_vaka": int(head["truth_anomaly_flag"].sum()),
            "vaka_100_denetim_basina": round(float(head["truth_anomaly_flag"].mean()) * 100, 1),
            "duzeltilen_tonaj": round(confirmed, 2),
            "toplam_tonajin_payi": round(confirmed / total_correction, 4) if total_correction else float("nan"),
            "denetim_maliyeti_try": round(cost, 2),
            "ton_basina_maliyet_try": round(cost / confirmed, 2) if confirmed > 0 else float("nan"),
            "toplam_inceleme_gunu": int(head["inspection_duration_days"].sum()),
        })
    return pd.DataFrame(rows)


def false_positive_profile(
    labels: pd.DataFrame,
    index: pd.Index,
    score: np.ndarray,
    k: int = 100,
) -> pd.DataFrame:
    sub = labels.loc[index]
    order = np.argsort(-np.asarray(score, dtype=float), kind="stable")
    head = sub.iloc[order[: min(k, len(sub))]]
    negatives = head[head["truth_anomaly_flag"] == 0]

    rows: List[Dict] = [{
        "kategori": f"Top-{k} toplam",
        "sayi": len(head),
        "pay": 1.0,
        "aciklama": "",
    }, {
        "kategori": "dogrulanan eksik beyan",
        "sayi": int(head["truth_anomaly_flag"].sum()),
        "pay": round(float(head["truth_anomaly_flag"].mean()), 4),
        "aciklama": "gercek pozitif",
    }]
    for mechanism, group in negatives.groupby("anomaly_type"):
        rows.append({
            "kategori": mechanism,
            "sayi": len(group),
            "pay": round(len(group) / max(len(head), 1), 4),
            "aciklama": "yanlis pozitif" if mechanism != "N09_veri_eksikligi" else "veri incelemesi kuyrugu",
        })
    causes = negatives[negatives["legitimate_cause"].astype(str) != ""]
    for cause, group in causes.groupby("legitimate_cause"):
        rows.append({
            "kategori": f"  mesru neden: {cause}",
            "sayi": len(group),
            "pay": round(len(group) / max(len(head), 1), 4),
            "aciklama": "denetci gerekce panelinde gorunur",
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Sinyal davranisi
# --------------------------------------------------------------------------
def signal_correlation(signal_scores: pd.DataFrame) -> pd.DataFrame:
    """Sekiz sinyalin birbirleriyle korelasyonu.

    "Bagimsiz" DEGIL "ayri" sinyaller oldugunun sayisal karsiligi budur.
    """
    columns = [f"sig_{code.lower()}" for code in SIGNAL_CODES]
    frame = signal_scores[columns].astype(float)
    frame.columns = list(SIGNAL_CODES)
    return frame.corr(method="spearman").round(3)


def signal_discrimination(
    signal_scores: pd.DataFrame,
    y: np.ndarray,
) -> pd.DataFrame:
    """Her sinyalin TEK BASINA ayirt etme gucu ve kullanilabilirligi."""
    rows: List[Dict] = []
    y = np.asarray(y, dtype=int)
    for code in SIGNAL_CODES:
        key = code.lower()
        available = signal_scores[f"avail_{key}"].to_numpy() > 0
        score = signal_scores[f"sig_{key}"].to_numpy(dtype=float)
        n = int(available.sum())
        if n < 30 or y[available].sum() == 0:
            rows.append({"sinyal": code, "kullanilabilirlik": round(float(available.mean()), 4),
                         "n": n, "PR_AUC": float("nan"), "ROC_AUC": float("nan"),
                         "atesleme_orani": float("nan")})
            continue
        rows.append({
            "sinyal": code,
            "kullanilabilirlik": round(float(available.mean()), 4),
            "n": n,
            "PR_AUC": round(average_precision(y[available], score[available]), 4),
            "ROC_AUC": round(roc_auc(y[available], score[available]), 4),
            "atesleme_orani": round(float((score[available] >= 22.0).mean()), 4),
        })
    return pd.DataFrame(rows)


__all__ = [
    "ranking_metrics",
    "compare_with_baselines",
    "reliability_table",
    "calibration_summary",
    "ablation",
    "subgroup_performance",
    "mechanism_recall",
    "yield_curve",
    "false_positive_profile",
    "signal_correlation",
    "signal_discrimination",
]
