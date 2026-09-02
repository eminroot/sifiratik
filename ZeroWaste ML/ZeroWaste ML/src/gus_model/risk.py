"""Katman 4 - sinyal birlestirme (fusion) ve oncelik puani.

Girdisi HAM ozellik degil, sekiz sinyalin 0-100 kaniti, kullanilabilirlikleri,
kalibre edilmis araliga gore konum ve veri guveni baglamidir. Bunun uc nedeni
var:

1. Aciklama sinyal dilinde kalir. SHAP katkisi dogrudan "S1 ne kadar katti"
   sorusunun cevabidir; ham ozellikten sinyale geri cevirmek gerekmez.
2. Az sayida pozitif ornekle (egitimde ~250) doksan ozellikli bir model
   sahte oruntu bulur. Otuz civari, anlami onceden tanimli girdi daha
   dayanikli ogrenir.
3. Kullanilabilirlik acikca modele girer; "veri yok"u "sorun yok"a cevirmez.

Karsilastirma icin `fit_direct_reference` tum Model_Ready ozellikleri uzerinde
dogrudan bir model uydurur. Bu, fusion'in ne kaybettigini durustce olcmek
icindir; teslim edilen model degildir.

OLASILIKTAN PUANA
-----------------
Ham olasilik izotonik regresyonla kalibre edilir, sonra REFERANS POPULASYONDAKI
yuzdeligi uzerinden 0-100 puana cevrilir. Capalar `config.SCORE_ANCHORS`
icindedir ve CRITICAL bandinin genisligi populasyon prevalansi kadardir:
kuyrugun tepesi sorunun boyu kadar olur. Puan, ihlal olasiligi DEGILDIR.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd

from .config import SCORE_ANCHORS, ModelConfig, band_for
from .featureset import RISK_FEATURES, categorical_names, prepare_matrix

_EPS = 1e-12


def _fold_of(firm_id: str, seed: int, folds: int) -> int:
    digest = hashlib.sha256(f"{seed}:risk:{firm_id}".encode()).hexdigest()
    return int(digest[:8], 16) % folds


def average_precision(y: np.ndarray, score: np.ndarray) -> float:
    order = np.argsort(-np.asarray(score, dtype=float), kind="stable")
    labels = np.asarray(y, dtype=float)[order]
    tp = np.cumsum(labels)
    precision = tp / np.arange(1, len(labels) + 1)
    positives = labels.sum()
    return float((precision * labels).sum() / positives) if positives else float("nan")


# --------------------------------------------------------------------------
# Fusion modeli
# --------------------------------------------------------------------------
def _sigmoid(margin: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(margin, dtype=float)))


@dataclass
class RiskModel:
    """Tohum toplulugu (seed ensemble).

    Egitimde ~250 pozitif ornek var; tek bir booster'in siralamasi tohum
    secimine gorunur bicimde duyarli. Farkli tohumlarla egitilmis birkac
    booster'in LOG-ODDS ortalamasi bu varyansi dusurur - egitim penceresinde
    capraz dogrulamayla olculdu, Precision@100 tutarli sekilde iyilesiyor.

    Ortalama OLASILIK degil MARJIN uzerinden alinir. Boylece SHAP katkilari
    (bunlar da marjin uzayindadir) toplandiginda tam olarak modelin ciktisini
    verir; aciklama ile puan arasinda kapanmayan bir fark kalmaz.
    """

    features: Tuple[str, ...] = RISK_FEATURES
    boosters: List[lgb.Booster] = field(default_factory=list)
    categories: Dict[str, List[str]] = field(default_factory=dict)
    best_iteration: int = 0
    n_seeds: int = 5

    @property
    def booster(self) -> Optional[lgb.Booster]:
        return self.boosters[0] if self.boosters else None

    def fit(
        self,
        cfg: ModelConfig,
        train: pd.DataFrame,
        y_train: np.ndarray,
        valid: Optional[pd.DataFrame] = None,
        y_valid: Optional[np.ndarray] = None,
    ) -> "RiskModel":
        x_train, categories = prepare_matrix(train, self.features)
        self.categories = categories
        cats = categorical_names(self.features)
        self.n_seeds = max(1, int(cfg.risk_seeds))

        x_valid = None
        if valid is not None and y_valid is not None and len(valid):
            x_valid, _ = prepare_matrix(valid, self.features, categories)

        self.boosters = []
        iterations: List[int] = []
        for member in range(self.n_seeds):
            params = dict(cfg.risk_params)
            params["seed"] = cfg.seed + 101 * member
            params["bagging_seed"] = cfg.seed + 211 * member
            params["feature_fraction_seed"] = cfg.seed + 307 * member
            params["metric"] = "average_precision"
            # Pozitif sinif seyrek. Sinif agirligi vermek yerine metrigi
            # siralamaya bagliyoruz; agirlik olasilik kalibrasyonunu bozar.

            dtrain = lgb.Dataset(
                x_train, label=y_train, categorical_feature=cats, free_raw_data=False
            )
            valid_sets = None
            callbacks = [lgb.log_evaluation(period=0)]
            if x_valid is not None:
                valid_sets = [
                    lgb.Dataset(
                        x_valid, label=y_valid, categorical_feature=cats,
                        reference=dtrain, free_raw_data=False,
                    )
                ]
                callbacks.append(lgb.early_stopping(cfg.risk_early_stopping, verbose=False))

            booster = lgb.train(
                params,
                dtrain,
                num_boost_round=cfg.risk_rounds,
                valid_sets=valid_sets,
                callbacks=callbacks,
            )
            self.boosters.append(booster)
            iterations.append(int(booster.best_iteration or cfg.risk_rounds))

        self.best_iteration = int(np.median(iterations))
        return self

    def _matrix(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not self.boosters:
            raise RuntimeError("RiskModel egitilmedi.")
        x, _ = prepare_matrix(frame, self.features, self.categories)
        return x

    def predict_margin(self, frame: pd.DataFrame) -> np.ndarray:
        x = self._matrix(frame)
        margins = [
            np.asarray(
                booster.predict(x, num_iteration=booster.best_iteration or None, raw_score=True),
                dtype=float,
            )
            for booster in self.boosters
        ]
        return np.mean(margins, axis=0)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        return _sigmoid(self.predict_margin(frame))

    def shap_values(self, frame: pd.DataFrame) -> pd.DataFrame:
        """TreeSHAP katkilari (marjin uzayi). Son sutun beklenen deger."""
        x = self._matrix(frame)
        stacked = [
            np.asarray(
                booster.predict(
                    x, num_iteration=booster.best_iteration or None, pred_contrib=True
                ),
                dtype=float,
            )
            for booster in self.boosters
        ]
        values = np.mean(stacked, axis=0)
        columns = list(self.features) + ["base_value"]
        return pd.DataFrame(values, index=frame.index, columns=columns)

    def importance(self) -> pd.DataFrame:
        if not self.boosters:
            raise RuntimeError("RiskModel egitilmedi.")
        frame = pd.DataFrame({"ozellik": self.boosters[0].feature_name()})
        frame["kazanc"] = np.mean(
            [b.feature_importance("gain") for b in self.boosters], axis=0
        )
        frame["bolme"] = np.mean(
            [b.feature_importance("split") for b in self.boosters], axis=0
        )
        return frame.sort_values("kazanc", ascending=False).reset_index(drop=True)

    def save(self, path: Path) -> List[Path]:
        """Topluluk uyeleri `risk_model.txt`, `risk_model_2.txt` ... olarak yazilir."""
        if not self.boosters:
            raise RuntimeError("RiskModel egitilmedi.")
        path.parent.mkdir(parents=True, exist_ok=True)
        written: List[Path] = []
        for i, booster in enumerate(self.boosters):
            target = path if i == 0 else path.with_name(f"{path.stem}_{i + 1}{path.suffix}")
            booster.save_model(str(target), num_iteration=booster.best_iteration or None)
            written.append(target)
        return written

    @classmethod
    def load(
        cls,
        path: Path,
        features: Sequence[str],
        categories: Dict[str, List[str]],
        members: int = 1,
    ) -> "RiskModel":
        model = cls(features=tuple(features), categories=categories, n_seeds=members)
        for i in range(max(members, 1)):
            target = path if i == 0 else path.with_name(f"{path.stem}_{i + 1}{path.suffix}")
            model.boosters.append(lgb.Booster(model_file=str(target)))
        model.best_iteration = int(model.boosters[0].current_iteration())
        return model


def fit_out_of_fold(
    cfg: ModelConfig,
    train: pd.DataFrame,
    y_train: np.ndarray,
    firm_ids: pd.Series,
    rounds: int,
) -> np.ndarray:
    """Egitim bolumu icin ORNEKLEM DISI olasiliklar.

    Kalibrasyon ve puan haritasi bu olasiliklardan kurulur. Modelin kendi
    egitim tahminleri asiri keskin oldugu icin dogrudan kullanilamaz.
    """
    folds = np.array([_fold_of(str(f), cfg.seed, cfg.cv_folds) for f in firm_ids])
    out = np.full(len(train), np.nan)
    # Katlarda dogrulama kumesi yok; tur sayisi nihai modelin sectigi sayiya
    # sabitlenir. Aksi halde her kat kendi erken durdurmasini yapar ve
    # kalibrasyon havuzu farkli karmasiklikta modellerin karisimi olur.
    inner = ModelConfig(**{**cfg.to_dict(), "risk_rounds": max(rounds, 1)})

    for k in range(cfg.cv_folds):
        in_fold = folds == k
        if not in_fold.any() or in_fold.all():
            continue
        model = RiskModel().fit(inner, train.loc[~in_fold], y_train[~in_fold])
        out[in_fold] = model.predict_proba(train.loc[in_fold])
    return out


# --------------------------------------------------------------------------
# Olasilik kalibrasyonu
# --------------------------------------------------------------------------
@dataclass
class ProbabilityCalibrator:
    """Izotonik regresyon; dugum noktalari olarak saklanir.

    Saklama bicimi kasitli olarak sadece iki dizidir: backend'de yeniden
    uretmek icin `numpy.interp` yeter, scikit-learn bagimliligi gerekmez.
    """

    x: List[float] = field(default_factory=list)
    y: List[float] = field(default_factory=list)
    fitted_on: str = ""

    def fit(self, prob: np.ndarray, target: np.ndarray, fitted_on: str = "") -> "ProbabilityCalibrator":
        from sklearn.isotonic import IsotonicRegression

        mask = np.isfinite(prob)
        model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        model.fit(prob[mask], np.asarray(target, dtype=float)[mask])

        grid = np.unique(np.quantile(prob[mask], np.linspace(0.0, 1.0, 512)))
        self.x = [float(v) for v in grid]
        self.y = [float(v) for v in model.predict(grid)]
        self.fitted_on = fitted_on
        return self

    def transform(self, prob: np.ndarray) -> np.ndarray:
        if not self.x:
            return np.asarray(prob, dtype=float)
        return np.interp(np.asarray(prob, dtype=float), self.x, self.y)

    def to_dict(self) -> Dict:
        return {"method": "isotonic", "x": self.x, "y": self.y, "fitted_on": self.fitted_on}

    @classmethod
    def from_dict(cls, payload: Dict) -> "ProbabilityCalibrator":
        return cls(
            x=[float(v) for v in payload.get("x", [])],
            y=[float(v) for v in payload.get("y", [])],
            fitted_on=str(payload.get("fitted_on", "")),
        )


# --------------------------------------------------------------------------
# Puan haritasi
# --------------------------------------------------------------------------
@dataclass
class ScoreMap:
    """Kalibre olasilik -> referans populasyondaki yuzdelik -> 0-100 puan."""

    reference: List[float] = field(default_factory=list)   # 0-1 arasi 1001 quantile
    anchors: Tuple[Tuple[float, float], ...] = SCORE_ANCHORS
    fitted_on: str = ""
    prevalence: float = 0.0

    def fit(self, prob: np.ndarray, prevalence: float, fitted_on: str = "") -> "ScoreMap":
        values = np.asarray(prob, dtype=float)
        values = values[np.isfinite(values)]
        grid = np.linspace(0.0, 1.0, 1001)
        self.reference = [float(v) for v in np.quantile(values, grid)]
        self.prevalence = float(prevalence)
        self.fitted_on = fitted_on
        return self

    def percentile(self, prob: np.ndarray) -> np.ndarray:
        if not self.reference:
            return np.clip(np.asarray(prob, dtype=float), 0.0, 1.0)
        grid = np.linspace(0.0, 1.0, len(self.reference))
        return np.interp(np.asarray(prob, dtype=float), self.reference, grid)

    def transform(self, prob: np.ndarray) -> np.ndarray:
        percentile = self.percentile(prob)
        xs = [a[0] for a in self.anchors]
        ys = [a[1] for a in self.anchors]
        # Dort ondalik: gosterimde yuvarlanir, fakat kuyruk siralamasi
        # modelin siralamasindan yuvarlama beraberlikleriyle ayrilmaz.
        return np.round(np.clip(np.interp(percentile, xs, ys), 0.0, 100.0), 4)

    def levels(self, score: np.ndarray) -> np.ndarray:
        return np.array([band_for(float(s)) for s in np.asarray(score, dtype=float)])

    def to_dict(self) -> Dict:
        return {
            "method": "reference_percentile_anchors",
            "anchors": [list(a) for a in self.anchors],
            "reference_quantiles": self.reference,
            "prevalence": self.prevalence,
            "fitted_on": self.fitted_on,
        }

    @classmethod
    def from_dict(cls, payload: Dict) -> "ScoreMap":
        anchors = tuple(tuple(a) for a in payload.get("anchors", SCORE_ANCHORS))
        return cls(
            reference=[float(v) for v in payload.get("reference_quantiles", [])],
            anchors=anchors,  # type: ignore[arg-type]
            fitted_on=str(payload.get("fitted_on", "")),
            prevalence=float(payload.get("prevalence", 0.0)),
        )


# --------------------------------------------------------------------------
# Karsilastirma modeli - teslim edilmez, yalnizca olcum icin
# --------------------------------------------------------------------------
def fit_direct_reference(
    cfg: ModelConfig,
    train: pd.DataFrame,
    y_train: np.ndarray,
    valid: pd.DataFrame,
    y_valid: np.ndarray,
    exclude: Sequence[str] = (),
) -> Tuple[lgb.Booster, List[str]]:
    """Tum Model_Ready ozellikleri uzerinde dogrudan siniflandirici.

    Fusion'in seffaflik icin ne kadar performans verdigi bu modelle olculur.
    """
    drop = set(exclude) | {
        "observation_id", "firm_id", "period", "split", "province", "year",
        "f_s2_peer_group", "f_data_confidence_level",
    }
    numeric = [
        c for c in train.columns
        if c not in drop and pd.api.types.is_numeric_dtype(train[c])
    ]
    params = dict(cfg.risk_params)
    params.update({"seed": cfg.seed, "metric": "average_precision", "num_leaves": 16,
                   "min_data_in_leaf": 40})

    dtrain = lgb.Dataset(train[numeric], label=y_train, free_raw_data=False)
    dvalid = lgb.Dataset(valid[numeric], label=y_valid, reference=dtrain, free_raw_data=False)
    booster = lgb.train(
        params,
        dtrain,
        num_boost_round=cfg.risk_rounds,
        valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(cfg.risk_early_stopping, verbose=False),
                   lgb.log_evaluation(period=0)],
    )
    return booster, numeric


__all__ = [
    "RiskModel",
    "ProbabilityCalibrator",
    "ScoreMap",
    "fit_out_of_fold",
    "fit_direct_reference",
    "average_precision",
]
