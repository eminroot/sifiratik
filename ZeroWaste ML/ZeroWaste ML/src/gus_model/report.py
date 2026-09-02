"""Degerlendirme raporlari ve model karti.

Uretilenler (`reports/` altinda):

    01_bolumler.csv             bolum buyuklukleri ve prevalans
    02_quantile_tani.csv        pinball kaybi, ham kapsama
    03_konformal_kapsama.csv    hedef vs gozlenen kapsama, alt gruplarla
    04_siralama.csv             model + referans baseline'lar ayni tabloda
    05_sinyal_ayirt.csv         sinyal basina kullanilabilirlik ve ayirt gucu
    06_sinyal_korelasyon.csv    sinyaller arasi Spearman korelasyonu
    07_ablation.csv             her sinyal cikarilarak yeniden egitim
    08_alt_grup.csv             sektor / olcek / veri guveni / il
    09_mekanizma.csv            anomali mekanizmasi bazli Top-K yakalama
    10_kalibrasyon.csv          olasilik guvenilirlik tablosu
    11_fayda.csv                Top-K karsiliginda tonaj ve denetim maliyeti
    12_yanlis_pozitif.csv       Top-100 icindeki negatiflerin profili
    MODEL_KARTI.md              model karti

Model karti bilincli olarak SINIRLILIKLARLA baslar; performans tablolari
ondan sonra gelir.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import evaluate as ev
from .config import SIGNAL_CODES, ModelConfig, signal_by_code
from .dataset import Bundle, split_report
from .featureset import RISK_FEATURES
from .pipeline import GusModel

TOP_K = 100


def _write(frame: pd.DataFrame, directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    frame.to_csv(directory / name, sep=";", index=False, encoding="utf-8-sig")


def write_reports(
    model: GusModel,
    bundle: Bundle,
    scored: Dict[str, pd.DataFrame],
    cfg: ModelConfig,
    root: Path,
    run_ablation: bool = True,
) -> Dict:
    directory = root / cfg.report_dir
    directory.mkdir(parents=True, exist_ok=True)

    splits = bundle.splits
    test_index = splits.test
    valid_index = splits.valid
    test_frame = bundle.rows(test_index)
    y_test = bundle.target(test_index)
    y_valid = bundle.target(valid_index)

    test_scored = scored["test"]
    valid_scored = scored["valid"]
    test_score = test_scored["priority_score"]
    valid_score = valid_scored["priority_score"]

    # -- 01/02/03 -----------------------------------------------------------
    _write(split_report(bundle), directory, "01_bolumler.csv")
    _write(model.diagnostics.quantile, directory, "02_quantile_tani.csv")

    coverage_rows = [model.diagnostics.coverage]
    for label, index in (("valid", valid_index), ("test", test_index)):
        frame = bundle.rows(index)
        calibrated = scored[label if label in scored else "test"]
        calibrated = scored["valid"] if label == "valid" else scored["test"]
        coverage_rows.append(
            model.conformal.coverage_report(frame, calibrated, label)
        )
        coverage_rows.append(
            model.conformal.coverage_report(frame, calibrated, label, by="size_band")
        )
        coverage_rows.append(
            model.conformal.coverage_report(frame, calibrated, label, by="sector")
        )
    coverage = pd.concat(coverage_rows, ignore_index=True)
    _write(coverage, directory, "03_konformal_kapsama.csv")

    # -- 04 siralama --------------------------------------------------------
    ranking = pd.concat([
        ev.compare_with_baselines(bundle, valid_index, valid_score, cfg, "valid"),
        ev.compare_with_baselines(bundle, test_index, test_score, cfg, "test"),
    ], ignore_index=True)
    # Politika (seffaf) birlestirme ve ham olasilik da ayni tabloda
    extra = [
        ev.ranking_metrics(y_test, test_scored["policy_score"].to_numpy(), cfg.eval_ks,
                           "politika agirlikli birlestirme", "test",
                           bootstrap=cfg.bootstrap_n, seed=cfg.seed),
    ]
    ranking = pd.concat([ranking, pd.DataFrame(extra)], ignore_index=True)
    ranking = ranking.sort_values(["bolum", "PR_AUC"], ascending=[True, False])
    _write(ranking, directory, "04_siralama.csv")

    # -- 05/06 sinyal davranisi --------------------------------------------
    discrimination = ev.signal_discrimination(test_scored, y_test)
    discrimination.insert(1, "ad", [signal_by_code(c)["ad"] for c in discrimination["sinyal"]])
    _write(discrimination, directory, "05_sinyal_ayirt.csv")

    correlation = ev.signal_correlation(test_scored).reset_index().rename(columns={"index": "sinyal"})
    _write(correlation, directory, "06_sinyal_korelasyon.csv")

    # -- 07 ablation --------------------------------------------------------
    ablation = pd.DataFrame()
    if run_ablation:
        train_inputs = _risk_inputs(model, bundle, splits.train, scored, "train")
        valid_inputs = _risk_inputs(model, bundle, splits.valid_a, scored, "valid")
        test_inputs = _risk_inputs(model, bundle, test_index, scored, "test")
        ablation = ev.ablation(
            cfg,
            train_inputs, bundle.target(splits.train),
            valid_inputs, bundle.target(splits.valid_a),
            test_inputs, y_test,
            k=TOP_K,
        )
        ablation.insert(
            1, "ad",
            [("-" if c == "-" else (signal_by_code(c)["ad"] if c in SIGNAL_CODES else c))
             for c in ablation["cikarilan"]],
        )
        _write(ablation, directory, "07_ablation.csv")

    # -- 08 alt grup --------------------------------------------------------
    subgroups = pd.concat([
        ev.subgroup_performance(test_frame, y_test, test_score.to_numpy(), by, k=TOP_K)
        for by in ("sector", "size_band", "f_data_confidence_level", "province")
    ], ignore_index=True)
    _write(subgroups, directory, "08_alt_grup.csv")

    # -- 09 mekanizma -------------------------------------------------------
    mechanism = ev.mechanism_recall(bundle.labels, test_index, test_score.to_numpy())
    _write(mechanism, directory, "09_mekanizma.csv")

    # -- 10 kalibrasyon -----------------------------------------------------
    reliability = ev.reliability_table(y_test, test_scored["risk_probability"].to_numpy())
    reliability.insert(0, "bolum", "test")
    valid_reliability = ev.reliability_table(y_valid, valid_scored["risk_probability"].to_numpy())
    valid_reliability.insert(0, "bolum", "valid")
    _write(pd.concat([valid_reliability, reliability], ignore_index=True), directory,
           "10_kalibrasyon.csv")

    # -- 11/12 fayda ve yanlis pozitif --------------------------------------
    benefit = ev.yield_curve(bundle.labels, test_index, test_score.to_numpy())
    _write(benefit, directory, "11_fayda.csv")

    false_positive = ev.false_positive_profile(bundle.labels, test_index, test_score.to_numpy(), k=TOP_K)
    _write(false_positive, directory, "12_yanlis_pozitif.csv")

    # -- ozet metrikler -----------------------------------------------------
    metrics = _summarise(
        model, bundle, scored, ranking, coverage, benefit, mechanism, y_test, y_valid
    )
    (directory / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    card = model_card(
        model, bundle, cfg, metrics, ranking, coverage, discrimination,
        ablation, subgroups, mechanism, benefit, false_positive,
    )
    (directory / "MODEL_KARTI.md").write_text(card, encoding="utf-8")

    periods = {
        name: ", ".join(sorted(bundle.rows(index)["period"].astype(str).unique()))
        for name, index in (("train", splits.train), ("valid", valid_index), ("test", test_index))
    }
    _print_summary(metrics, directory)
    return {"metrics": metrics, "periods": periods}


def _risk_inputs(
    model: GusModel,
    bundle: Bundle,
    index: pd.Index,
    scored: Dict[str, pd.DataFrame],
    key: str,
) -> pd.DataFrame:
    """Ablation icin fusion girdi matrisi (sinyal puanlari + aralik + baglam)."""
    frame = bundle.rows(index)
    source = scored[key].reindex(index)
    columns = [c for c in source.columns if c.startswith(("raw_", "sig_", "avail_", "interval_"))]
    columns.append("active_signal_count")
    columns = [c for c in dict.fromkeys(columns) if c in source.columns]
    return pd.concat([frame, source[columns]], axis=1)


def _summarise(
    model: GusModel,
    bundle: Bundle,
    scored: Dict[str, pd.DataFrame],
    ranking: pd.DataFrame,
    coverage: pd.DataFrame,
    benefit: pd.DataFrame,
    mechanism: pd.DataFrame,
    y_test: np.ndarray,
    y_valid: np.ndarray,
) -> Dict:
    def _row(model_name: str, split: str) -> Dict:
        match = ranking[(ranking["model"] == model_name) & (ranking["bolum"] == split)]
        return match.iloc[0].to_dict() if len(match) else {}

    fusion_test = _row("GUS-DEDEKTIV (fusion)", "test")
    fusion_valid = _row("GUS-DEDEKTIV (fusion)", "valid")
    best_baseline = (
        ranking[(ranking["bolum"] == "test") & (ranking["model"].str.startswith("bl_"))]
        .sort_values("PR_AUC", ascending=False)
    )
    best_baseline_row = best_baseline.iloc[0].to_dict() if len(best_baseline) else {}

    test_coverage = coverage[(coverage["bolum"] == "test") & (coverage["grup"] == "tumu")]
    valid_coverage = coverage[(coverage["bolum"] == "valid") & (coverage["grup"] == "tumu")]

    calibration = ev.calibration_summary(y_test, scored["test"]["risk_probability"].to_numpy())

    a08 = mechanism[mechanism["mekanizma"] == "A08_dis_kanit_uyumsuz"]

    return {
        "model_version": model.cfg.model_version,
        "data_version": model.data_version,
        "test": {
            "n": int(fusion_test.get("n", 0)),
            "prevalans": fusion_test.get("prevalans"),
            "PR_AUC": fusion_test.get("PR_AUC"),
            "ROC_AUC": fusion_test.get("ROC_AUC_ek_gosterge"),
            "Precision@100": fusion_test.get("Precision@100"),
            "Precision@100_CI": [
                fusion_test.get("Precision@100_CI_alt"),
                fusion_test.get("Precision@100_CI_ust"),
            ],
            "Recall@100": fusion_test.get("Recall@100"),
            "Lift@100": fusion_test.get("Lift@100"),
            "Precision@50": fusion_test.get("Precision@50"),
            "Lift@50": fusion_test.get("Lift@50"),
        },
        "valid": {
            "PR_AUC": fusion_valid.get("PR_AUC"),
            "Precision@100": fusion_valid.get("Precision@100"),
        },
        "en_iyi_baseline": {
            "ad": best_baseline_row.get("model"),
            "PR_AUC": best_baseline_row.get("PR_AUC"),
            "Precision@100": best_baseline_row.get("Precision@100"),
        },
        "konformal": {
            "hedef_kapsama": model.cfg.target_coverage,
            "gozlenen_valid": float(valid_coverage["gozlenen_kapsama"].iloc[0]) if len(valid_coverage) else None,
            "gozlenen_test": float(test_coverage["gozlenen_kapsama"].iloc[0]) if len(test_coverage) else None,
            "ortanca_bagil_genislik_test": float(test_coverage["ortanca_bagil_genislik"].iloc[0]) if len(test_coverage) else None,
        },
        "olasilik_kalibrasyonu": calibration,
        "fayda_top100": benefit[benefit["K"] == TOP_K].to_dict("records")[0] if (benefit["K"] == TOP_K).any() else {},
        "kavramsal_kayma_A08": a08.to_dict("records")[0] if len(a08) else {},
        "harman_agirligi_hist": round(model.blend.weight, 3),
    }


def _print_summary(metrics: Dict, directory: Path) -> None:
    test = metrics["test"]
    print("\nTEST bolumu - ozet")
    print("-" * 74)
    print(f"  PR-AUC                : {test['PR_AUC']}")
    print(f"  ROC-AUC (ek gosterge) : {test['ROC_AUC']}")
    print(f"  Precision@100         : {test['Precision@100']}  "
          f"(CI {test['Precision@100_CI'][0]} - {test['Precision@100_CI'][1]})")
    print(f"  Recall@100            : {test['Recall@100']}")
    print(f"  Lift@100              : {test['Lift@100']}")
    baseline = metrics["en_iyi_baseline"]
    print(f"  en iyi baseline       : {baseline['ad']} "
          f"PR-AUC {baseline['PR_AUC']} / Precision@100 {baseline['Precision@100']}")
    conformal = metrics["konformal"]
    print(f"  konformal kapsama     : hedef {conformal['hedef_kapsama']} / "
          f"valid {conformal['gozlenen_valid']} / test {conformal['gozlenen_test']}")
    print(f"\nRaporlar: {directory}")


# --------------------------------------------------------------------------
# Model karti
# --------------------------------------------------------------------------
def _table(frame: pd.DataFrame, columns: Optional[List[str]] = None, limit: int = 40) -> str:
    if frame is None or len(frame) == 0:
        return "_(uretilmedi)_\n"
    view = frame[columns] if columns else frame
    view = view.head(limit)
    header = "| " + " | ".join(str(c) for c in view.columns) + " |"
    rule = "|" + "|".join("---" for _ in view.columns) + "|"
    rows = [
        "| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |"
        for row in view.itertuples(index=False)
    ]
    return "\n".join([header, rule, *rows]) + "\n"


def model_card(
    model: GusModel,
    bundle: Bundle,
    cfg: ModelConfig,
    metrics: Dict,
    ranking: pd.DataFrame,
    coverage: pd.DataFrame,
    discrimination: pd.DataFrame,
    ablation: pd.DataFrame,
    subgroups: pd.DataFrame,
    mechanism: pd.DataFrame,
    benefit: pd.DataFrame,
    false_positive: pd.DataFrame,
) -> str:
    test = metrics["test"]
    conformal = metrics["konformal"]
    periods = {
        name: sorted(bundle.rows(index)["period"].astype(str).unique())
        for name, index in (
            ("train", bundle.splits.train),
            ("valid", bundle.splits.valid),
            ("test", bundle.splits.test),
        )
    }

    test_ranking = ranking[ranking["bolum"] == "test"]
    ranking_columns = [
        "model", "PR_AUC", "ROC_AUC_ek_gosterge", "Precision@50", "Precision@100",
        "Recall@100", "Lift@100", "Precision@100_CI_alt", "Precision@100_CI_ust",
    ]
    ranking_columns = [c for c in ranking_columns if c in test_ranking.columns]

    coverage_view = coverage[(coverage["bolum"] == "test")]

    return f"""# GUS-DEDEKTIV - Model Karti

