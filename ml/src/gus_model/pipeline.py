"""Uctan uca model hatti.

    Katman 3   iki quantile baslik -> harman -> Mondrian CQR kalibrasyonu
    Katman 4   sekiz kanit sinyali -> olcekleme -> fusion -> oncelik puani
    Katman 5   TreeSHAP katkilari -> sablonlu gerekce

UYDURMA SIRASI ve HANGI BOLUMUN NE ICIN KULLANILDIGI
----------------------------------------------------
    train     quantile basliklari, fusion modeli
    valid_a   quantile erken durdurma, harman agirligi, fusion erken durdurma
    valid_b   konformal kalibrasyon havuzunun bir parcasi
    train(OOF) konformal artiklar + olasilik kalibrasyonu + puan haritasi
    test      YALNIZCA raporlama

Ayni bolumun hem model secimi hem kalibrasyon icin kullanilmamasi kasitlidir;
aksi halde kapsama orani ve olasilik kalibrasyonu iyimser cikar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import (
    CONFIDENCE_HIGH_COVERAGE,
    CONFIDENCE_HIGH_QUALITY,
    CONFIDENCE_LOW_COVERAGE,
    CONFIDENCE_LOW_QUALITY,
    POLICY_WEIGHTS,
    SIGNAL_CODES,
    STRONGEST_SIGNAL_SHARE,
    ModelConfig,
)
from .conformal import ConformalCalibrator, build_calibrator
from .dataset import Bundle
from .explain import contribution_shares, signal_contributions
from .featureset import HIST_FEATURES, PEER_FEATURES, RISK_FEATURES, TARGET_COLUMN, log_target
from .quantile import (
    BlendedExpectation,
    QuantileHead,
    fit_cross_fitted,
    head_diagnostics,
)
from .risk import ProbabilityCalibrator, RiskModel, ScoreMap, fit_out_of_fold
from .signals import SignalScaler, interval_features, policy_fusion, raw_statistics


@dataclass
class FitDiagnostics:
    splits: pd.DataFrame = field(default_factory=pd.DataFrame)
    quantile: pd.DataFrame = field(default_factory=pd.DataFrame)
    coverage: pd.DataFrame = field(default_factory=pd.DataFrame)
    blend_weight: float = 0.5
    blend_loss: Dict[str, float] = field(default_factory=dict)
    risk_iterations: int = 0
    signal_anchors: Dict = field(default_factory=dict)


def estimate_coverage_drift(
    cfg: ModelConfig,
    train: pd.DataFrame,
    train_pred_log: pd.DataFrame,
    later: pd.DataFrame,
    later_pred_log: pd.DataFrame,
) -> float:
    """Bir sonraki donemde kaybedilen kapsamayi tahmin eder.

    Konformal garanti degisim-degismezlik (exchangeability) varsayar. Bizim
    kullanimimizda bu varsayim YAPISAL OLARAK bozuktur: aralik W doneminde
    kalibre edilir, W+1 doneminde kullanilir. Ne kadar kaybedildigini test
    bolumune bakmadan olcmenin yolu, ayni deneyi egitim penceresi ICINDE
    tekrarlamaktir:

        kalibre et   egitim penceresinin ilk ceyrekleri
        carpani ayarla  egitim penceresinin son iki ceyregi
        olc          valid bolumu (bir sonraki pencere)

    Aradaki fark, dagilim kaymasinin kapsamaya maliyetidir ve nihai carpan
    ayarina ek pay olarak eklenir. Test bolumu bu hesaba GIRMEZ.
    """
    periods = sorted(train["period"].astype(str).unique())
    if len(periods) < 4 or len(later) == 0:
        return 0.0

    tune_periods = set(periods[-2:])
    is_tune = train["period"].astype(str).isin(tune_periods).to_numpy()
    if is_tune.all() or not is_tune.any():
        return 0.0

    inner = build_calibrator(cfg).fit(
        train.loc[~is_tune], train_pred_log.loc[~is_tune], fitted_on="train (ilk ceyrekler)"
    )
    inner.tune_scale(
        train.loc[is_tune], train_pred_log.loc[is_tune], fitted_on="train (son ceyrekler)"
    )

    calibrated = inner.apply(later, later_pred_log)
    y = later[TARGET_COLUMN].astype(float).to_numpy()
    observed = float(
        ((y >= calibrated["q05_cal"].to_numpy()) & (y <= calibrated["q95_cal"].to_numpy())).mean()
    )
    return max(0.0, inner.required_coverage - observed)


@dataclass
class GusModel:
    """Egitilmis GUS-DEDEKTIV modeli."""

    cfg: ModelConfig
    hist: Optional[QuantileHead] = None
    peer: Optional[QuantileHead] = None
    blend: BlendedExpectation = field(default_factory=BlendedExpectation)
    conformal: Optional[ConformalCalibrator] = None
    scaler: SignalScaler = field(default_factory=SignalScaler)
    risk: Optional[RiskModel] = None
    probability: ProbabilityCalibrator = field(default_factory=ProbabilityCalibrator)
    score_map: ScoreMap = field(default_factory=ScoreMap)
    diagnostics: FitDiagnostics = field(default_factory=FitDiagnostics)
    coverage_drift: float = 0.0
    data_version: str = "unknown"

    # ------------------------------------------------------------------ fit --

    def fit(self, bundle: Bundle) -> "GusModel":
        cfg = self.cfg
        splits = bundle.splits
        train = bundle.rows(splits.train)
        valid_a = bundle.rows(splits.valid_a)
        valid_b = bundle.rows(splits.valid_b)

        # --- Katman 3.1: quantile basliklari -----------------------------
        self.hist = QuantileHead("hist", HIST_FEATURES).fit(cfg, train, valid_a)
        self.peer = QuantileHead("peer", PEER_FEATURES).fit(cfg, train, valid_a)

        # --- Katman 3.2: harman agirligi (valid_a) -----------------------
        hist_va = self.hist.predict_log(valid_a)
        peer_va = self.peer.predict_log(valid_a)
        self.blend = BlendedExpectation().fit_weight(
            hist_va, peer_va, log_target(valid_a[TARGET_COLUMN])
        )

        # --- Katman 3.3: konformal kalibrasyon ---------------------------
        # Kalibrasyon havuzu: egitim bolumunun ORNEKLEM DISI (capraz uydurulmus)
        # tahminleri + valid_b. Ikisi de model tarafindan gorulmemistir.
        hist_oof = fit_cross_fitted(cfg, "hist", train)
        peer_oof = fit_cross_fitted(cfg, "peer", train)
        blend_oof = self.blend.blend_log(hist_oof, peer_oof)

        hist_vb = self.hist.predict_log(valid_b)
        peer_vb = self.peer.predict_log(valid_b)
        blend_vb = self.blend.blend_log(hist_vb, peer_vb)

        if cfg.conformal_source == "valid_b":
            calibration_frame, calibration_pred = valid_b, blend_vb
            source = "valid_b"
        else:
            calibration_frame = pd.concat([train, valid_b])
            calibration_pred = pd.concat([blend_oof, blend_vb])
            source = "train(OOF) + valid_b"
        self.conformal = build_calibrator(cfg).fit(
            calibration_frame, calibration_pred, fitted_on=source
        )
        # Duzeltme carpani, kalibrasyon havuzuna GIRMEYEN valid_a uzerinde
        # ayarlanir; boylece hedef kapsama ile gozlenen kapsama arasindaki
        # sistematik fark kapanir ve grup yapisi korunur. Ayrica aralik bir
        # SONRAKI donemde kullanilacagi icin kayma payi eklenir.
        blend_va = self.blend.blend_log(hist_va, peer_va)
        self.coverage_drift = estimate_coverage_drift(
            cfg, train, blend_oof, pd.concat([valid_a, valid_b]),
            pd.concat([blend_va, blend_vb]),
        )
        self.conformal.tune_scale(
            valid_a, blend_va, fitted_on="valid_a", extra_margin=self.coverage_drift
        )

        # --- Katman 4.1: sinyal olcegi (egitim penceresinden) -------------
        train_expectation = self._expectation_from_log(hist_oof, peer_oof)
        train_raw = raw_statistics(train, train_expectation)
        self.scaler = SignalScaler().fit(train_raw, fitted_on="train (out-of-fold expectation)")

        # --- Katman 4.2: fusion modeli ------------------------------------
        train_inputs = self._risk_inputs(train, hist_oof, peer_oof, blend_oof)
        valid_inputs = self._risk_inputs(valid_a, hist_va, peer_va,
                                         self.blend.blend_log(hist_va, peer_va))
        y_train = bundle.target(splits.train)
        y_valid = bundle.target(splits.valid_a)

        self.risk = RiskModel(RISK_FEATURES).fit(cfg, train_inputs, y_train, valid_inputs, y_valid)

        # --- Katman 4.3: olasilik kalibrasyonu ve puan haritasi ------------
        oof_prob = fit_out_of_fold(
            cfg, train_inputs, y_train, train["firm_id"], self.risk.best_iteration
        )
        self.probability = ProbabilityCalibrator().fit(
            oof_prob, y_train, fitted_on="train (out-of-fold)"
        )
        self.score_map = ScoreMap().fit(
            oof_prob, prevalence=float(np.mean(y_train)),
            fitted_on="train (out-of-fold, ham olasilik)",
        )

        # --- Tani bilgileri -----------------------------------------------
        heads = {"hist": self.hist, "peer": self.peer}
        coverage = []
        for label, frame, pred in (
            ("valid_a", valid_a, self.blend.blend_log(hist_va, peer_va)),
            ("valid_b", valid_b, blend_vb),
        ):
            calibrated = self.conformal.apply(frame, pred)
            coverage.append(self.conformal.coverage_report(frame, calibrated, label))
        self.diagnostics = FitDiagnostics(
            quantile=pd.concat(
                [head_diagnostics(heads, self.blend, valid_a, "valid_a"),
                 head_diagnostics(heads, self.blend, valid_b, "valid_b")],
                ignore_index=True,
            ),
            coverage=pd.concat(coverage, ignore_index=True),
            blend_weight=self.blend.weight,
            blend_loss=self.blend.per_quantile_loss,
            risk_iterations=self.risk.best_iteration,
            signal_anchors=self.scaler.anchors,
        )
        self.data_version = bundle.data_version
        return self

    # -------------------------------------------------------------- helpers --

    @staticmethod
    def _expectation_from_log(hist_log: pd.DataFrame, peer_log: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({
            "hist_q05": np.expm1(hist_log["q05"]).clip(lower=0.0),
            "hist_q50": np.expm1(hist_log["q50"]).clip(lower=0.0),
            "hist_q95": np.expm1(hist_log["q95"]).clip(lower=0.0),
            "peer_q05": np.expm1(peer_log["q05"]).clip(lower=0.0),
            "peer_q50": np.expm1(peer_log["q50"]).clip(lower=0.0),
            "peer_q95": np.expm1(peer_log["q95"]).clip(lower=0.0),
        }, index=hist_log.index)

    def _risk_inputs(
        self,
        frame: pd.DataFrame,
        hist_log: pd.DataFrame,
        peer_log: pd.DataFrame,
        blend_log: pd.DataFrame,
    ) -> pd.DataFrame:
        expectation = self._expectation_from_log(hist_log, peer_log)
        calibrated = self.conformal.apply(frame, blend_log)
        raw = raw_statistics(frame, expectation)
        scores = self.scaler.transform(raw)
        intervals = interval_features(frame, calibrated)
        raw_only = raw[[f"raw_{c.lower()}" for c in SIGNAL_CODES]]
        return pd.concat([frame, raw_only, scores, intervals], axis=1)

    # -------------------------------------------------------------- predict --

    def predict(self, frame: pd.DataFrame, lang: str = "tr") -> pd.DataFrame:
        """Bir cerceve icin tam skorlama ciktisi."""
        if self.hist is None or self.peer is None or self.risk is None or self.conformal is None:
            raise RuntimeError("Model egitilmedi.")

        hist_log = self.hist.predict_log(frame)
        peer_log = self.peer.predict_log(frame)
        blend_log = self.blend.blend_log(hist_log, peer_log)

        expectation = self._expectation_from_log(hist_log, peer_log)
        calibrated = self.conformal.apply(frame, blend_log)

        raw = raw_statistics(frame, expectation)
        scores = self.scaler.transform(raw)
        status = self.scaler.status(scores)
        intervals = interval_features(frame, calibrated)

        inputs = pd.concat([frame, raw, scores, intervals], axis=1)
        prob_raw = self.risk.predict_proba(inputs)
        prob = self.probability.transform(prob_raw)
        priority = self.score_map.transform(prob_raw)
        level = self.score_map.levels(priority)

        shap_frame = self.risk.shap_values(inputs)
        contributions = signal_contributions(shap_frame, self.risk.features)
        shares = contribution_shares(contributions)

        policy = policy_fusion(scores, POLICY_WEIGHTS, STRONGEST_SIGNAL_SHARE)
        declared = frame[TARGET_COLUMN].astype(float).to_numpy()
        lower = calibrated["q05_cal"].to_numpy()
        upper = calibrated["q95_cal"].to_numpy()

        out = pd.concat([
            expectation, calibrated, raw, scores, status, intervals,
            contributions, shares, policy,
        ], axis=1)
        out["risk_probability_raw"] = np.round(prob_raw, 6)
        out["risk_probability"] = np.round(prob, 6)
        out["priority_score"] = priority
        out["priority_level"] = level
        out["declared_tonnage"] = declared
        out["position"] = np.where(
            declared < lower, "BELOW", np.where(declared > upper, "ABOVE", "WITHIN")
        )
        out["shortfall_tonnage"] = np.round(np.maximum(lower - declared, 0.0), 3)
        out["confidence"] = self._confidence(frame, policy)
        out["model_version"] = self.cfg.model_version
        out["data_version"] = self.data_version
        return out

    def _confidence(self, frame: pd.DataFrame, policy: pd.DataFrame) -> np.ndarray:
        coverage = policy["signal_coverage"].to_numpy(dtype=float)
        quality = frame["f_data_quality_score"].astype(float).to_numpy()
        confidence = np.full(len(frame), "MEDIUM", dtype=object)
        confidence[(coverage >= CONFIDENCE_HIGH_COVERAGE) & (quality >= CONFIDENCE_HIGH_QUALITY)] = "HIGH"
        confidence[(coverage < CONFIDENCE_LOW_COVERAGE) | (quality < CONFIDENCE_LOW_QUALITY)] = "LOW"
        return confidence

    # ------------------------------------------------------------------ io --

    def metadata(self) -> Dict:
        return {
            "model_version": self.cfg.model_version,
            "data_version": self.data_version,
            "blend_weight_hist": round(self.blend.weight, 3),
            "blend_pinball": self.blend.per_quantile_loss,
            "risk_iterations": self.risk.best_iteration if self.risk else 0,
            "quantile_iterations": {
                "hist": self.hist.best_iteration if self.hist else {},
                "peer": self.peer.best_iteration if self.peer else {},
            },
            "target_coverage": self.cfg.target_coverage,
            "coverage_drift_margin": round(self.coverage_drift, 4),
            "conformal_delta_scale": (
                round(self.conformal.delta_scale, 3) if self.conformal else None
            ),
            "seed": self.cfg.seed,
        }


__all__ = ["GusModel", "FitDiagnostics"]
