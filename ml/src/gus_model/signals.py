"""Katman 4 - sekiz ayri kanit sinyali.

Her sinyal tek bir soru sorar ve UC durumdan birini bildirir:

    ACTIVE       atesledi
    CLEAR        bakildi, bulgu yok
    UNAVAILABLE  bakilamadi - NEDENI ile birlikte

Ucuncu durum asla ikinciye katlanmaz. "Veri yok" dusuk risk DEGILDIR.

OLCEKLEME
---------
Sinyallerin ham istatistikleri farkli birimlerdedir (oransal fark, L1 kayma,
esneklik) ve kuyruk kalinliklari cok farklidir. Bunlari toplayabilmek icin her
biri EGITIM PENCERESINDEKI KENDI DAGILIMININ yuzdeligine cevrilir, sonra
`SIGNAL_RAMP_LOW_PCT` ile 100 arasi gerilir. Boylece "60 puan" her sinyalde
ayni seyi ifade eder: egitim penceresinde bu kadar nadir. Ayrintili gerekce
`SignalScaler` icindedir.

Notr taban korunur: ham istatistik sifirin altindaysa - yani beyan beklentinin
USTUNDEYSE - puan her halukarda 0'dir. Yuzdelik capalari ve donusum tablosu
`signals.json` icine yazilir; backend ayni olcegi kullanir.

Sinyaller BAGIMSIZ DEGILDIR, AYRIDIR. Korelasyonlari `evaluate.py` icinde
korelasyon matrisi ve ablation ile olculur.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import (
    SIGNAL_ACTIVE_THRESHOLD,
    SIGNAL_CODES,
    SIGNAL_RAMP_HIGH_PCT,
    SIGNAL_RAMP_LOW_PCT,
    SIGNAL_SPECS,
    signal_by_code,
)

_EPS = 1e-9

STATUS_ACTIVE = "ACTIVE"
STATUS_CLEAR = "CLEAR"
STATUS_UNAVAILABLE = "UNAVAILABLE"

# Urun agaci beklentisinin kapsam oranina bolunerek genisletilebilmesi icin
# gereken en dusuk kapsam. Bunun altinda bolme sayisal olarak guvenilmez ve
# S3 kullanilamaz isaretlenir - dataset ureticinin de kullandigi esiktir.
MIN_BOM_COVERAGE = 0.05

# S7'de eskimis agirlik matrisi ham istatistigi buyuten carpan. Matris
# guncellenmemisse ayni malzeme kaymasi daha suphelidir.
STALE_MATRIX_MULTIPLIER = 0.35


def _safe_ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    out = np.full(a.shape, np.nan)
    mask = np.isfinite(b) & (np.abs(b) > _EPS) & np.isfinite(a)
    out[mask] = a[mask] / b[mask]
    return out


def _col(frame: pd.DataFrame, name: str) -> np.ndarray:
    if name not in frame.columns:
        return np.full(len(frame), np.nan)
    return frame[name].astype(float).to_numpy()


def _flag(frame: pd.DataFrame, name: str) -> np.ndarray:
    if name not in frame.columns:
        return np.zeros(len(frame), dtype=bool)
    return frame[name].fillna(0).astype(float).to_numpy() > 0.5


# --------------------------------------------------------------------------
# Ham istatistikler
# --------------------------------------------------------------------------
def raw_statistics(
    frame: pd.DataFrame,
    expectation: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Her sinyal icin ham istatistik ve kullanilabilirlik.

    `expectation`, `hist_q50` ve `peer_q50` sutunlarini tasiyan bir cerceve
    olmalidir (ton cinsinden). Yoksa S1 ve S2 kullanilamaz isaretlenir.
    """
    declared = _col(frame, "declared_packaging_tonnage")
    out = pd.DataFrame(index=frame.index)

    if expectation is not None:
        hist_q50 = expectation.reindex(frame.index)["hist_q50"].to_numpy(dtype=float)
        peer_q50 = expectation.reindex(frame.index)["peer_q50"].to_numpy(dtype=float)
    else:
        hist_q50 = np.full(len(frame), np.nan)
        peer_q50 = np.full(len(frame), np.nan)

    # S1 - kendi gecmisinden turetilen beklentiye gore eksiklik
    out["raw_s1"] = 1.0 - _safe_ratio(declared, hist_q50)
    out["available_s1"] = _flag(frame, "f_avail_s1") & np.isfinite(hist_q50) & (hist_q50 > _EPS)

    # S2 - emsal beklentisine gore eksiklik
    out["raw_s2"] = 1.0 - _safe_ratio(declared, peer_q50)
    out["available_s2"] = _flag(frame, "f_avail_s2") & np.isfinite(peer_q50) & (peer_q50 > _EPS)

    # S3 - urun agacindan beklenen tonaja gore eksiklik.
    #
    # Ham `f_s3_bom_gap_rel`, urun agacinin YALNIZCA KAPSANAN kismindan gelen
    # beklentiyi kullanir. Kapsam ortalama %58 oldugu icin bu beklenti butun
    # firmalarda sistematik olarak DUSUKTUR: kayitlarin yalnizca %3,4'unde
    # beyan bu kismi beklentinin altinda kalir. Yani ham istatistik esas olarak
    # KAPSAMI olcer, eksik beyani degil.
    #
    # Kapsam orani gozlenen bir alandir; beklenti ona bolunerek tam urun
    # agacina genisletilir. Dedektorun latent beklentiyi gozlenen alanlardan
    # CIKARSAMASI beklenir - yapilan islem tam olarak budur. Olculdu:
    # tek basina ROC-AUC 0,611 -> 0,666, PR-AUC 0,138 -> 0,233 (test).
    bom = _col(frame, "f_s3_bom_expected")
    coverage = _col(frame, "f_s3_bom_coverage")
    usable_coverage = np.isfinite(coverage) & (coverage > MIN_BOM_COVERAGE)
    expected_full = np.divide(
        bom, coverage, out=np.full(len(frame), np.nan), where=usable_coverage
    )
    out["raw_s3"] = 1.0 - _safe_ratio(declared, expected_full)
    out["available_s3"] = (
        _flag(frame, "f_avail_s3") & usable_coverage & np.isfinite(expected_full)
        & (expected_full > _EPS)
    )

    # S4 - faaliyet ile beyan hareketinin ayrismasi (beyan geride kaliyorsa risk)
    div_yoy = _col(frame, "f_s4_divergence_yoy")
    div_qoq = _col(frame, "f_s4_divergence_qoq")
    divergence = np.where(np.isfinite(div_yoy), div_yoy, div_qoq)
    out["raw_s4"] = -divergence
    out["available_s4"] = _flag(frame, "f_avail_s4") & np.isfinite(divergence)

    # S5 - ic piyasa arzina gore beyan oraninin kendi gecmisine gore dususu
    out["raw_s5"] = 1.0 - _col(frame, "f_s5_dpd_vs_hist")
    out["available_s5"] = _flag(frame, "f_avail_s5") & np.isfinite(out["raw_s5"].to_numpy())

    # S6 - ayni ceyregin kendi kalibina gore kirilma
    out["raw_s6"] = -_col(frame, "f_s6_seasonal_resid")
    out["available_s6"] = _flag(frame, "f_avail_s6") & np.isfinite(out["raw_s6"].to_numpy())

    # S7 - malzeme kompozisyonundaki aciklanamayan kayma; eskimis matris buyutur
    mix_shift = _col(frame, "f_s7_mix_shift_l1")
    stale = _flag(frame, "f_s7_matrix_stale_flag").astype(float)
    out["raw_s7"] = mix_shift * (1.0 + STALE_MATRIX_MULTIPLIER * stale)
    out["available_s7"] = _flag(frame, "f_avail_s7") & np.isfinite(mix_shift)

    # S8 - dis kanit (ERP / onceki denetim) ile beyan farki
    out["raw_s8"] = _col(frame, "f_s8_external_gap_rel")
    out["available_s8"] = _flag(frame, "f_avail_s8") & np.isfinite(out["raw_s8"].to_numpy())

    for code in SIGNAL_CODES:
        key = code.lower()
        out[f"available_{key}"] = out[f"available_{key}"].astype(bool)
        out.loc[~out[f"available_{key}"], f"raw_{key}"] = np.nan
    return out


