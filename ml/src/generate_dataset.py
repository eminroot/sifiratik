"""GUS-DEDEKTIV dataset uretim komutu.

Kullanim:
    python src/generate_dataset.py --seed 20260902 --firms 600
    python src/generate_dataset.py --firms 1200 --out data/output

Ayni seed + ayni parametreler ile ayni dataset uretilir.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gus_generator import GeneratorConfig, build_dataset          # noqa: E402
from gus_generator.excel_builder import build_excel               # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="GUS-DEDEKTIV sentetik dataset ureteci")
    ap.add_argument("--seed", type=int, default=20260902, help="Sabit random seed")
    ap.add_argument("--firms", type=int, default=600, help="Sentetik firma sayisi (300-2500 onerilir)")
    ap.add_argument("--out", type=str, default="data/output", help="Cikti dizini")
    ap.add_argument("--ref", type=str, default="data/reference", help="Katman A referans dizini")
    ap.add_argument("--no-excel", action="store_true", help="Excel uretimini atla")
    ap.add_argument("--no-parquet", action="store_true", help="Parquet uretimini atla")
    args = ap.parse_args()

    if args.firms < 300:
        print("UYARI: 300'den az firma ile dataset TEKNOFEST minimum olcegini karsilamaz.", file=sys.stderr)

    t0 = time.time()
    cfg = GeneratorConfig(seed=args.seed, n_firms=args.firms, out_dir=args.out)
    print(f"[1/4] Dataset uretiliyor (seed={cfg.seed}, firms={cfg.n_firms}) ...")
    b = build_dataset(cfg, ref_dir=args.ref)
    print(f"      firma={len(b.firms_public)}  gozlem={len(b.observations)}  sku={len(b.packaging)}  "
          f"prevalans={b.manifest['prevalence_overall']:.4f}")

    os.makedirs(args.out, exist_ok=True)

    print("[2/4] CSV yaziliyor ...")
    csv_dir = os.path.join(args.out, "csv")
    os.makedirs(csv_dir, exist_ok=True)
    tables = {
        "firms": b.firms_public, "observations": b.observations,
        "product_packaging": b.packaging, "model_ready": b.model_ready,
        "audit_labels": b.audit_labels, "evaluation": b.evaluation,
        "quality_checks": b.quality_checks, "climate_scenarios": b.climate_scenarios,
        "cop31_dashboard": b.cop31_dashboard,
    }
    for name, df in tables.items():
        df.to_csv(os.path.join(csv_dir, f"{name}.csv"), index=False, sep=";", encoding="utf-8-sig")

    if not args.no_parquet:
        print("[3/4] Parquet yaziliyor ...")
        pq_dir = os.path.join(args.out, "parquet")
        os.makedirs(pq_dir, exist_ok=True)
        for name, df in tables.items():
            try:
                out = df.copy()
                # Karisik tipli object sutunlari metne cevir (Parquet sema zorunlulugu)
                for c in out.columns:
                    if out[c].dtype == object:
                        out[c] = out[c].astype(str)
                out.to_parquet(os.path.join(pq_dir, f"{name}.parquet"), index=False)
            except Exception as e:
                print(f"      Parquet atlandi ({name}): {e}")
    else:
        print("[3/4] Parquet atlandi.")

    manifest_path = os.path.join(args.out, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(b.manifest, fh, ensure_ascii=False, indent=2)

    if not args.no_excel:
        print("[4/4] Excel uretiliyor ...")
        xlsx = os.path.join(args.out, cfg.excel_name)
        build_excel(b, xlsx)
        size_mb = os.path.getsize(xlsx) / 1024 / 1024
        print(f"      {xlsx}  ({size_mb:.1f} MB)")
    else:
        print("[4/4] Excel atlandi.")

    failed = b.quality_checks[b.quality_checks["durum"] == "KALDI"]
    print(f"\nKalite kontrol: {len(b.quality_checks)} kontrol, {len(failed)} KALDI")
    if len(failed):
        for r in failed.itertuples():
            print(f"  KALDI  {r.kategori} / {r.kontrol}: {r.deger} (beklenen {r.beklenen})")

    print(f"\nTamamlandi. {time.time() - t0:.1f} sn")
    return 1 if len(failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
