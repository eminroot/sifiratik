"""Dataset dogrulama scripti.

Uretilmis dataseti bagimsiz olarak dogrular:
  1. Referans CSV butunlugu (alan sayisi, kaynak zorunlulugu, URL varligi)
  2. Mimari sizinti kurali: features.py, anomalies modulunu ithal etmemeli
  3. Sutun bazli sizinti (yasak kalip + korelasyon)
  4. Zamansal butunluk (ileriye bakis yok)
  5. Determinizm (ayni seed -> ayni cikti)
  6. Mantik ve is kurallari
  7. Dataset trivial mi

Kullanim:
    python src/validate_dataset.py
    python src/validate_dataset.py --firms 300 --skip-determinism
"""

from __future__ import annotations

import argparse
import ast
import glob
import hashlib
import io
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gus_generator import GeneratorConfig, build_dataset          # noqa: E402
from gus_generator.features import FORBIDDEN_PATTERNS             # noqa: E402

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"kontrol": name, "durum": "GECTI" if ok else "KALDI", "detay": detail})
    flag = "  OK  " if ok else " KALDI"
    print(f"[{flag}] {name}" + (f"  -> {detail}" if detail else ""))


# --------------------------------------------------------------------------
def validate_reference(ref_dir: str) -> None:
    files = sorted(glob.glob(os.path.join(ref_dir, "*.csv")))
    check("Referans dosyalari mevcut", len(files) >= 5, f"{len(files)} dosya")

    for p in files:
        name = os.path.basename(p)
        lines = io.open(p, encoding="utf-8").read().splitlines()
        want = lines[0].count(";")
        bad = [i + 1 for i, l in enumerate(lines) if l.strip() and l.count(";") != want]
        check(f"CSV alan sayisi tutarli - {name}", not bad, f"hatali satirlar: {bad}" if bad else "")

    src = pd.read_csv(os.path.join(ref_dir, "source_registry.csv"), sep=";", dtype=str)
    check("Her kaynakta URL var", src["url"].notna().all() and (src["url"].str.len() > 5).all())
    check("Her kaynakta erisim tarihi var", src["erisim_tarihi"].notna().all())
    check("Her kaynakta sinirlamalar alani dolu", (src["sinirlamalar"].str.len() > 10).all())
    check("Birincil/ikincil ayrimi yapilmis",
          set(src["birincil_ikincil"].unique()) <= {"Birincil", "Ikincil", "Sentetik"},
          str(sorted(src["birincil_ikincil"].unique())))

    rates = pd.read_csv(os.path.join(ref_dir, "gekap_rates.csv"), sep=";", dtype=str)
    check("GEKAP tarifelerinde 2023 YOK (dogrulanamadi, uydurulmadi)",
          "2023" not in set(rates["yil"]), "beklenen davranis")
    check("GEKAP tarifeleri 2024-2025-2026 kapsiyor",
          {"2024", "2025", "2026"} <= set(rates["yil"]))
    check("Her tarife satirinda source_id var", rates["source_id"].notna().all())
    ahsap = rates[rates["ana_kategori"] == "AHSAP AMBALAJ"]
    check("Ahsap ambalaj tarifesi ADET bazli", (ahsap["birim"] == "adet").all())

    # Yeniden degerleme zinciri: 2025 = 2024 x 1,4393 ve 2026 = 2025 x 1,2549 (%5 kesir kurali)
    def kg_rate(y, cat):
        r = rates[(rates["yil"] == y) & (rates["ana_kategori"] == cat) & (rates["birim"] == "kg")]
        return float(r.iloc[0]["tutar_kurus"].replace(",", ".")) if len(r) else None

    ok_chain = True
    detail = []
    for cat in ["PLASTIK AMBALAJ", "METAL AMBALAJ", "KAGIT KARTON AMBALAJ", "CAM AMBALAJ", "KOMPOZIT AMBALAJ"]:
        v24, v25, v26 = kg_rate("2024", cat), kg_rate("2025", cat), kg_rate("2026", cat)
        if None in (v24, v25, v26):
            continue
        e25, e26 = v24 * 1.4393, v25 * 1.2549
        good = (0 <= e25 - v25 <= 0.05 * e25) and (0 <= e26 - v26 <= 0.05 * e26)
        ok_chain &= good
        if not good:
            detail.append(f"{cat}: {v24}->{v25}(bek {e25:.1f}) ->{v26}(bek {e26:.1f})")
    check("Tarife zinciri yeniden degerleme + %5 kesir kuralina uyuyor", ok_chain, "; ".join(detail))


