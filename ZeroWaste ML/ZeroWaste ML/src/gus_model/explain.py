"""Katman 5 - aciklama.

Iki parcasi var:

`signal_contributions`  TreeSHAP katkilarini SINYAL duzeyine toplar. Bir
    sinyalin katkisi, o sinyale ait tum girdilerin (puani ve kullanilabilirlik
    bayragi) katkilarinin toplamidir. Boylece "S1 %31 katti" ifadesi modelin
    gercek hesabina karsilik gelir, sonradan uydurulmus bir agirliga degil.

`reasons`  Katkilari SABLONLU cumleye cevirir. Sablon secildi cunku metin
    deterministik ve denetlenebilir olmalidir: ayni girdi ayni cumleyi uretir,
    halusinasyon riski yoktur ve her cumle arkasindaki sayiyi tasir. Serbest
    uretimli bir dil modeli bu iki ozelligi de veremez.

Diller: `tr` ve `en`. Backend `en` yayinlar (kural motoruyla ayni), rapor ve
model karti `tr` kullanir.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .config import SIGNAL_CODES, signal_by_code

# Sinyal disi girdi gruplari - katki tablosunda ayri satir olarak gorunur
GROUP_INTERVAL = "INTERVAL"
GROUP_CONTEXT = "CONTEXT"


def feature_groups(features: Sequence[str]) -> Dict[str, List[str]]:
    """Fusion girdilerini sinyal / aralik / baglam gruplarina ayirir."""
    groups: Dict[str, List[str]] = {code: [] for code in SIGNAL_CODES}
    groups[GROUP_INTERVAL] = []
    groups[GROUP_CONTEXT] = []

    for name in features:
        matched = None
        for code in SIGNAL_CODES:
            key = code.lower()
            if name in (f"raw_{key}", f"sig_{key}", f"avail_{key}"):
                matched = code
                break
        if matched:
            groups[matched].append(name)
        elif name.startswith("interval_"):
            groups[GROUP_INTERVAL].append(name)
        else:
            groups[GROUP_CONTEXT].append(name)
    return groups


def signal_contributions(
    shap_frame: pd.DataFrame,
    features: Sequence[str],
) -> pd.DataFrame:
    """Grup basina SHAP katkisi (log-odds uzayinda, isaretli)."""
    groups = feature_groups(features)
    out = pd.DataFrame(index=shap_frame.index)
    for name, columns in groups.items():
        present = [c for c in columns if c in shap_frame.columns]
        out[f"shap_{name.lower()}"] = (
            shap_frame[present].sum(axis=1) if present else 0.0
        )
    out["shap_base"] = shap_frame["base_value"] if "base_value" in shap_frame else 0.0
    return out


def contribution_shares(contributions: pd.DataFrame) -> pd.DataFrame:
    """Sekiz sinyalin POZITIF katkilarinin normalize edilmis paylari.

    Yalnizca pozitif katkilar paylastirilir: denetciye "bu dosyayi kuyrugun
    yukarisina TASIYAN neydi" sorusunun cevabi verilir. Negatif katkilar
    (riski dusuren kanit) ayrica `shap_*` sutunlarinda durur.
    """
    columns = [f"shap_{code.lower()}" for code in SIGNAL_CODES]
    values = contributions[columns].to_numpy(dtype=float)
    positive = np.clip(values, 0.0, None)
    total = positive.sum(axis=1, keepdims=True)
    shares = np.divide(positive, total, out=np.zeros_like(positive), where=total > 1e-12)
    return pd.DataFrame(
        {f"contribution_{code.lower()}": shares[:, i] for i, code in enumerate(SIGNAL_CODES)},
        index=contributions.index,
    )


# --------------------------------------------------------------------------
# Sablonlu gerekce metni
# --------------------------------------------------------------------------
TEMPLATES: Dict[str, Dict[str, str]] = {
    "S1": {
        "tr": "Firma, kendi gecmis beyan davranisindan beklenen {beklenen} ton yerine {beyan} ton beyan etti (%{fark} altinda).",
        "en": "Declared {beyan} t where this company's own filing history implies {beklenen} t, {fark}% below it.",
    },
    "S2": {
        "tr": "Ayni sektor ve olcekteki emsal firmalarin beklentisi {beklenen} ton iken beyan {beyan} ton (%{fark} altinda).",
        "en": "Peers of the same sector and size imply {beklenen} t; the declaration is {beyan} t, {fark}% below.",
    },
    "S3": {
        "tr": "Urun agacindan beklenen ambalaj tonaji {beklenen} ton (agirlik matrisi kapsami %{kapsam}), beyan {beyan} ton (%{fark} altinda).",
        "en": "The product tree implies {beklenen} t of packaging ({kapsam}% matrix coverage) against a declaration of {beyan} t, {fark}% below.",
    },
    "S4": {
        "tr": "Uretim %{uretim} degisirken ambalaj beyani %{beyan_degisim} degisti; ayrisma {fark} puan.",
        "en": "Output moved {uretim}% while the packaging declaration moved {beyan_degisim}%, a {fark} point divergence.",
    },
    "S5": {
        "tr": "Ic piyasa arzina gore beyan orani, firmanin kendi gecmis seviyesinin %{fark} altinda.",
        "en": "Declared packaging per tonne placed on the domestic market is {fark}% below this company's own past level.",
    },
    "S6": {
        "tr": "Ayni ceyregin kendi kalibina gore beyan %{fark} dusuk; mevsimsellikle aciklanmiyor.",
        "en": "Against its own pattern for this quarter the declaration is {fark}% low, which seasonality does not explain.",
    },
    "S7": {
        "tr": "Beyan edilen malzeme kompozisyonu onceki doneme gore {kayma} birim kaydi{matris}.",
        "en": "The reported material composition shifted by {kayma} against the previous period{matris}.",
    },
    "S8": {
        "tr": "Dis dogrulama kaydi {beklenen} ton gosterirken beyan {beyan} ton (%{fark} altinda).",
        "en": "External verification records {beklenen} t against a declaration of {beyan} t, {fark}% below.",
    },
}

CLEAR_TEMPLATES: Dict[str, Dict[str, str]] = {
    "S1": {"tr": "Kendi gecmisine gore beyanda anlamli bir dusus yok.",
           "en": "No material shortfall against the company's own history."},
    "S2": {"tr": "Emsal grubun beklenen araligi icinde.",
           "en": "Within the expected range for its peer group."},
    "S3": {"tr": "Urun agaci beklentisi ile beyan uyumlu.",
           "en": "The declaration is in line with the product tree expectation."},
    "S4": {"tr": "Uretim ve beyan hareketleri birlikte seyrediyor.",
           "en": "Output and declared volume moved together."},
    "S5": {"tr": "Dis ticaret ve duzeltmeler beyanla tutarli.",
           "en": "Trade volumes and corrections are consistent with the declaration."},
    "S6": {"tr": "Ceyreklik kalipta kirilma yok.",
           "en": "No break in the quarterly pattern."},
    "S7": {"tr": "Malzeme kompozisyonu onceki donemle uyumlu.",
           "en": "Material composition is consistent with the previous period."},
    "S8": {"tr": "Dis dogrulama kaydi beyanla uyumlu.",
           "en": "External verification records agree with the declaration."},
}

MATRIX_SUFFIX = {
    "tr": "; ambalaj agirlik matrisi {yil} yilindan beri guncellenmemis",
    "en": "; the packaging weight matrix has not been updated since {yil}",
}


def _pct(value: float) -> str:
    return f"{value * 100:.0f}"


def _ton(value: float) -> str:
    if not np.isfinite(value):
        return "-"
    return f"{value:,.0f}" if abs(value) >= 100 else f"{value:,.1f}"


def signal_sentence(
    code: str,
    row: pd.Series,
    expectation: pd.Series,
    lang: str = "tr",
    active: bool = True,
) -> str:
    """Bir sinyalin gerekce cumlesi."""
    if not active:
        return CLEAR_TEMPLATES[code][lang]

    declared = float(row.get("declared_packaging_tonnage", np.nan))
    raw = float(row.get(f"raw_{code.lower()}", np.nan))
    template = TEMPLATES[code][lang]

    if code == "S1":
        expected = float(expectation.get("hist_q50", np.nan))
        return template.format(beklenen=_ton(expected), beyan=_ton(declared), fark=_pct(max(raw, 0.0)))
    if code == "S2":
        expected = float(expectation.get("peer_q50", np.nan))
        return template.format(beklenen=_ton(expected), beyan=_ton(declared), fark=_pct(max(raw, 0.0)))
    if code == "S3":
        # Gosterilen beklenti, kapsam oranina bolunerek tam urun agacina
        # genisletilmis olandir - sinyalin uzerinde calistigi buyukluk budur.
        coverage = float(row.get("f_s3_bom_coverage", np.nan))
        partial = float(row.get("f_s3_bom_expected", np.nan))
        expected = partial / coverage if np.isfinite(coverage) and coverage > 0 else np.nan
        return template.format(
            beklenen=_ton(expected),
            kapsam=_pct(coverage) if np.isfinite(coverage) else "-",
            beyan=_ton(declared),
            fark=_pct(max(raw, 0.0)),
        )
    if code == "S4":
        prod = float(row.get("f_s4_prod_yoy", row.get("f_s4_prod_qoq", np.nan)))
        decl = float(row.get("f_s1_decl_yoy", row.get("f_s1_decl_qoq", np.nan)))
        return template.format(
            uretim=_pct(prod) if np.isfinite(prod) else "-",
            beyan_degisim=_pct(decl) if np.isfinite(decl) else "-",
            fark=f"{raw * 100:.0f}",
        )
    if code in ("S5", "S6"):
        return template.format(fark=_pct(max(raw, 0.0)))
    if code == "S7":
        shift = float(row.get("f_s7_mix_shift_l1", np.nan))
        stale = float(row.get("f_s7_matrix_stale_flag", 0.0)) > 0.5
        vintage = row.get("f_s7_matrix_age_years", None)
        suffix = ""
        if stale and vintage is not None and np.isfinite(float(vintage)):
            year = int(row.get("year", 0)) - int(float(vintage))
            suffix = MATRIX_SUFFIX[lang].format(yil=year if year > 1900 else "-")
        return template.format(kayma=f"{shift:.2f}" if np.isfinite(shift) else "-", matris=suffix)
    if code == "S8":
        gap = float(row.get("f_s8_external_gap_abs", np.nan))
        external = declared + gap if np.isfinite(gap) else np.nan
        return template.format(beklenen=_ton(external), beyan=_ton(declared), fark=_pct(max(raw, 0.0)))
    return ""


def reasons(
    row: pd.Series,
    signal_row: pd.Series,
    expectation: pd.Series,
    contributions: pd.Series,
    lang: str = "tr",
    limit: int = 3,
    active_threshold: float = 22.0,
) -> List[str]:
    """En cok katki veren, ATESLEMIS sinyallerin gerekce cumleleri."""
    ranked: List[Tuple[float, str]] = []
    for code in SIGNAL_CODES:
        key = code.lower()
        if signal_row.get(f"avail_{key}", 0) <= 0:
            continue
        score = float(signal_row.get(f"sig_{key}", np.nan))
        if not np.isfinite(score) or score < active_threshold:
            continue
        share = float(contributions.get(f"contribution_{key}", 0.0))
        ranked.append((share, code))

    ranked.sort(reverse=True)
    combined = pd.concat([row, signal_row])
    out: List[str] = []
    for _, code in ranked[:limit]:
        sentence = signal_sentence(code, combined, expectation, lang=lang, active=True)
        out.append(f"{sentence} ({code})")
    return out


def explanation_table(
    frame: pd.DataFrame,
    signal_scores: pd.DataFrame,
    expectation: pd.DataFrame,
    contributions: pd.DataFrame,
    lang: str = "tr",
) -> pd.DataFrame:
    """Kayit basina sinyal durumu, katki ve gerekce - denetci paneli icin."""
    records: List[Dict] = []
    for observation_id in frame.index:
        row = frame.loc[observation_id]
        signal_row = signal_scores.loc[observation_id]
        exp_row = expectation.loc[observation_id]
        contrib_row = contributions.loc[observation_id]

        used: List[Dict] = []
        unavailable: List[Dict] = []
        for code in SIGNAL_CODES:
            key = code.lower()
            spec = signal_by_code(code)
            if signal_row.get(f"avail_{key}", 0) <= 0:
                unavailable.append({"signal": code, "reason": spec["avail_reason"]})
                continue
            used.append({
                "signal": code,
                "name": spec["ad"],
                "score": float(signal_row.get(f"sig_{key}", np.nan)),
                "status": str(signal_row.get(f"status_{key}", "")),
                "contribution": round(float(contrib_row.get(f"contribution_{key}", 0.0)), 4),
            })

        records.append({
            "observation_id": observation_id,
            "reasons": reasons(row, signal_row, exp_row, contrib_row, lang=lang),
            "signals_used": used,
            "signals_unavailable": unavailable,
        })
    return pd.DataFrame(records).set_index("observation_id")


__all__ = [
    "feature_groups",
    "signal_contributions",
    "contribution_shares",
    "signal_sentence",
    "reasons",
    "explanation_table",
    "TEMPLATES",
    "CLEAR_TEMPLATES",
]