# --------------------------------------------------------------------------
# Olcekleme
# --------------------------------------------------------------------------
GRID_POINTS = 201


@dataclass
class SignalScaler:
    """Ham istatistigi 0-100 kanit puanina cevirir.

    Donusum DOGRUSAL DEGIL, YUZDELIK tabanlidir: ham deger once egitim
    penceresindeki kendi dagiliminin yuzdeligine cevrilir, sonra `low_pct`
    ile 100 arasi gerilir.

    Neden dogrusal rampa degil: sekiz istatistigin kuyruk kalinliklari cok
    farklidir. Dogrusal rampada S3'un uzun kuyrugu tum olcegi yutuyor ve
    kayitlarin yalnizca %2,9'u atesliyordu; S1 ise %17,8. Ayni "60 puan" iki
    sinyalde bambaska bir seyrekligi ifade ediyordu - halbuki puanlarin
    toplanabilmesi icin AYNI seyi ifade etmeleri gerekir. Yuzdelik tabanli
    donusumde 60 puan her sinyalde ayni sey demektir: "egitim penceresinde bu
    kadar nadir".

    Notr taban korunur: ham istatistik sifirin altindaysa (yani beyan
    beklentinin USTUNDE) puan her halukarda 0'dir.
    """

    anchors: Dict[str, Dict[str, float]] = field(default_factory=dict)
    breaks: Dict[str, List[float]] = field(default_factory=dict)
    active_threshold: float = SIGNAL_ACTIVE_THRESHOLD
    low_pct: float = SIGNAL_RAMP_LOW_PCT
    high_pct: float = SIGNAL_RAMP_HIGH_PCT
    fitted_on: str = ""

    def fit(self, raw: pd.DataFrame, fitted_on: str = "") -> "SignalScaler":
        self.anchors = {}
        self.breaks = {}
        grid = np.linspace(0.0, 1.0, GRID_POINTS)
        for code in SIGNAL_CODES:
            key = code.lower()
            values = raw.loc[raw[f"available_{key}"], f"raw_{key}"].to_numpy(dtype=float)
            values = values[np.isfinite(values)]
            if len(values) < 30:
                # Cok az gozlem: dagilim guvenilir degil. Notrden 1'e kadar
                # muhafazakar bir dogrusal varsayilan kullanilir.
                quantiles = list(np.linspace(0.0, 1.0, GRID_POINTS))
            else:
                quantiles = [float(v) for v in np.quantile(values, grid)]
            self.breaks[code] = quantiles
            self.anchors[code] = {
                "low": round(float(np.interp(self.low_pct / 100.0, grid, quantiles)), 6),
                "high": round(float(np.interp(self.high_pct / 100.0, grid, quantiles)), 6),
                "n": int(len(values)),
                "availability_rate": round(float(raw[f"available_{key}"].mean()), 4),
            }
        self.fitted_on = fitted_on
        return self

    def _percentile(self, code: str, values: np.ndarray) -> np.ndarray:
        quantiles = np.asarray(self.breaks.get(code) or [], dtype=float)
        if quantiles.size == 0:
            low = float(self.anchors.get(code, {}).get("low", 0.0))
            high = float(self.anchors.get(code, {}).get("high", 1.0))
            return np.clip((values - low) / max(high - low, _EPS), 0.0, 1.0)
        grid = np.linspace(0.0, 1.0, len(quantiles))
        return np.interp(values, quantiles, grid)

    def transform(self, raw: pd.DataFrame) -> pd.DataFrame:
        floor = self.low_pct / 100.0
        out = pd.DataFrame(index=raw.index)
        for code in SIGNAL_CODES:
            key = code.lower()
            values = raw[f"raw_{key}"].to_numpy(dtype=float)
            percentile = self._percentile(code, values)
            score = np.clip((percentile - floor) / max(1.0 - floor, _EPS), 0.0, 1.0) * 100.0
            # Notr taban: beklentinin ustunde beyan asla puan almaz.
            score = np.where(np.isfinite(values) & (values <= 0.0), 0.0, score)
            score = np.where(raw[f"available_{key}"].to_numpy(), score, np.nan)
            out[f"sig_{key}"] = np.round(score, 2)
            out[f"avail_{key}"] = raw[f"available_{key}"].astype(int)
        out["active_signal_count"] = out[[f"avail_{c.lower()}" for c in SIGNAL_CODES]].sum(axis=1)
        return out

    def status(self, scores: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=scores.index)
        for code in SIGNAL_CODES:
            key = code.lower()
            available = scores[f"avail_{key}"].to_numpy() > 0
            value = scores[f"sig_{key}"].to_numpy(dtype=float)
            out[f"status_{key}"] = np.where(
                ~available,
                STATUS_UNAVAILABLE,
                np.where(value >= self.active_threshold, STATUS_ACTIVE, STATUS_CLEAR),
            )
        return out

    # ------------------------------------------------------------------ io --

    def to_dict(self) -> Dict:
        return {
            "method": "train_window_percentile_rank",
            "grid_points": GRID_POINTS,
            "low_percentile": self.low_pct,
            "high_percentile": self.high_pct,
            "active_threshold": self.active_threshold,
            "neutral_floor": (
                "raw <= 0 => score 0 (beyan beklentinin ustunde)"
            ),
            "fitted_on": self.fitted_on,
            "stale_matrix_multiplier": STALE_MATRIX_MULTIPLIER,
            "signals": {
                spec["code"]: {
                    "key": spec["key"],
                    "name": spec["ad"],
                    "question": spec["soru"],
                    "source": spec["kaynak"],
                    "availability_feature": spec["avail"],
                    "unavailable_reason": spec["avail_reason"],
                    **self.anchors.get(spec["code"], {}),
                    "breaks": self.breaks.get(spec["code"], []),
                }
                for spec in SIGNAL_SPECS
            },
        }

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, payload: Dict) -> "SignalScaler":
        scaler = cls(
            active_threshold=float(payload.get("active_threshold", SIGNAL_ACTIVE_THRESHOLD)),
            low_pct=float(payload.get("low_percentile", SIGNAL_RAMP_LOW_PCT)),
            high_pct=float(payload.get("high_percentile", SIGNAL_RAMP_HIGH_PCT)),
            fitted_on=str(payload.get("fitted_on", "")),
        )
        scaler.anchors = {
            code: {"low": float(item["low"]), "high": float(item["high"])}
            for code, item in payload.get("signals", {}).items()
            if "low" in item and "high" in item
        }
        scaler.breaks = {
            code: [float(v) for v in item.get("breaks", [])]
            for code, item in payload.get("signals", {}).items()
            if item.get("breaks")
        }
        return scaler

    @classmethod
    def load(cls, path: Path) -> "SignalScaler":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# --------------------------------------------------------------------------
