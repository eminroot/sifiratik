"""Kalite kontrolleri, gercekcilik testleri ve REFERANS baseline degerlendirmesi.

Buradaki baseline'lar GUS-DEDEKTIV MODELI DEGILDIR. Amaclari yalnizca:
  (a) datasetin trivial olmadigini gostermek (Top-K otomatik %100 cikmamali),
  (b) model asamasinda kullanilacak alt sinir referanslarini uretmek,
  (c) veri sizintisi olup olmadigini erken yakalamak.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config import GEKAP_MATERIALS


# ==========================================================================
# Metrikler
# ==========================================================================
def precision_recall_at_k(y_true: np.ndarray, score: np.ndarray, k: int) -> Dict[str, float]:
    n = len(y_true)
    k = min(k, n)
    order = np.argsort(-score, kind="stable")
    top = order[:k]
    tp = int(y_true[top].sum())
    total_pos = int(y_true.sum())
    prevalence = total_pos / n if n else 0.0
    precision = tp / k if k else 0.0
    recall = tp / total_pos if total_pos else 0.0
    lift = precision / prevalence if prevalence > 0 else float("nan")
    return {"k": k, "tp": tp, "precision": precision, "recall": recall, "lift": lift}


def average_precision(y_true: np.ndarray, score: np.ndarray) -> float:
    """PR-AUC (average precision). sklearn bagimliligi olmadan hesaplanir."""
    order = np.argsort(-score, kind="stable")
    y = y_true[order]
    tp = np.cumsum(y)
    fp = np.cumsum(1 - y)
    prec = tp / np.maximum(tp + fp, 1)
    total_pos = y.sum()
    if total_pos == 0:
        return float("nan")
    return float((prec * y).sum() / total_pos)


def roc_auc(y_true: np.ndarray, score: np.ndarray) -> float:
    """ROC-AUC (Mann-Whitney U). YALNIZCA EK gosterge olarak kullanilir."""
    pos = score[y_true == 1]
    neg = score[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    all_s = np.concatenate([pos, neg])
    ranks = pd.Series(all_s).rank(method="average").to_numpy()
    r_pos = ranks[: len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def bootstrap_ci(
    y_true: np.ndarray, score: np.ndarray, k: int, n_boot: int = 500, seed: int = 7
) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    n = len(y_true)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        vals.append(precision_recall_at_k(y_true[idx], score[idx], k)["precision"])
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return {"precision_ci_low": float(lo), "precision_ci_high": float(hi)}


# ==========================================================================
# REFERANS baseline skorlari (model DEGILDIR)
# ==========================================================================
def _z(series: pd.Series) -> np.ndarray:
    v = series.astype(float).to_numpy()
    med = np.nanmedian(v)
    mad = np.nanmedian(np.abs(v - med))
    scale = 1.4826 * mad if mad > 1e-9 else (np.nanstd(v) or 1.0)
    z = (v - med) / scale
    return np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)


def compute_baseline_scores(model_ready: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    mr = model_ready.copy()
    out = mr[["observation_id", "firm_id", "period", "split"]].copy()

    out["bl_random"] = rng.random(len(mr))

    # Basit uzman kurali: kendi gecmis oraninin belirgin altinda mi?
    ratio_drop = 1.0 - mr["f_s1_vs_hist_median_ratio"].astype(float)
    out["bl_expert_rule"] = np.nan_to_num(ratio_drop.to_numpy(), nan=0.0)

    # Z-score (tarihsel)
    out["bl_zscore_hist"] = -_z(mr["f_s1_ratio_z_own"])

    # Emsal karsilastirmasi
    out["bl_peer"] = -_z(mr["f_s2_vs_peer_median"])

    # Yalnizca beklenen-beyan farki (S3)
    out["bl_bom_gap"] = np.nan_to_num(mr["f_s3_bom_gap_rel"].astype(float).to_numpy(), nan=0.0)

    # Naif birlesim: sekiz sinyalin kaba vekilleri, mevcut olanlar uzerinden
    parts = {
        "s1": -_z(mr["f_s1_ratio_z_own"]),
        "s2": -_z(mr["f_s2_vs_peer_median"]),
        "s3": _z(mr["f_s3_bom_gap_rel"]),
        "s4": -_z(mr["f_s4_divergence_yoy"]),
        "s5": -_z(mr["f_s5_decl_per_domestic"]),
        "s6": -_z(mr["f_s6_seasonal_resid"]),
        "s7": _z(mr["f_s7_mix_shift_l1"]),
        "s8": _z(mr["f_s8_external_gap_rel"]),
    }
    stack = np.vstack([parts[f"s{i}"] for i in range(1, 9)])
    avail = mr[[f"f_avail_s{i}" for i in range(1, 9)]].to_numpy().T.astype(float)
    denom = np.maximum(avail.sum(axis=0), 1.0)
    out["bl_naive_8signal"] = (stack * avail).sum(axis=0) / denom

    return out


def evaluate_baselines(
    baselines: pd.DataFrame,
    labels: pd.DataFrame,
    split: str = "test",
    ks: tuple = (25, 50, 100),
) -> pd.DataFrame:
    merged = baselines.merge(
        labels[["observation_id", "truth_anomaly_flag"]], on="observation_id", how="left"
    )
    sub = merged[merged["split"] == split].reset_index(drop=True)
    y = sub["truth_anomaly_flag"].fillna(0).astype(int).to_numpy()

    score_cols = [c for c in sub.columns if c.startswith("bl_")]
    rows: List[Dict] = []
    for c in score_cols:
        s = sub[c].astype(float).to_numpy()
        s = np.nan_to_num(s, nan=-1e9)
        row: Dict = {
            "baseline": c,
            "split": split,
            "n": len(sub),
            "pozitif_sayisi": int(y.sum()),
            "prevalans": round(float(y.mean()), 4),
            "PR_AUC": round(average_precision(y, s), 4),
            "ROC_AUC_ek_gosterge": round(roc_auc(y, s), 4),
        }
        for k in ks:
            m = precision_recall_at_k(y, s, k)
            row[f"Precision@{k}"] = round(m["precision"], 4)
            row[f"Recall@{k}"] = round(m["recall"], 4)
            row[f"Lift@{k}"] = round(m["lift"], 3)
        ci = bootstrap_ci(y, s, min(100, len(sub)))
        row["Precision@100_CI_alt"] = round(ci["precision_ci_low"], 4)
        row["Precision@100_CI_ust"] = round(ci["precision_ci_high"], 4)
        rows.append(row)
    return pd.DataFrame(rows)


def difficulty_probe(model_ready: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Guclu bir modelin datasetten ne kadar sinyal cikardigini olcer.

    Amac: dataset TRIVIAL mi? Test ROC-AUC ~1,00 veya Precision@100 ~1,00 ise
    veri sizintisi veya asiri kolay dataset var demektir.
    sklearn kurulu degilse atlanir.
    """
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
    except Exception:
        return pd.DataFrame([{
            "kontrol": "difficulty_probe",
            "durum": "ATLANDI",
            "aciklama": "scikit-learn kurulu degil; probe calistirilamadi",
        }])

    mr = model_ready.merge(
        labels[["observation_id", "truth_anomaly_flag"]], on="observation_id", how="left"
    )
    num_cols = [
        c for c in mr.columns
        if c.startswith("f_") and pd.api.types.is_numeric_dtype(mr[c])
    ]
    tr = mr[mr["split"] == "train"]
    te = mr[mr["split"] == "test"]
    if tr.empty or te.empty or tr["truth_anomaly_flag"].sum() < 10:
        return pd.DataFrame([{"kontrol": "difficulty_probe", "durum": "ATLANDI",
                              "aciklama": "yeterli egitim pozitifi yok"}])

    X_tr = tr[num_cols].to_numpy(dtype=float)
    y_tr = tr["truth_anomaly_flag"].fillna(0).astype(int).to_numpy()
    X_te = te[num_cols].to_numpy(dtype=float)
    y_te = te["truth_anomaly_flag"].fillna(0).astype(int).to_numpy()

    clf = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.06, random_state=42)
    clf.fit(X_tr, y_tr)
    s = clf.predict_proba(X_te)[:, 1]

    auc = roc_auc(y_te, s)
    p100 = precision_recall_at_k(y_te, s, 100)
    ap = average_precision(y_te, s)
    trivial = bool(auc > 0.97 or p100["precision"] > 0.95)

    return pd.DataFrame([{
        "kontrol": "difficulty_probe (HistGradientBoosting - REFERANS, GUS-DEDEKTIV modeli degildir)",
        "durum": "UYARI - dataset cok kolay veya sizinti var" if trivial else "GECTI",
        "test_ROC_AUC": round(auc, 4),
        "test_PR_AUC": round(ap, 4),
        "test_Precision@100": round(p100["precision"], 4),
        "test_Lift@100": round(p100["lift"], 3),
        "test_prevalans": round(float(y_te.mean()), 4),
        "aciklama": "ROC-AUC > 0,97 veya Precision@100 > 0,95 ise dataset trivial kabul edilir",
    }])


