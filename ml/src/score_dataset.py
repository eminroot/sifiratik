"""Teslim paketiyle skorlama ve tur-donus dogrulamasi.

    python src/score_dataset.py --split test
    python src/score_dataset.py --split test --models models --out reports/queue_test.csv

Modeli YALNIZCA `models/` altindaki dosyalardan kurar. Boylece paketin
kendine yeterli oldugu ve backend'in ayni ciktiyi uretecegi gosterilir.
`--verify` verilirse ayni veri egitim hattiyla yeniden skorlanir ve iki
siralamanin birebir ayni oldugu dogrulanir.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gus_model import GusModel, ModelConfig, load_bundle              # noqa: E402
from gus_model.config import SIGNAL_CODES, signal_by_code            # noqa: E402
from gus_model.explain import reasons                                # noqa: E402
from gus_model.serving import load_model                             # noqa: E402

QUEUE_COLUMNS = [
    "observation_id", "firm_id", "period", "sector", "size_band",
    "priority_score", "priority_level", "confidence",
    "declared_tonnage", "q05_cal", "q50_cal", "q95_cal", "position",
    "shortfall_tonnage", "risk_probability", "signal_coverage",
    "active_signal_count", "conformal_group",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Teslim paketiyle skorlama")
    parser.add_argument("--models", default="models")
    parser.add_argument("--split", default="test",
                        choices=["train", "valid", "test", "history", "all"])
    parser.add_argument("--out", default="")
    parser.add_argument("--lang", default="tr", choices=["tr", "en"])
    parser.add_argument("--top", type=int, default=20, help="ekrana yazilacak kayit sayisi")
    parser.add_argument("--verify", action="store_true",
                        help="egitim hattiyla yeniden skorlayip birebir esitligi dogrula")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    cfg = ModelConfig()
    bundle = load_bundle(cfg, root)

    index = {
        "train": bundle.splits.train,
        "valid": bundle.splits.valid,
        "test": bundle.splits.test,
        "history": bundle.splits.history,
        "all": bundle.model_ready.index,
    }[args.split]
    frame = bundle.rows(index)

    model = load_model(root / args.models)
    print(f"Model paketi yuklendi: {args.models}")
    print(f"  surum {model.cfg.model_version} · veri {model.data_version} · "
          f"{len(frame)} kayit skorlanacak\n")

    scored = model.predict(frame)

    combined = pd.concat(
        [frame[["firm_id", "period", "sector", "size_band"]],
         scored.loc[:, ~scored.columns.isin(frame.columns)]],
        axis=1,
    )
    combined.insert(0, "observation_id", combined.index)
    queue = combined[[c for c in QUEUE_COLUMNS if c in combined.columns]].copy()
    queue = queue.sort_values("priority_score", ascending=False)

    shares = scored[[f"contribution_{c.lower()}" for c in SIGNAL_CODES]]
    top_signal = shares.idxmax(axis=1).str.replace("contribution_", "", regex=False).str.upper()
    queue.insert(
        queue.columns.get_loc("priority_level") + 1, "baskin_sinyal",
        [f"{code} {signal_by_code(code)['ad']}" for code in top_signal.loc[queue.index]],
    )

    head = queue.head(args.top)
    print(head[[
        "observation_id", "period", "sector", "size_band", "priority_score",
        "priority_level", "baskin_sinyal", "declared_tonnage", "q05_cal", "q50_cal",
        "shortfall_tonnage", "confidence",
    ]].to_string(index=False))

    print("\nOrnek gerekce panelleri")
    print("-" * 74)
    for observation_id in queue.index[:3]:
        row = frame.loc[observation_id]
        signal_row = scored.loc[observation_id]
        text = reasons(row, signal_row, signal_row, signal_row, lang=args.lang)
        print(f"\n{observation_id}  puan {signal_row['priority_score']:.1f} "
              f"({signal_row['priority_level']}) · veri guveni {signal_row['confidence']}")
        print(f"  beklenen aralik {signal_row['q05_cal']:.1f} - {signal_row['q95_cal']:.1f} ton "
              f"(ortanca {signal_row['q50_cal']:.1f}) · beyan {signal_row['declared_tonnage']:.1f} ton")
        for sentence in text:
            print(f"  - {sentence}")
        unavailable = [
            f"{code}: {signal_by_code(code)['avail_reason']}"
            for code in SIGNAL_CODES
            if signal_row.get(f"avail_{code.lower()}", 0) <= 0
        ]
        for item in unavailable:
            print(f"  ! degerlendirilemedi - {item}")

    if args.out:
        target = root / args.out
        target.parent.mkdir(parents=True, exist_ok=True)
        queue.to_csv(target, sep=";", index=False, encoding="utf-8-sig")
        print(f"\nKuyruk yazildi: {target}")

    if args.verify:
        print("\nTur-donus dogrulamasi ...")
        reference = GusModel(cfg).fit(bundle).predict(frame)
        same_rank = np.array_equal(
            scored["priority_score"].rank(method="first").to_numpy(),
            reference["priority_score"].rank(method="first").to_numpy(),
        )
        largest = float(
            np.nanmax(np.abs(scored["priority_score"] - reference["priority_score"]))
        )
        print(f"  siralama ayni : {same_rank}")
        print(f"  en buyuk puan farki : {largest:.6f}")
        if not same_rank or largest > 1e-6:
            print("  UYARI: paket ile egitim hatti ayni sonucu vermiyor.")
            return 1
        print("  paket kendine yeterli ve egitim hattiyla birebir ayni.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
