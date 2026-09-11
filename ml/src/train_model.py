"""GUS-DEDEKTIV model egitimi.

    python src/train_model.py
    python src/train_model.py --seed 20260902 --out models --report reports
    python src/train_model.py --export ../../backend/models

Egitim, kalibrasyon, degerlendirme ve teslim paketi tek komutta uretilir.
Test bolumu yalnizca degerlendirme adiminda okunur.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gus_model import GusModel, ModelConfig, load_bundle, split_report   # noqa: E402
from gus_model import evaluate as ev                                     # noqa: E402
from gus_model.export import export                                      # noqa: E402
from gus_model.report import write_reports                               # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GUS-DEDEKTIV model egitimi")
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--data", default="data/output/parquet")
    parser.add_argument("--out", default="models", help="model dosyalarinin yazilacagi dizin")
    parser.add_argument("--report", default="reports", help="degerlendirme raporlari dizini")
    parser.add_argument(
        "--export", default="", help="backend teslim dizini (ornek: ../../backend/models)"
    )
    parser.add_argument(
        "--train-on-history", action="store_true",
        help="2023 burn-in bolumunu de egitime kat (varsayilan: katma)",
    )
    parser.add_argument("--no-ablation", action="store_true", help="ablation testini atla")
    parser.add_argument("--bootstrap", type=int, default=2000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    started = time.perf_counter()

    cfg = ModelConfig(
        seed=args.seed,
        data_dir=args.data,
        out_dir=args.out,
        report_dir=args.report,
        train_on_history=args.train_on_history,
        bootstrap_n=args.bootstrap,
    )

    print("GUS-DEDEKTIV - model egitimi")
    print("=" * 74)

    bundle = load_bundle(cfg, root)
    splits = split_report(bundle)
    print(splits.to_string(index=False))
    print()

    print("Katman 3-4 uydurulyor ...")
    model = GusModel(cfg).fit(bundle)
    print(f"  harman agirligi (tarihsel baslik payi) : {model.blend.weight:.2f}")
    print(f"  fusion yineleme sayisi                 : {model.risk.best_iteration}")
    print()

    print("Quantile basliklari - pinball kaybi ve ham kapsama")
    print(model.diagnostics.quantile.to_string(index=False))
    print()
    print("Konformal kapsama (kalibrasyon sonrasi)")
    print(model.diagnostics.coverage.to_string(index=False))
    print()

    print("Skorlaniyor ...")
    scored = {
        name: model.predict(bundle.rows(index))
        for name, index in (
            ("train", bundle.splits.train),
            ("valid", bundle.splits.valid),
            ("test", bundle.splits.test),
        )
    }

    reports = write_reports(model, bundle, scored, cfg, root, run_ablation=not args.no_ablation)

    out_dir = root / cfg.out_dir
    written = export(
        model,
        out_dir,
        metrics=reports["metrics"],
        notes=[
            "Sentetik veri uzerinde egitilmistir; gercek kamu performansi degildir.",
            f"Zamansal holdout: train={reports['periods']['train']} "
            f"valid={reports['periods']['valid']} test={reports['periods']['test']}",
        ],
    )
    print(f"\nModel paketi yazildi: {out_dir}")
    for name in sorted(written):
        print(f"  {name}")

    if args.export:
        target = (root / args.export).resolve()
        export(model, target, metrics=reports["metrics"])
        print(f"\nBackend teslim paketi: {target}")

    print(f"\nToplam sure: {time.perf_counter() - started:.1f} sn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