**Model surumu:** `{metrics['model_version']}` · **Veri surumu:** `{metrics['data_version']}`
**Egitim tohumu:** {cfg.seed} · **Hedef kapsama:** {cfg.target_coverage}

---

## 1. Once sinirliliklar

- Model **SENTETIK** veri uzerinde egitilmistir. Buradaki performans
  **gercek kamu performansi olarak sunulamaz**.
- Cikti **operasyonel inceleme onceligidir**; suc, ihlal veya usulsuzluk
  olasiligi **degildir**. Model tek basina ceza veya olumsuz idari karar
  **uretemez**; nihai karar yetkili insan denetciye aittir.
- Egitim penceresinde yalnizca {int(bundle.target(bundle.splits.train).sum())} pozitif ornek vardir.
  Precision@100 gibi metrikler dar orneklemde genis guven araligi tasir; bu
  nedenle **bootstrap guven araliklari** ile birlikte raporlanir.
- `A08_dis_kanit_uyumsuz` mekanizmasi egitimde nadir, testte siktir. Bu
  **kasitli bir kavramsal kayma (concept drift) testidir**; ilgili satira bakiniz.
- Il (`province`) bilgisi modele **girdi olarak verilmemistir**. Cografi
  profilleme riski nedeniyle yalnizca alt grup adalet olcumunde kullanilir.
