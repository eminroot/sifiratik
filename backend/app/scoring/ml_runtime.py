"""Loading and running the delivered model artefacts.

This module is the backend's half of the contract written by the model
repository's `gus_model.export`. It knows how to read the files and how to put
a record through the model; it knows nothing about the ORM, the API or the
company records, which is what lets it be tested against the model repository's
own predictions and required to agree with them exactly.

The order of operations mirrors the training pipeline, and has to:

    1. structural anchor            density x activity, in log space
    2. two quantile heads           own history, and peers
    3. blend                        weighted mean of the two, in log space
    4. conformal calibration        Mondrian CQR widening for the row's group
    5. eight evidence signals       raw statistic, availability, 0-100 score
    6. fusion                       gradient boosted ensemble over the signals
    7. isotonic calibration         raw margin to a probability
    8. score map                    probability to 0-100 against the reference

Only numpy and lightgbm are needed. Nothing here imports pandas, and nothing
imports the model repository: the artefacts are the whole interface.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

try:  # pragma: no cover - exercised by the absence of the dependency
    import lightgbm as lgb
except ImportError:  # pragma: no cover
    lgb = None  # type: ignore[assignment]

EPS = 1e-9
QUANTILES = ("q05", "q50", "q95")
SIGNAL_CODES = ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8")

# Group levels the conformal tables are keyed by, most specific first. Must
# match `gus_model.conformal.GROUP_LEVELS`.
GROUP_LEVELS: tuple[tuple[str, ...], ...] = (
    ("sector", "size_band"),
    ("sector",),
    ("size_band",),
    (),
)
GLOBAL_KEY = "*"

# Anchor sources per head: (density column, activity column). The first pair
# that yields a finite positive product wins. Must match
# `gus_model.quantile.ANCHOR_SOURCES`.
ANCHOR_SOURCES: dict[str, tuple[tuple[str, str | None], ...]] = {
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

MIN_BOM_COVERAGE = 0.05


class ArtifactError(RuntimeError):
    """The artefact set is missing, incomplete or of an unexpected shape."""


def _as_float(value: Any) -> float:
    if value is None:
        return math.nan
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def _column(rows: Sequence[dict], name: str) -> np.ndarray:
    return np.array([_as_float(row.get(name)) for row in rows], dtype=float)


def _flag(rows: Sequence[dict], name: str) -> np.ndarray:
    return _column(rows, name) > 0.5


def _ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    out = np.full(numerator.shape, np.nan)
    usable = np.isfinite(numerator) & np.isfinite(denominator) & (np.abs(denominator) > EPS)
    out[usable] = numerator[usable] / denominator[usable]
    return out


# --------------------------------------------------------------------------- #
# Prediction result
# --------------------------------------------------------------------------- #


@dataclass
class SignalReading:
    code: str
    raw: float
    score: float | None
    available: bool
    contribution: float


@dataclass
class Prediction:
    hist_median: float
    peer_median: float
    lower: float
    median: float
    upper: float
    conformal_group: str
    interval_position_z: float
    priority_score: float
    risk_probability: float
    signals: list[SignalReading]
    signal_coverage: float
    active_signal_count: int


# --------------------------------------------------------------------------- #
# Runtime
# --------------------------------------------------------------------------- #


@dataclass
class MLRuntime:
    directory: Path
    manifest: dict = field(default_factory=dict)
    calibration: dict = field(default_factory=dict)
    conformal: dict = field(default_factory=dict)
    signal_spec: dict = field(default_factory=dict)
    hist: dict = field(default_factory=dict)
    peer: dict = field(default_factory=dict)
    risk: list = field(default_factory=list)

    # --------------------------------------------------------------- load --

    @classmethod
    def load(cls, directory: Path) -> "MLRuntime":
        if lgb is None:
            raise ArtifactError(
                "lightgbm is not installed, so the delivered model cannot be run."
            )
        directory = Path(directory)
        runtime = cls(directory=directory)
        runtime.manifest = _read_json(directory / "manifest.json")
        runtime.calibration = _read_json(directory / "calibration.json")
        runtime.conformal = _read_json(directory / "conformal.json")
        runtime.signal_spec = _read_json(directory / "signals.json")

        for head in ("hist", "peer"):
            boosters = {}
            for quantile in QUANTILES:
                path = directory / f"quantile_{head}_{quantile}.txt"
                boosters[quantile] = lgb.Booster(model_file=str(path))
            setattr(runtime, head, boosters)

        members = runtime.manifest.get("risk_members") or ["risk_model.txt"]
        runtime.risk = [lgb.Booster(model_file=str(directory / name)) for name in members]

        missing = [
            name for name in ("feature_order", "categories") if name not in runtime.manifest
        ]
        if missing:
            raise ArtifactError(
                "manifest.json is missing " + ", ".join(missing) + "; the feature "
                "layout cannot be reconstructed and predictions would be silently wrong."
            )
        return runtime

    @property
    def version(self) -> str:
        return str(self.manifest.get("version", "unknown"))

    @property
    def data_version(self) -> str:
        return str(self.manifest.get("data_version", "unknown"))

    @property
    def target_coverage(self) -> float:
        return float(self.manifest.get("target_coverage", 0.90))

    def signal_meta(self, code: str) -> dict:
        return self.signal_spec.get("signals", {}).get(code, {})

    # ------------------------------------------------------------- matrix --

    def _matrix(self, rows: Sequence[dict], head: str) -> np.ndarray:
        order = self.manifest["feature_order"][head]
        categories = self.manifest["categories"].get(head, {})
        matrix = np.empty((len(rows), len(order)), dtype=float)

        for column, name in enumerate(order):
            levels = categories.get(name)
            if levels is not None:
                # LightGBM was trained on pandas categoricals, so it expects the
                # position of the level, and treats NaN as "unseen".
                lookup = {level: float(i) for i, level in enumerate(levels)}
                matrix[:, column] = [
                    lookup.get(_category(row.get(name)), math.nan) for row in rows
                ]
            elif name == "log_production":
                matrix[:, column] = np.log1p(
                    np.clip(_column(rows, "production_qty"), 0.0, None)
                )
            elif name in _LOG1P_COLUMNS:
                matrix[:, column] = np.log1p(np.clip(_column(rows, name), 0.0, None))
            else:
                matrix[:, column] = _column(rows, name)
        return matrix

    # ------------------------------------------------------------ anchors --

    def _anchor_log(self, rows: Sequence[dict], head: str) -> np.ndarray:
        fallback = float(
            self.manifest.get("anchor_fallback_log", {}).get(head, 0.0)
        )
        out = np.full(len(rows), np.nan)
        for density, activity in ANCHOR_SOURCES[head]:
            value = _column(rows, density)
            if activity is not None:
                value = value * _column(rows, activity)
            pending = np.isnan(out) & np.isfinite(value) & (value > 0)
            out[pending] = value[pending]
        anchor = np.log1p(np.clip(out, 0.0, None))
        return np.where(np.isfinite(anchor), anchor, fallback)

    def _quantiles_log(self, rows: Sequence[dict], head: str) -> np.ndarray:
        matrix = self._matrix(rows, head)
        anchor = self._anchor_log(rows, head)
        boosters = getattr(self, head)
        stacked = np.column_stack([
            np.asarray(boosters[quantile].predict(matrix), dtype=float) + anchor
            for quantile in QUANTILES
        ])
        return np.sort(stacked, axis=1)

    # ---------------------------------------------------------- conformal --

    def _conformal_delta(self, rows: Sequence[dict]) -> tuple[np.ndarray, list[str]]:
        tables = self.conformal.get("tables", [])
        min_group = int(self.conformal.get("min_group", 60))
        thin_widen = float(self.conformal.get("thin_widen", 1.15))
        scale = float(self.conformal.get("delta_scale", 1.0))

        deltas = np.full(len(rows), np.nan)
        levels = [GLOBAL_KEY] * len(rows)
        thin = np.ones(len(rows), dtype=bool)

        for enough in (True, False):
            for table, level in zip(tables, GROUP_LEVELS):
                if not table:
                    continue
                for index, row in enumerate(rows):
                    if not math.isnan(deltas[index]):
                        continue
                    entry = table.get(_group_key(row, level))
                    if not entry:
                        continue
                    if enough and int(entry.get("n", 0)) < min_group:
                        continue
                    deltas[index] = float(entry["delta"])
                    levels[index] = "|".join(level) or GLOBAL_KEY
                    thin[index] = not enough
            if not np.isnan(deltas).any():
                break

        deltas = np.where(thin & np.isfinite(deltas), deltas * thin_widen, deltas)
        return np.nan_to_num(deltas, nan=0.0) * scale, levels

    # ------------------------------------------------------------ signals --

    def _raw_statistics(
        self, rows: Sequence[dict], hist_median: np.ndarray, peer_median: np.ndarray
    ) -> dict[str, np.ndarray]:
        """The eight raw statistics and their availability.

        Mirrors `gus_model.signals.raw_statistics`. Every definition here has a
        counterpart there; changing one without the other makes the delivered
        thresholds meaningless.
        """
        declared = _column(rows, "declared_packaging_tonnage")
        raw: dict[str, np.ndarray] = {}
        available: dict[str, np.ndarray] = {}

        raw["S1"] = 1.0 - _ratio(declared, hist_median)
        available["S1"] = _flag(rows, "f_avail_s1") & np.isfinite(hist_median) & (hist_median > EPS)

        raw["S2"] = 1.0 - _ratio(declared, peer_median)
        available["S2"] = _flag(rows, "f_avail_s2") & np.isfinite(peer_median) & (peer_median > EPS)

        # The product tree covers only part of the range, so its expectation is
        # scaled back up by the coverage ratio before being compared.
        bom = _column(rows, "f_s3_bom_expected")
        coverage = _column(rows, "f_s3_bom_coverage")
        usable = np.isfinite(coverage) & (coverage > MIN_BOM_COVERAGE)
        expected_full = np.full(len(rows), np.nan)
        expected_full[usable] = bom[usable] / coverage[usable]
        raw["S3"] = 1.0 - _ratio(declared, expected_full)
        available["S3"] = (
            _flag(rows, "f_avail_s3") & usable & np.isfinite(expected_full)
            & (expected_full > EPS)
        )

        yoy = _column(rows, "f_s4_divergence_yoy")
        qoq = _column(rows, "f_s4_divergence_qoq")
        divergence = np.where(np.isfinite(yoy), yoy, qoq)
        raw["S4"] = -divergence
        available["S4"] = _flag(rows, "f_avail_s4") & np.isfinite(divergence)

        raw["S5"] = 1.0 - _column(rows, "f_s5_dpd_vs_hist")
        available["S5"] = _flag(rows, "f_avail_s5") & np.isfinite(raw["S5"])

        raw["S6"] = -_column(rows, "f_s6_seasonal_resid")
        available["S6"] = _flag(rows, "f_avail_s6") & np.isfinite(raw["S6"])

        multiplier = float(self.signal_spec.get("stale_matrix_multiplier", 0.35))
        mix_shift = _column(rows, "f_s7_mix_shift_l1")
        stale = _flag(rows, "f_s7_matrix_stale_flag").astype(float)
        raw["S7"] = mix_shift * (1.0 + multiplier * stale)
        available["S7"] = _flag(rows, "f_avail_s7") & np.isfinite(mix_shift)

        raw["S8"] = _column(rows, "f_s8_external_gap_rel")
        available["S8"] = _flag(rows, "f_avail_s8") & np.isfinite(raw["S8"])

        for code in SIGNAL_CODES:
            raw[code] = np.where(available[code], raw[code], np.nan)
        return {"raw": raw, "available": available}

    def _signal_scores(self, raw: dict[str, np.ndarray], available: dict[str, np.ndarray]):
        floor = float(self.signal_spec.get("low_percentile", 70.0)) / 100.0
        scores: dict[str, np.ndarray] = {}
        for code in SIGNAL_CODES:
            meta = self.signal_meta(code)
            breaks = np.asarray(meta.get("breaks", []), dtype=float)
            values = raw[code]
            if breaks.size:
                grid = np.linspace(0.0, 1.0, len(breaks))
                percentile = np.interp(values, breaks, grid)
            else:
                low, high = float(meta.get("low", 0.0)), float(meta.get("high", 1.0))
                percentile = np.clip((values - low) / max(high - low, EPS), 0.0, 1.0)
            score = np.clip((percentile - floor) / max(1.0 - floor, EPS), 0.0, 1.0) * 100.0
            # A declaration above its expectation never scores, whatever its rank.
            score = np.where(np.isfinite(values) & (values <= 0.0), 0.0, score)
            scores[code] = np.where(available[code], np.round(score, 2), np.nan)
        return scores

    # --------------------------------------------------------------- score --

    def predict(self, rows: Sequence[dict]) -> list[Prediction]:
        if not rows:
            return []

        hist_log = self._quantiles_log(rows, "hist")
        peer_log = self._quantiles_log(rows, "peer")

        weight = float(self.calibration["blend"]["weight_hist"])
        blend_log = np.empty_like(hist_log)
        for column in range(hist_log.shape[1]):
            head, peers = hist_log[:, column], peer_log[:, column]
            both = np.isfinite(head) & np.isfinite(peers)
            blended = np.where(np.isfinite(head), head, peers)
            blended[both] = weight * head[both] + (1.0 - weight) * peers[both]
            blend_log[:, column] = blended
        blend_log = np.sort(blend_log, axis=1)

        delta, groups = self._conformal_delta(rows)
        lower_log = np.minimum(blend_log[:, 0] - delta, blend_log[:, 1])
        upper_log = np.maximum(blend_log[:, 2] + delta, blend_log[:, 1])
        median_log = blend_log[:, 1]

        lower = np.expm1(lower_log).clip(min=0.0)
        median = np.expm1(median_log).clip(min=0.0)
        upper = np.expm1(upper_log).clip(min=0.0)

        hist_median = np.expm1(hist_log[:, 1]).clip(min=0.0)
        peer_median = np.expm1(peer_log[:, 1]).clip(min=0.0)

        statistics = self._raw_statistics(rows, hist_median, peer_median)
        raw, available = statistics["raw"], statistics["available"]
        scores = self._signal_scores(raw, available)

        declared = _column(rows, "declared_packaging_tonnage")
        declared_log = np.log1p(np.clip(declared, 0.0, None))
        half = np.maximum(median_log - lower_log, 1e-3)
        interval = {
            "interval_position_z": (lower_log - declared_log) / half,
            "interval_rel_gap": 1.0 - _ratio(declared, median),
            "interval_width_rel": _ratio(upper - lower, median),
            "interval_below_lower": (declared < lower).astype(float),
        }

        enriched = []
        for index, row in enumerate(rows):
            extra = dict(row)
            for code in SIGNAL_CODES:
                key = code.lower()
                extra[f"raw_{key}"] = raw[code][index]
                extra[f"sig_{key}"] = scores[code][index]
                extra[f"avail_{key}"] = float(available[code][index])
            for name, values in interval.items():
                extra[name] = values[index]
            enriched.append(extra)

        risk_matrix = self._matrix(enriched, "risk")
        margins = np.mean(
            [np.asarray(b.predict(risk_matrix, raw_score=True), dtype=float) for b in self.risk],
            axis=0,
        )
        contributions = np.mean(
            [np.asarray(b.predict(risk_matrix, pred_contrib=True), dtype=float) for b in self.risk],
            axis=0,
        )
        probability_raw = 1.0 / (1.0 + np.exp(-margins))
        probability = _isotonic(self.calibration["probability"], probability_raw)
        priority = _score_map(self.calibration["score_map"], probability_raw)

        shares = self._contribution_shares(contributions)
        weights = self.calibration.get("policy_fusion", {}).get("weights", {})
        total_weight = sum(float(v) for v in weights.values()) or 1.0

        results: list[Prediction] = []
        for index in range(len(rows)):
            readings = [
                SignalReading(
                    code=code,
                    raw=float(raw[code][index]),
                    score=(
                        None if not available[code][index] else float(scores[code][index])
                    ),
                    available=bool(available[code][index]),
                    contribution=float(shares[index, position]),
                )
                for position, code in enumerate(SIGNAL_CODES)
            ]
            covered = sum(
                float(weights.get(reading.code, 0.0)) for reading in readings if reading.available
            )
            results.append(
                Prediction(
                    hist_median=float(hist_median[index]),
                    peer_median=float(peer_median[index]),
                    lower=float(lower[index]),
                    median=float(median[index]),
                    upper=float(upper[index]),
                    conformal_group=groups[index],
                    interval_position_z=float(interval["interval_position_z"][index]),
                    priority_score=float(priority[index]),
                    risk_probability=float(probability[index]),
                    signals=readings,
                    signal_coverage=round(covered / total_weight, 4),
                    active_signal_count=int(sum(r.available for r in readings)),
                )
            )
        return results

    def _contribution_shares(self, contributions: np.ndarray) -> np.ndarray:
        """Positive SHAP mass per signal, normalised to sum to one.

        A signal's contribution is the sum over every input that belongs to it,
        which for this model is its raw statistic and its availability flag.
        Only positive contributions are shared out: the question the panel
        answers is what pushed this file up the queue.
        """
        order = self.manifest["feature_order"]["risk"]
        grouped = np.zeros((contributions.shape[0], len(SIGNAL_CODES)))
        for position, code in enumerate(SIGNAL_CODES):
            key = code.lower()
            columns = [
                i for i, name in enumerate(order)
                if name in (f"raw_{key}", f"sig_{key}", f"avail_{key}")
            ]
            if columns:
                grouped[:, position] = contributions[:, columns].sum(axis=1)
        positive = np.clip(grouped, 0.0, None)
        total = positive.sum(axis=1, keepdims=True)
        return np.divide(positive, total, out=np.zeros_like(positive), where=total > 1e-12)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_LOG1P_COLUMNS = {
    "production_qty",
    "f_s1_decl_lag1",
    "f_s1_decl_lag2",
    "f_s1_decl_lag3",
    "f_s1_decl_lag4",
    "f_s1_hist_median",
    "f_s1_hist_p10",
    "f_s1_hist_std",
    "f_s3_bom_expected",
    "f_s4_prod_lag1",
    "f_s4_prod_lag4",
    "f_s5_domestic_derived",
    "f_s5_correction_qty",
}


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise ArtifactError(f"Missing artefact: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ArtifactError(f"{path.name} is not valid JSON: {error}") from error


def _category(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text and text.lower() != "nan" else None


def _group_key(row: dict, level: tuple[str, ...]) -> str:
    if not level:
        return GLOBAL_KEY
    return "|".join(str(row.get(name)) for name in level)


def _isotonic(spec: dict, values: np.ndarray) -> np.ndarray:
    knots_x = np.asarray(spec.get("x", []), dtype=float)
    knots_y = np.asarray(spec.get("y", []), dtype=float)
    if knots_x.size == 0:
        return values
    return np.interp(values, knots_x, knots_y)


def _score_map(spec: dict, values: np.ndarray) -> np.ndarray:
    reference = np.asarray(spec.get("reference_quantiles", []), dtype=float)
    anchors = spec.get("anchors", [[0.0, 0.0], [1.0, 100.0]])
    if reference.size == 0:
        percentile = np.clip(values, 0.0, 1.0)
    else:
        grid = np.linspace(0.0, 1.0, len(reference))
        percentile = np.interp(values, reference, grid)
    xs = [float(a[0]) for a in anchors]
    ys = [float(a[1]) for a in anchors]
    return np.round(np.clip(np.interp(percentile, xs, ys), 0.0, 100.0), 4)


__all__ = ["MLRuntime", "Prediction", "SignalReading", "ArtifactError", "SIGNAL_CODES"]
