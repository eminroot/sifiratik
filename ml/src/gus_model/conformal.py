"""Konformal kalibrasyon - Mondrian CQR.

Yontem: Conformalized Quantile Regression (Romano, Patterson, Candes 2019).
Kalibrasyon kumesindeki her kayit icin uygunsuzluk skoru

    E_i = max( qlo(x_i) - y_i ,  y_i - qhi(x_i) )

hesaplanir; aralik iki ucundan da Q_{1-alpha}(E) kadar genisletilir. Sonuc,
degisim-degismezlik (exchangeability) varsayimi altinda dagilimdan bagimsiz
kapsama garantisidir. Sonlu ornek duzeltmesi ceil((n+1)(1-alpha))/n ile
yapilir; kalibrasyon kumesi kucukse duzeltme aralig genisletir - dogru olan da
budur.

MONDRIAN: kapsama TUM populasyonda degil, HER ALT GRUPTA tutmalidir. Aksi
halde iyi verili buyuk firmalarda fazla dar, ince verili mikro firmalarda
fazla genis bir aralik ortalamada dogru gorunur ve denetciyi yanlis kapiya
gonderir. Gruplar sirasiyla denenir:

    (sektor, olcek, veri guveni) -> (olcek, veri guveni) -> (sektor, olcek)
    -> veri guveni -> sektor -> olcek -> global

VERI GUVENI neden gruplama boyutu: model, veri kalitesi dustukce araligi zaten
bir miktar genisletmeyi ogreniyor (test bolumunde ortanca bagil genislik
yuksek guvende 0,85 iken dusuk guvende 0,95). Fakat bu kendiliginden yeterli
degil - dusuk guvenli kayitlarda gozlenen kapsama yine de daha dusuk kaliyordu.
Veri guvenini gruplama boyutu yapmak, kapsama garantisini bu kayitlar icin de
ayri ayri kurar. Kotu verili bir firmaya dar aralik vermek, denetciyi yanlis
kapiya gonderen hatadir.

Bir grup `conformal_min_group` esigini tutmuyorsa bir ust gruba dusulur ve
aralik `conformal_thin_widen` carpaniyla ayrica genisletilir; ince kalibrasyon
dar aralik uretmemelidir.

Hesap LOG uzayinda yapilir; geri cevrildiginde genisletme carpansal olur.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import ModelConfig
from .featureset import TARGET_COLUMN, log_target, unlog

GROUP_LEVELS: Tuple[Tuple[str, ...], ...] = (
    ("sector", "size_band", "f_data_confidence_level"),
    ("size_band", "f_data_confidence_level"),
    ("sector", "size_band"),
    ("f_data_confidence_level",),
    ("sector",),
    ("size_band",),
    (),
)

GLOBAL_KEY = "*"


def group_keys(frame: pd.DataFrame, level: Tuple[str, ...]) -> pd.Series:
    if not level:
        return pd.Series(GLOBAL_KEY, index=frame.index)
    parts = [frame[c].astype(str) for c in level]
    joined = parts[0]
    for extra in parts[1:]:
        joined = joined + "|" + extra
    return joined


def _finite_sample_quantile(scores: np.ndarray, coverage: float) -> float:
    """CQR'nin sonlu ornek duzeltmeli quantile'i."""
    scores = np.asarray(scores, dtype=float)
    scores = scores[np.isfinite(scores)]
    n = len(scores)
    if n == 0:
        return float("nan")
    rank = int(np.ceil((n + 1) * coverage))
    if rank > n:
        # Kalibrasyon kumesi bu kapsama icin fazla kucuk. Sonsuz aralik yerine
        # en buyuk artigi kullanir ve `thin` bayragiyla ayrica genisletiriz.
        return float(np.max(scores))
    return float(np.sort(scores)[rank - 1])


@dataclass
class ConformalCalibrator:
    """Grup bazli CQR genisletme paylari."""

    target_coverage: float = 0.90
    min_group: int = 60
    thin_widen: float = 1.15
    # Ikinci asama duzeltme carpani. Kalibrasyon havuzu capraz uydurulmus
    # modellerin artiklarini icerdigi icin - bunlar tam modelden bir tik
    # zayiftir - genisletme payi sistematik olarak BUYUK cikar ve aralik
    # hedefin uzerinde kapsar. Bu skaler, AYRI TUTULAN bir bolumde gozlenen
    # kapsamayi hedefe oturtur. Grup yapisini bozmaz, yalnizca olcekler.
    delta_scale: float = 1.0
    scale_fitted_on: str = ""
    required_coverage: float = 0.0
    # level_index -> {group_key: {"delta": float, "n": int, "thin": bool}}
    tables: List[Dict[str, Dict[str, float]]] = field(default_factory=list)
    fitted_on: str = ""

    # ------------------------------------------------------------------ fit --

    def fit(
        self,
        frame: pd.DataFrame,
        pred_log: pd.DataFrame,
        fitted_on: str = "",
    ) -> "ConformalCalibrator":
        y_log = log_target(frame[TARGET_COLUMN])
        lo = pred_log["q05"].to_numpy(dtype=float)
        hi = pred_log["q95"].to_numpy(dtype=float)
        scores = np.maximum(lo - y_log, y_log - hi)

        self.tables = []
        for level in GROUP_LEVELS:
            keys = group_keys(frame, level)
            table: Dict[str, Dict[str, float]] = {}
            for key, idx in keys.groupby(keys).groups.items():
                sub = scores[keys.index.get_indexer(idx)]
                sub = sub[np.isfinite(sub)]
                if len(sub) == 0:
                    continue
                delta = _finite_sample_quantile(sub, self.target_coverage)
                thin = len(sub) < self.min_group
                table[str(key)] = {
                    "delta": float(delta),
                    "n": int(len(sub)),
                    "thin": bool(thin),
                }
            self.tables.append(table)

        self.fitted_on = fitted_on
        return self

    # -------------------------------------------------------------- resolve --

    def resolve(self, frame: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Her satir icin genisletme payi, kaynak grup ve incelik bayragi.

        Seviye seviye vektorel olarak cozulur: once en ozel grup, esigi
        tutmayan satirlar bir ust seviyeye dusurulur. `delta_scale` burada
        UYGULANMAZ; olcek arama sirasinda ayni cozumun tekrar tekrar
        hesaplanmasi gerekmesin diye ayri tutulur.
        """
        n_rows = len(frame)
        deltas = np.full(n_rows, np.nan)
        counts = np.zeros(n_rows, dtype=int)
        levels = np.array([GLOBAL_KEY] * n_rows, dtype=object)
        thin = np.ones(n_rows, dtype=bool)

        for enough in (True, False):
            for table, level in zip(self.tables, GROUP_LEVELS):
                if not table:
                    continue
                pending = np.isnan(deltas)
                if not pending.any():
                    break
                keys = group_keys(frame, level)
                delta_map = {
                    k: v["delta"] for k, v in table.items()
                    if not enough or v["n"] >= self.min_group
                }
                count_map = {
                    k: v["n"] for k, v in table.items()
                    if not enough or v["n"] >= self.min_group
                }
                candidate = keys.map(delta_map).to_numpy(dtype=float)
                hit = pending & np.isfinite(candidate)
                deltas[hit] = candidate[hit]
                counts[hit] = keys.map(count_map).to_numpy(dtype=float)[hit].astype(int)
                levels[hit] = "|".join(level) or GLOBAL_KEY
                thin[hit] = not enough
            if not np.isnan(deltas).any():
                break

        # Esigi hicbir seviyede tutmayan gruplar: dar aralik uretmemek icin
        # ayrica genisletilir.
        deltas = np.where(thin & np.isfinite(deltas), deltas * self.thin_widen, deltas)
        return {"delta": deltas, "n": counts, "level": levels, "thin": thin}

    def apply(
        self,
        frame: pd.DataFrame,
        pred_log: pd.DataFrame,
        resolved: Optional[Dict[str, np.ndarray]] = None,
    ) -> pd.DataFrame:
        """Kalibre edilmis aralik + hangi gruptan kalibre edildigi."""
        resolved = resolved or self.resolve(frame)
        deltas = resolved["delta"] * self.delta_scale
        ns = resolved["n"]
        levels = list(resolved["level"])
        thins = resolved["thin"]

        lo_log = pred_log["q05"].to_numpy(dtype=float) - deltas
        hi_log = pred_log["q95"].to_numpy(dtype=float) + deltas
        mid_log = pred_log["q50"].to_numpy(dtype=float)
        lo_log = np.minimum(lo_log, mid_log)
        hi_log = np.maximum(hi_log, mid_log)

        return pd.DataFrame({
            "q05_cal": unlog(lo_log),
            "q50_cal": unlog(mid_log),
            "q95_cal": unlog(hi_log),
            "q05_cal_log": lo_log,
            "q50_cal_log": mid_log,
            "q95_cal_log": hi_log,
            "conformal_delta_log": deltas,
            "conformal_group": levels,
            "conformal_n": ns,
            "conformal_thin": thins,
        }, index=frame.index)

    def tune_scale(
        self,
        frame: pd.DataFrame,
        pred_log: pd.DataFrame,
        fitted_on: str = "",
        grid: Optional[np.ndarray] = None,
        extra_margin: float = 0.0,
    ) -> "ConformalCalibrator":
        """Duzeltme carpanini AYRI TUTULAN bir bolumde ayarlar.

        Kural: gozlenen kapsamayi hedefe EN YAKIN yapan carpan degil, hedefi
        BIR STANDART HATA payiyla TUTAN en kucuk carpan secilir.

        Iki gerekcesi var. Birincisi, ayar bolumu de sonlu bir orneklemdir;
        hedefe tam oturtmak, gercek kapsamanin yarisi ihtimalle hedefin altina
        dusmesi demektir. Ikincisi ve daha onemlisi, iki hata yonu esit degildir:
        gereginden GENIS aralik beyan acigini kucuk gosterir (denetci gitmez),
        gereginden DAR aralik ise normal bir firmanin beyanini acikli gosterir
        ve denetciyi yanlis kapiya gonderir. Ikincisi daha pahalidir.

        `extra_margin`, aralik kalibre edildigi donemde DEGIL bir sonraki
        donemde kullanildigi icin olusan kapsama kaybinin tahminidir; nasil
        olculdugu `pipeline.estimate_coverage_drift` icindedir.
        """
        y_log = log_target(frame[TARGET_COLUMN])
        candidates = np.arange(0.50, 2.001, 0.01) if grid is None else np.asarray(grid)

        resolved = self.resolve(frame)
        base = np.nan_to_num(resolved["delta"], nan=0.0)
        lo = pred_log["q05"].to_numpy(dtype=float)
        hi = pred_log["q95"].to_numpy(dtype=float)

        n = max(len(frame), 1)
        target = self.target_coverage
        margin = float(np.sqrt(target * (1.0 - target) / n))
        required = min(target + margin + max(0.0, float(extra_margin)), 0.999)

        chosen: Optional[float] = None
        best_scale, best_coverage = float(candidates[-1]), -1.0
        for scale in np.sort(candidates):
            delta = base * float(scale)
            coverage = float(((y_log >= lo - delta) & (y_log <= hi + delta)).mean())
            if coverage > best_coverage:
                best_scale, best_coverage = float(scale), coverage
            if chosen is None and coverage >= required:
                chosen = float(scale)
        # Hicbir carpan esigi tutmuyorsa en yuksek kapsamayi veren secilir.
        self.delta_scale = chosen if chosen is not None else best_scale
        self.required_coverage = required
        self.scale_fitted_on = (
            f"{fitted_on} (hedef {target} + 1 standart hata {margin:.4f}"
            f" + kayma payi {max(0.0, float(extra_margin)):.4f} = {required:.4f})"
        )
        return self

    # ------------------------------------------------------------ coverage --

    def coverage_report(
        self,
        frame: pd.DataFrame,
        calibrated: pd.DataFrame,
        label: str,
        by: Optional[str] = None,
    ) -> pd.DataFrame:
        y = frame[TARGET_COLUMN].astype(float).to_numpy()
        inside = (y >= calibrated["q05_cal"].to_numpy()) & (y <= calibrated["q95_cal"].to_numpy())
        width = calibrated["q95_cal"].to_numpy() - calibrated["q05_cal"].to_numpy()
        rel_width = np.divide(
            width,
            np.maximum(calibrated["q50_cal"].to_numpy(), 1e-6),
            out=np.full(len(width), np.nan),
            where=calibrated["q50_cal"].to_numpy() > 1e-6,
        )

        def _row(name: str, mask: np.ndarray) -> Dict:
            n = int(mask.sum())
            return {
                "bolum": label,
                "grup": name,
                "n": n,
                "hedef_kapsama": self.target_coverage,
                "gozlenen_kapsama": round(float(inside[mask].mean()), 4) if n else float("nan"),
                "ortanca_genislik_ton": round(float(np.nanmedian(width[mask])), 3) if n else float("nan"),
                "ortanca_bagil_genislik": round(float(np.nanmedian(rel_width[mask])), 3) if n else float("nan"),
            }

        if not by:
            return pd.DataFrame([_row("tumu", np.ones(len(frame), dtype=bool))])
        values = frame[by].astype(str)
        rows = [
            _row(f"{by}={value}", (values == value).to_numpy())
            for value in sorted(values.unique())
        ]
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------ io --

    def to_dict(self) -> Dict:
        return {
            "method": "mondrian_cqr",
            "target_coverage": self.target_coverage,
            "min_group": self.min_group,
            "thin_widen": self.thin_widen,
            "delta_scale": self.delta_scale,
            "required_coverage": self.required_coverage,
            "fitted_on": self.fitted_on,
            "scale_fitted_on": self.scale_fitted_on,
            "space": "log1p",
            "levels": [list(level) for level in GROUP_LEVELS],
            "tables": self.tables,
        }

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, payload: Dict) -> "ConformalCalibrator":
        calibrator = cls(
            target_coverage=float(payload.get("target_coverage", 0.90)),
            min_group=int(payload.get("min_group", 60)),
            thin_widen=float(payload.get("thin_widen", 1.15)),
            fitted_on=str(payload.get("fitted_on", "")),
        )
        calibrator.delta_scale = float(payload.get("delta_scale", 1.0))
        calibrator.required_coverage = float(payload.get("required_coverage", 0.0))
        calibrator.scale_fitted_on = str(payload.get("scale_fitted_on", ""))
        calibrator.tables = payload.get("tables", [])
        return calibrator

    @classmethod
    def load(cls, path: Path) -> "ConformalCalibrator":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def build_calibrator(cfg: ModelConfig) -> ConformalCalibrator:
    return ConformalCalibrator(
        target_coverage=cfg.target_coverage,
        min_group=cfg.conformal_min_group,
        thin_widen=cfg.conformal_thin_widen,
    )


__all__ = [
    "ConformalCalibrator",
    "GROUP_LEVELS",
    "build_calibrator",
    "group_keys",
]