- Model **veri toplamaz**. Kurumun kendi verisini kendi ortaminda degerlendirir.

## 2. Ne yapar

Firma-ceyrek GEKAP beyani icin (a) beklenen beyan araligini kalibre ederek
uretir, (b) sekiz ayri kanit sinyalini degerlendirir, (c) bunlari 0-100
inceleme onceligine cevirir, (d) her sonucu hangi sinyalin ne kadar
urettigini SHAP katkisiyla acikca soyler, (e) **degerlendirilemeyen** sinyali
nedeniyle birlikte bildirir.

Analiz birimi **firma-ceyrek**tir.

## 3. Mimari

| Katman | Bilesen | Yontem |
|---|---|---|
| 3 | Tarihsel baslik | LightGBM quantile (q05/q50/q95), hedef `log1p(beyan)` |
| 3 | Emsal baslik | LightGBM quantile; firmanin **kendi beyan gecmisi girmez** |
| 3 | Harman | log uzayinda agirlikli ortalama, agirlik = **{metrics['harman_agirligi_hist']}** (valid_a pinball) |
| 3 | Kalibrasyon | Mondrian **CQR** (sector x size_band -> sector -> size_band -> global) |
| 4 | Sekiz sinyal | ham istatistik -> egitim penceresi yuzdelik rampasi -> 0-100 |
| 4 | Birlestirme | LightGBM (girdi: sinyaller + kullanilabilirlik + aralik konumu + veri guveni) |
| 4 | Puan | izotonik kalibrasyon -> referans yuzdelik -> 0-100 |
| 5 | Aciklama | TreeSHAP katkisi -> sinyal duzeyi -> **sablonlu** gerekce cumlesi |