# Aralik konumu - Katman 3'u Katman 4'e baglayan koprü
# --------------------------------------------------------------------------
def interval_features(frame: pd.DataFrame, calibrated: pd.DataFrame) -> pd.DataFrame:
    declared = _col(frame, "declared_packaging_tonnage")
    declared_log = np.log1p(np.clip(declared, 0.0, None))

    lo_log = calibrated["q05_cal_log"].to_numpy(dtype=float)
    mid_log = calibrated["q50_cal_log"].to_numpy(dtype=float)
    lo = calibrated["q05_cal"].to_numpy(dtype=float)
    mid = calibrated["q50_cal"].to_numpy(dtype=float)
    hi = calibrated["q95_cal"].to_numpy(dtype=float)

    half = np.maximum(mid_log - lo_log, 1e-3)

    out = pd.DataFrame(index=frame.index)
    # Pozitif deger: beyan kalibre alt sinirin ALTINDA, kac yarim aralik kadar.
    out["interval_position_z"] = (lo_log - declared_log) / half
    out["interval_rel_gap"] = 1.0 - _safe_ratio(declared, mid)
    out["interval_width_rel"] = _safe_ratio(hi - lo, mid)
    out["interval_below_lower"] = (declared < lo).astype(int)
    return out


# --------------------------------------------------------------------------
# Seffaf (politika agirlikli) birlestirme - ogrenilmis fusion'in yedegi
# --------------------------------------------------------------------------
def policy_fusion(
    scores: pd.DataFrame,
    weights: Dict[str, float],
    strongest_share: float,
) -> pd.DataFrame:
    """Agirlikli ortalama + en guclu bulgunun payi.

    Kullanilamayan sinyal agirlik TASIMAZ; kalan agirliklar yeniden
    olceklenir. Hicbir sinyal yoksa puan uretilmez (NaN) - kayit veri
    incelemesi kuyruguna gider.
    """
    codes = list(SIGNAL_CODES)
    value = np.vstack([scores[f"sig_{c.lower()}"].to_numpy(dtype=float) for c in codes])
    avail = np.vstack([scores[f"avail_{c.lower()}"].to_numpy(dtype=float) for c in codes])
    weight = np.array([weights.get(c, 0.0) for c in codes], dtype=float)[:, None]

    filled = np.nan_to_num(value, nan=0.0)
    effective = weight * avail
    total = effective.sum(axis=0)
    weighted = np.divide(
        (filled * effective).sum(axis=0),
        total,
        out=np.full(total.shape, np.nan),
        where=total > _EPS,
    )
    strongest = np.where(avail > 0, filled, -np.inf).max(axis=0)
    strongest = np.where(np.isfinite(strongest), strongest, np.nan)

    combined = (1.0 - strongest_share) * weighted + strongest_share * strongest
    coverage = total / max(sum(weights.values()), _EPS)

    return pd.DataFrame({
        "policy_score": np.round(np.clip(combined, 0.0, 100.0), 2),
        "signal_coverage": np.round(coverage, 4),
    }, index=scores.index)