# --------------------------------------------------------------------------
def validate_architecture() -> None:
    """features.py, anomalies/ground-truth modullerini ITHAL ETMEMELIDIR."""
    src = io.open("src/gus_generator/features.py", encoding="utf-8").read()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            for a in node.names:
                imported.add(a.name)
    bad = {m for m in imported if "anomal" in m or "label" in m}
    check("features.py anomalies/label modulunu ithal etmiyor (dongusellik korumasi)", not bad, str(bad))


# --------------------------------------------------------------------------
def validate_dataset(b) -> None:
    mr, lab, obs = b.model_ready, b.audit_labels, b.observations

    # 1) Sutun adi sizintisi
    bad = [c for c in mr.columns if any(p in c.lower() for p in FORBIDDEN_PATTERNS)]
    check("Model_Ready yasak sutun icermiyor", not bad, str(bad))
    bad2 = [c for c in mr.columns if c.startswith("lat_") or c.startswith("_")]
    check("Model_Ready latent sutun icermiyor", not bad2, str(bad2))

    # 2) Korelasyon sizintisi
    m = mr.merge(lab[["observation_id", "truth_anomaly_flag"]], on="observation_id", how="left")
    y = m["truth_anomaly_flag"].fillna(0).astype(float)
    worst, wcol = 0.0, ""
    for c in m.columns:
        if not c.startswith("f_") or not pd.api.types.is_numeric_dtype(m[c]):
            continue
        v = m[c].astype(float)
        if v.notna().sum() < 100 or v.nunique(dropna=True) < 3:
            continue
        r = abs(float(v.corr(y)))
        if not np.isnan(r) and r > worst:
            worst, wcol = r, c
    check("Hicbir ozellik hedefle asiri korelasyonlu degil (<0,90)", worst < 0.90, f"max={worst:.4f} ({wcol})")

    # 3) Zamansal butunluk: gecikmeli ozellikler ilk donemde bos olmali
    firsts = mr.sort_values(["firm_id", "period"]).groupby("firm_id").head(1)
    check("Ilk donemde lag ozellikleri bos (ileriye bakis yok)",
          firsts["f_s1_decl_lag1"].isna().all())
    # Emsal istatistigi firmanin KENDI gecmisine degil, grubun t-1 donemine baglidir.
    # Bu nedenle dogru kontrol: datasetin EN ERKEN doneminde emsal gecmisi bos olmali.
    first_period = mr["period"].min()
    check("En erken donemde emsal gecmisi bos (ileriye bakis yok)",
          mr.loc[mr["period"] == first_period, "f_s2_peer_median_prev"].isna().all(),
          f"donem={first_period}")

    # 4) Anahtar butunlugu
    check("observation_id essiz", not obs["observation_id"].duplicated().any())
    check("Her gozlem icin etiket var", set(obs["observation_id"]) == set(lab["observation_id"]))
    check("Model_Ready ile Observations ayni kayit kumesi",
          set(mr["observation_id"]) == set(obs["observation_id"]))

    # 5) Is kurallari
    check("Beyan tonaji negatif degil", (obs["declared_packaging_tonnage"] >= 0).all())
    unpriced = obs[obs["gekap_rate_status"] == "history_not_priced"]
    check("Tarifesi dogrulanmamis donemde parasal tutar bos",
          unpriced["gekap_amount_try"].isna().all(),
          "2023 tarifesi uydurulmamistir")
    priced = obs[obs["gekap_rate_status"] == "official_verified"]
    check("Tarifesi dogrulanmis donemde parasal tutar dolu", priced["gekap_amount_try"].notna().all())

    mats = [c for c in obs.columns if c.startswith("declared_ton_")]
    diff = (obs[mats].sum(axis=1) - obs["declared_packaging_tonnage"]).abs()
    check("Malzeme kirilimi toplami = toplam beyan", (diff <= 0.01).all(), f"max sapma={diff.max():.6f}")

    # 6) Dagilim ve zorluk
    prev = float(lab["truth_anomaly_flag"].mean())
    check("Prevalans gercekci aralikta (0,03-0,15)", 0.03 <= prev <= 0.15, f"{prev:.4f}")
    check("Zor negatif (N10_mesru_gorunum) var", (lab["anomaly_type"] == "N10_mesru_gorunum").sum() > 0)
    check("Veri incelemesi kuyrugu (N09) var", (lab["anomaly_type"] == "N09_veri_eksikligi").sum() > 0)
    check("En az 6 farkli gercek anomali mekanizmasi",
          lab[lab["truth_anomaly_flag"] == 1]["anomaly_type"].nunique() >= 6)

    d = b.difficulty
    if "test_ROC_AUC" in d.columns:
        auc = float(d.iloc[0]["test_ROC_AUC"]); p100 = float(d.iloc[0]["test_Precision@100"])
        check("Dataset trivial degil (ROC-AUC<0,97 ve Precision@100<0,95)",
              auc < 0.97 and p100 < 0.95, f"ROC-AUC={auc:.4f}, P@100={p100:.4f}")
        check("Dataset rastgeleden anlamli olcude iyi (Lift@100 > 1,5)",
              float(d.iloc[0]["test_Lift@100"]) > 1.5, f"Lift@100={d.iloc[0]['test_Lift@100']}")

    # 7) Sentetik isaretleme
    check("Firms tablosu is_synthetic ile isaretli", bool(b.firms_public["is_synthetic"].all()))
    check("Observations provenance alanlari dolu",
          obs["source_ids"].notna().all() and obs["data_source_type"].notna().all())

    # 8) Zamansal bolunme
    check("Tum bolunmeler dolu",
          set(obs["split"].unique()) == {"history", "train", "valid", "test"},
          str(sorted(obs["split"].unique())))
    per = obs.groupby("split")["period"].agg(["min", "max"]).to_dict("index")
    ok = per["train"]["max"] < per["valid"]["min"] < per["valid"]["max"] < per["test"]["min"]
    check("Bolunmeler zamansal olarak ayrisik (train < valid < test)", ok, str(per))