Gerekce metni sablonludur; serbest uretimli dil modeli **kullanilmaz**.
Ayni girdi ayni cumleyi uretir ve her cumle arkasindaki sayiyi tasir.

## 4. Veri ve bolumleme

| Bolum | Donemler |
|---|---|
| train | {', '.join(periods['train'])} |
| valid | {', '.join(periods['valid'])} |
| test | {', '.join(periods['test'])} |

`valid`, **firma bazinda** ikiye ayrilir: `valid_a` model secimi ve erken
durdurma, `valid_b` kalibrasyon. Ayni satirlari hem secim hem kalibrasyon
icin kullanmak kapsama oranini iyimser gosterirdi.

Konformal artiklar ek olarak egitim bolumunun **capraz uydurulmus
(out-of-fold)** tahminlerinden alinir; boylece artiklar ornekle**m disi**dir.

## 5. Test bolumu sonuclari

> Test bolumu **yalnizca bir kez** okunmustur. Tum model ve esik secimleri
> `valid` uzerinde yapilmistir.

| Metrik | Deger |
|---|---|
| Kayit / pozitif | {test['n']} / prevalans {test['prevalans']} |
| PR-AUC | **{test['PR_AUC']}** |
| ROC-AUC (ek gosterge) | {test['ROC_AUC']} |
| Precision@50 | {test.get('Precision@50')} (Lift {test.get('Lift@50')}) |
| Precision@100 | **{test['Precision@100']}** (bootstrap %95 GA {test['Precision@100_CI'][0]} - {test['Precision@100_CI'][1]}) |
| Recall@100 | {test['Recall@100']} |
| Lift@100 | **{test['Lift@100']}** |