# ==========================================================================
# Kalite ve gercekcilik kontrolleri
# ==========================================================================
def run_quality_checks(
    firms: pd.DataFrame,
    observations: pd.DataFrame,
    packaging: pd.DataFrame,
    model_ready: pd.DataFrame,
    labels: pd.DataFrame,
    material_anchor: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    checks: List[Dict] = []

    def add(kategori, kontrol, deger, beklenen, durum, aciklama=""):
        checks.append({
            "kategori": kategori, "kontrol": kontrol, "deger": deger,
            "beklenen": beklenen, "durum": durum, "aciklama": aciklama,
        })

    # --- Butunluk ---
    add("Butunluk", "Firma sayisi", len(firms), ">= 300",
        "GECTI" if len(firms) >= 300 else "KALDI")
    add("Butunluk", "Firma-ceyrek kayit sayisi", len(observations), ">= 3600",
        "GECTI" if len(observations) >= 3600 else "KALDI")
    add("Butunluk", "Farkli donem sayisi", observations["period"].nunique(), ">= 12",
        "GECTI" if observations["period"].nunique() >= 12 else "KALDI")
    dup = int(observations["observation_id"].duplicated().sum())
    add("Butunluk", "Yinelenen observation_id", dup, "0", "GECTI" if dup == 0 else "KALDI")
    dupf = int(firms["firm_id"].duplicated().sum())
    add("Butunluk", "Yinelenen firm_id", dupf, "0", "GECTI" if dupf == 0 else "KALDI")

    # --- Referans butunlugu ---
    orphan = int((~observations["firm_id"].isin(set(firms["firm_id"]))).sum())
    add("Butunluk", "Firms tablosunda karsiligi olmayan gozlem", orphan, "0",
        "GECTI" if orphan == 0 else "KALDI")
    miss_lbl = int((~observations["observation_id"].isin(set(labels["observation_id"]))).sum())
    add("Butunluk", "Etiketi olmayan gozlem", miss_lbl, "0",
        "GECTI" if miss_lbl == 0 else "KALDI")

    # --- Sizinti ---
    forbidden = [c for c in model_ready.columns
                 if any(p in c.lower() for p in ("truth", "anomaly", "audit", "true_", "label_"))]
    add("Sizinti", "Model_Ready icinde yasak sutun", len(forbidden), "0",
        "GECTI" if not forbidden else "KALDI", ";".join(forbidden))

    mr = model_ready.merge(labels[["observation_id", "truth_anomaly_flag"]],
                           on="observation_id", how="left")
    y = mr["truth_anomaly_flag"].fillna(0).astype(float)
    max_corr, max_col = 0.0, ""
    for c in mr.columns:
        if not c.startswith("f_") or not pd.api.types.is_numeric_dtype(mr[c]):
            continue
        v = mr[c].astype(float)
        if v.notna().sum() < 50 or v.nunique(dropna=True) < 3:
            continue
        r = abs(float(v.corr(y)))
        if not np.isnan(r) and r > max_corr:
            max_corr, max_col = r, c
    add("Sizinti", "En yuksek |korelasyon| (ozellik vs truth)", round(max_corr, 4), "< 0,90",
        "GECTI" if max_corr < 0.90 else "KALDI", f"sutun: {max_col}")

    # --- Anomali dagilimi ---
    prev = float(labels["truth_anomaly_flag"].mean())
    add("Dagilim", "Genel anomali prevalansi", round(prev, 4), "0,03 - 0,15",
        "GECTI" if 0.03 <= prev <= 0.15 else "UYARI")
    for sp in ("train", "valid", "test"):
        s = labels[labels["split"] == sp]
        if len(s):
            add("Dagilim", f"Prevalans - {sp}", round(float(s["truth_anomaly_flag"].mean()), 4),
                "0,03 - 0,15", "GECTI" if 0.03 <= s["truth_anomaly_flag"].mean() <= 0.15 else "UYARI")

    hard_neg = int((labels["anomaly_type"] == "N10_mesru_gorunum").sum())
    add("Dagilim", "Mesru gorunum (hard negative) sayisi", hard_neg, "> 0",
        "GECTI" if hard_neg > 0 else "KALDI",
        "Yanlis-pozitif olcumu icin gereklidir")
    dq = int((labels["anomaly_type"] == "N09_veri_eksikligi").sum())
    add("Dagilim", "Veri incelemesi kuyrugu kaydi", dq, "> 0",
        "GECTI" if dq > 0 else "UYARI")

    n_types = labels[labels["truth_anomaly_flag"] == 1]["anomaly_type"].nunique()
    add("Dagilim", "Farkli gercek anomali mekanizmasi sayisi", n_types, ">= 6",
        "GECTI" if n_types >= 6 else "UYARI")

    # --- Ortusme (dataset cok kolay olmamali) ---
    obs_l = observations.merge(labels[["observation_id", "truth_anomaly_flag"]],
                               on="observation_id", how="left")
    mrl = model_ready.merge(labels[["observation_id", "truth_anomaly_flag"]],
                            on="observation_id", how="left")
    v = mrl["f_s1_vs_hist_median_ratio"].astype(float)
    p_norm = v[mrl["truth_anomaly_flag"] == 0].quantile(0.10)
    p_anom = v[mrl["truth_anomaly_flag"] == 1].quantile(0.90)
    overlap = bool(p_anom > p_norm)
    add("Ayirt edilebilirlik", "Normal p10 ile anomali p90 ortusuyor mu",
        f"normal_p10={round(float(p_norm),3)} / anomali_p90={round(float(p_anom),3)}",
        "ortusme OLMALI", "GECTI" if overlap else "UYARI",
        "Ortusme yoksa dataset trivial demektir")

    # --- Eksik veri ---
    for col in ("import_qty", "export_qty", "production_qty",
                "bom_expected_tonnage_observable", "external_evidence_tonnage"):
        rate = float(observations[col].isna().mean())
        add("Eksik veri", f"Eksik oran - {col}", round(rate, 4), "0,00 - 0,90", "BILGI")

    add("Eksik veri", "Dusuk veri guveni orani",
        round(float((observations["data_confidence_level"] == "dusuk").mean()), 4),
        "> 0", "BILGI", "Eksik veri dusuk risk olarak degerlendirilMEZ")

    # --- Mantik kontrolleri ---
    neg = int((observations["declared_packaging_tonnage"] < 0).sum())
    add("Mantik", "Negatif beyan tonaji", neg, "0", "GECTI" if neg == 0 else "KALDI")
    mat_cols = [f"declared_ton_{m}" for m in GEKAP_MATERIALS]
    diff = (observations[mat_cols].sum(axis=1) - observations["declared_packaging_tonnage"]).abs()
    bad_sum = int((diff > 0.01).sum())
    add("Mantik", "Malzeme kirilimi toplami ile toplam beyan uyusmazligi", bad_sum, "0",
        "GECTI" if bad_sum == 0 else "KALDI")

    priced = observations[observations["gekap_rate_status"] == "official_verified"]
    unpriced = observations[observations["gekap_rate_status"] == "history_not_priced"]
    add("Mantik", "Tarifesi dogrulanmis donem kayitlari", len(priced), "> 0",
        "GECTI" if len(priced) > 0 else "KALDI")
    add("Mantik", "Tarifesi dogrulanMAMIS (2023) kayitlarda GEKAP tutari bos mu",
        int(unpriced["gekap_amount_try"].notna().sum()), "0",
        "GECTI" if unpriced["gekap_amount_try"].notna().sum() == 0 else "KALDI",
        "2023 tarifeleri birincil kaynaktan dogrulanamadigi icin parasal tutar UYDURULMAZ")

    # --- Gercekcilik ---
    if material_anchor:
        tot = observations[mat_cols].sum()
        share = (tot / tot.sum()).to_dict()
        for m in GEKAP_MATERIALS:
            add("Gercekcilik", f"Malzeme payi - {m}",
                round(float(share.get(f'declared_ton_{m}', 0.0)), 4),
                f"resmi atik beyan referansi: {round(material_anchor.get(m, float('nan')), 4)}",
                "BILGI",
                "Referans ATIK BEYAN evrenidir; piyasaya surme evreni ile birebir esitlik BEKLENMEZ")

    for band in firms["size_band"].unique():
        ids = set(firms[firms["size_band"] == band]["firm_id"])
        med = float(observations[observations["firm_id"].isin(ids)]["declared_packaging_tonnage"].median())
        add("Gercekcilik", f"Medyan ceyreklik beyan tonaji - {band}", round(med, 3),
            "olcekle artan", "BILGI")

    # --- Bolunme ---
    for sp in ("history", "train", "valid", "test"):
        add("Bolunme", f"Kayit sayisi - {sp}", int((observations["split"] == sp).sum()),
            "> 0", "GECTI" if (observations["split"] == sp).sum() > 0 else "KALDI")

    return pd.DataFrame(checks)