# --------------------------------------------------------------------------
def validate_determinism(firms: int) -> None:
    def digest(bundle):
        h = hashlib.sha256()
        for df in (bundle.firms_public, bundle.observations, bundle.audit_labels, bundle.model_ready):
            h.update(pd.util.hash_pandas_object(df, index=False).values.tobytes())
        return h.hexdigest()

    b1 = build_dataset(GeneratorConfig(n_firms=firms))
    b2 = build_dataset(GeneratorConfig(n_firms=firms))
    check("Determinizm: ayni seed -> ayni dataset", digest(b1) == digest(b2))

    b3 = build_dataset(GeneratorConfig(n_firms=firms, seed=999))
    check("Farkli seed -> farkli dataset", digest(b1) != digest(b3))


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--firms", type=int, default=600)
    ap.add_argument("--ref", type=str, default="data/reference")
    ap.add_argument("--skip-determinism", action="store_true")
    args = ap.parse_args()

    print("=" * 78)
    print("GUS-DEDEKTIV DATASET DOGRULAMA")
    print("=" * 78)

    print("\n--- 1. Referans veri (Katman A) ---")
    validate_reference(args.ref)

    print("\n--- 2. Mimari sizinti korumasi ---")
    validate_architecture()

    print("\n--- 3. Dataset ---")
    b = build_dataset(GeneratorConfig(n_firms=args.firms), ref_dir=args.ref)
    validate_dataset(b)

    if not args.skip_determinism:
        print("\n--- 4. Determinizm ---")
        validate_determinism(min(args.firms, 200))

    failed = [r for r in RESULTS if r["durum"] == "KALDI"]
    print("\n" + "=" * 78)
    print(f"SONUC: {len(RESULTS)} kontrol, {len(RESULTS) - len(failed)} GECTI, {len(failed)} KALDI")
    print("=" * 78)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