### Referans baseline'lar ile ayni tabloda

Metrik tanimlari `gus_generator.quality` icinden ithal edilmistir; iki tablo
ayni fonksiyonlari kullanir.

{_table(test_ranking, ranking_columns)}

## 6. Beklenen aralik ve kalibrasyon

Hedef kapsama **{conformal['hedef_kapsama']}**.
Gozlenen kapsama: valid **{conformal['gozlenen_valid']}**, test **{conformal['gozlenen_test']}**.
Test bolumunde ortanca bagil aralik genisligi **{conformal['ortanca_bagil_genislik_test']}**.

{_table(coverage_view, ["grup", "n", "gozlenen_kapsama", "ortanca_genislik_ton", "ortanca_bagil_genislik"], limit=20)}

Olasilik kalibrasyonu (test): Brier **{metrics['olasilik_kalibrasyonu']['brier']}**,
ECE **{metrics['olasilik_kalibrasyonu']['ece']}**,
ortalama tahmin {metrics['olasilik_kalibrasyonu']['ortalama_tahmin']} vs
gozlenen prevalans {metrics['olasilik_kalibrasyonu']['gozlenen_prevalans']}.

## 7. Sinyaller

Sinyaller **bagimsiz degil, ayridir**; korelasyonlari `06_sinyal_korelasyon.csv`
icindedir. Tek basina ayirt gucleri:

{_table(discrimination)}

### Ablation - her sinyal cikarilarak yeniden egitim

{_table(ablation)}

## 8. Alt grup davranisi

{_table(subgroups, ["boyut", "grup", "n", "prevalans", "PR_AUC", "Top100_payi"], limit=45)}

## 9. Mekanizma bazli yakalama ve kavramsal kayma

{_table(mechanism)}

## 10. Denetim faydasi

{_table(benefit)}

### Top-100 icindeki negatiflerin profili

`N10_mesru_gorunum`, mesru nedenle riskli **gorunen** kayitlardir; denetciye
gerekce panelinde nedeniyle birlikte gosterilir. `N09_veri_eksikligi` dusuk
risk **sayilmaz**, ayri veri incelemesi kuyruguna gider.

{_table(false_positive)}

## 11. Kullanim sinirlari

- Puan siralamadir; esik gecmek **ihlal kaniti degildir**.
- Kullanilamayan sinyal **temiz sonuc degildir**; veri guveni dusurulur.
- Model kararlari `decision_id` ile model ve veri surumune baglanir.
- Gercek veriye gecişte sinyal mantigi degismez; sentetik alanlar karsilik
  gelen resmi kaynakla degistirilir.
"""


__all__ = ["write_reports", "model_card"]