def contribution_shares(
    scores: pd.DataFrame,
    weights: Dict[str, float],
) -> pd.DataFrame:
    """Politika birlestirmesinde her sinyalin payi (0-1, toplami 1)."""
    codes = list(SIGNAL_CODES)
    value = np.vstack([scores[f"sig_{c.lower()}"].to_numpy(dtype=float) for c in codes])
    avail = np.vstack([scores[f"avail_{c.lower()}"].to_numpy(dtype=float) for c in codes])
    weight = np.array([weights.get(c, 0.0) for c in codes], dtype=float)[:, None]

    mass = np.nan_to_num(value, nan=0.0) * weight * avail
    total = mass.sum(axis=0)
    shares = np.divide(mass, total, out=np.zeros_like(mass), where=total > _EPS)
    return pd.DataFrame(
        {f"share_{c.lower()}": shares[i] for i, c in enumerate(codes)},
        index=scores.index,
    )


def unavailable_reasons(row: pd.Series) -> List[Dict[str, str]]:
    reasons: List[Dict[str, str]] = []
    for code in SIGNAL_CODES:
        if row.get(f"avail_{code.lower()}", 0) > 0:
            continue
        spec = signal_by_code(code)
        reasons.append({"signal": code, "reason": spec["avail_reason"]})
    return reasons


__all__ = [
    "SignalScaler",
    "raw_statistics",
    "interval_features",
    "policy_fusion",
    "contribution_shares",
    "unavailable_reasons",
    "STATUS_ACTIVE",
    "STATUS_CLEAR",
    "STATUS_UNAVAILABLE",
]
