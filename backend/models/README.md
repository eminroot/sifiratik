# Model artefacts

Produced by the model repository (`ml/`) and read by
`app/scoring/ml_runtime.py`. With them present and lightgbm installed, the
model engine serves; without either, `resolve_engine` falls back to the rule
engine and every response says which one produced it.

    quantile_hist_q05.txt   own-history quantile head, 5th percentile
    quantile_hist_q50.txt   median
    quantile_hist_q95.txt   95th percentile
    quantile_peer_q05.txt   peer-and-output head, which never sees the
    quantile_peer_q50.txt   company's own filing history, so a company that
    quantile_peer_q95.txt   has under-declared for years cannot talk it down
    risk_model.txt          signal fusion, first ensemble member
    risk_model_2..5.txt     the remaining members; log-odds are averaged
    conformal.json          Mondrian CQR widening, keyed by sector, size band
                            and data confidence, with the scale correction
    signals.json            per-signal scale learned on the training window
    calibration.json        blend weight, isotonic fit, score map, bands
    manifest.json           version, feature order, categories, metrics

`manifest.json` carries `feature_order` and `categories`, and they are binding:
the runtime rebuilds the feature matrix from them. A mismatch would make
lightgbm read the wrong column and predict confidently from nonsense, so the
runtime refuses to load without them.

## Regenerating

From the model repository root:

```bash
python src/train_model.py --export ../backend/models
```

The artefacts are committed, so a fresh checkout runs the model engine with no
extra step. They are delivered with a version rather than a diff: replace the
whole set, never a single file. `python src/score_dataset.py --split test
--verify` checks that a bundle scores identically to the pipeline that produced
it.

## What the figures mean

`manifest.json` holds the metrics the model was accepted on, measured on a
held-out later period. They come from **synthetic** data and are not evidence
of performance on real declarations. The priority score is an inspection
priority, not a probability of wrongdoing.
