"""Profesyonel .xlsx ciktisi (16 sayfa).

Bicimlendirme: filtreler, dondurulmus baslik, sutun genislikleri, kurumsal
renk sistemi, sayi/tarih formatlari, formulle hesaplanan alanlar, data
validation, kosullu bicimlendirme, dashboard grafikleri.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config import GEKAP_MATERIALS, ANOMALY_TYPES, LEGITIMATE_CAUSES

# --- Kurumsal renk sistemi ---
C_HDR = "#0B3D5C"      # lacivert - baslik
C_HDR_TXT = "#FFFFFF"
C_ACCENT = "#0E7C7B"   # turkuaz - vurgu
C_WARN = "#B3261E"     # kirmizi - uyari
C_OK = "#1B7F3B"       # yesil
C_BAND = "#F2F6F9"     # acik zebra
C_OFFICIAL = "#DCEBF7"
C_SYNTH = "#FDF0DC"
C_DERIVED = "#E8F3EA"


def _fmt(wb) -> Dict:
    f = {}
    f["title"] = wb.add_format({"bold": True, "font_size": 16, "font_color": C_HDR})
    f["subtitle"] = wb.add_format({"bold": True, "font_size": 12, "font_color": C_ACCENT})
    f["h"] = wb.add_format({"bold": True, "bg_color": C_HDR, "font_color": C_HDR_TXT,
                            "border": 1, "text_wrap": True, "valign": "vcenter", "align": "center"})
    f["txt"] = wb.add_format({"text_wrap": True, "valign": "top", "border": 1})
    f["txt_nb"] = wb.add_format({"text_wrap": True, "valign": "top"})
    f["num0"] = wb.add_format({"num_format": "#,##0", "border": 1})
    f["num2"] = wb.add_format({"num_format": "#,##0.00", "border": 1})
    f["num4"] = wb.add_format({"num_format": "#,##0.0000", "border": 1})
    f["pct"] = wb.add_format({"num_format": "0.00%", "border": 1})
    f["tl"] = wb.add_format({"num_format": '#,##0.00" TL"', "border": 1})
    f["date"] = wb.add_format({"num_format": "yyyy-mm-dd", "border": 1})
    f["url"] = wb.add_format({"font_color": "#0563C1", "underline": 1, "text_wrap": True,
                              "valign": "top", "border": 1})
    f["warn"] = wb.add_format({"bold": True, "font_color": C_WARN, "text_wrap": True, "valign": "top"})
    f["ok"] = wb.add_format({"bold": True, "font_color": C_OK})
    f["official"] = wb.add_format({"bg_color": C_OFFICIAL, "border": 1, "text_wrap": True, "valign": "top"})
    f["synth"] = wb.add_format({"bg_color": C_SYNTH, "border": 1, "text_wrap": True, "valign": "top"})
    f["derived"] = wb.add_format({"bg_color": C_DERIVED, "border": 1, "text_wrap": True, "valign": "top"})
    f["banner"] = wb.add_format({"bold": True, "bg_color": C_WARN, "font_color": "#FFFFFF",
                                 "text_wrap": True, "valign": "vcenter"})
    f["banner_ok"] = wb.add_format({"bold": True, "bg_color": C_ACCENT, "font_color": "#FFFFFF",
                                    "text_wrap": True, "valign": "vcenter"})
    return f


_NUMERIC_HINTS = {
    "ton": "num4", "tonnage": "num4", "qty": "num2", "amount": "num2",
    "try": "tl", "score": "num4", "ratio": "num4", "share": "num4",
    "count": "num0", "days": "num0", "year": "num0", "n": "num0",
}


def _pick_format(col: str, series: pd.Series, f: Dict):
    lc = col.lower()
    if lc.endswith("_url") or lc == "url":
        return f["url"], 55
    if not pd.api.types.is_numeric_dtype(series):
        n = series.astype(str).str.len().max() if len(series) else 10
        width = int(min(max(len(col) + 2, (n or 10) * 0.95), 60))
        return f["txt"], width
    if "try" in lc:
        return f["tl"], 16
    for k, v in _NUMERIC_HINTS.items():
        if k in lc:
            return f[v], max(len(col) + 2, 13)
    return f["num4"], max(len(col) + 2, 13)


def _write_table(wb, ws, df: pd.DataFrame, f: Dict, start_row: int = 0,
                 autofilter: bool = True, freeze: bool = True,
                 max_rows: Optional[int] = None, note: str = "") -> int:
    """DataFrame'i bicimli olarak yazar. Son yazilan satirin indeksini doner."""
    if note:
        ws.write(start_row, 0, note, f["warn"])
        start_row += 2

    cols = list(df.columns)
    for j, c in enumerate(cols):
        ws.write(start_row, j, c, f["h"])

    body = df if max_rows is None else df.head(max_rows)
    for j, c in enumerate(cols):
        fmt, width = _pick_format(c, body[c], f)
        ws.set_column(j, j, width, fmt)
        series = body[c]
        is_num = pd.api.types.is_numeric_dtype(series)
        for i, v in enumerate(series.tolist()):
            r = start_row + 1 + i
            if v is None or (is_num and (pd.isna(v))):
                ws.write_blank(r, j, None, fmt)
            elif is_num:
                ws.write_number(r, j, float(v), fmt)
            elif isinstance(v, str) and v.startswith("http"):
                ws.write_url(r, j, v, f["url"], v)
            elif isinstance(v, (bool, np.bool_)):
                ws.write_boolean(r, j, bool(v), fmt)
            else:
                ws.write_string(r, j, str(v), fmt)

    last = start_row + len(body)
    if autofilter and len(cols):
        ws.autofilter(start_row, 0, last, len(cols) - 1)
    if freeze:
        ws.freeze_panes(start_row + 1, 0)
    ws.set_row(start_row, 34)
    return last


# ==========================================================================
def build_excel(bundle, out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    wb_writer = pd.ExcelWriter(out_path, engine="xlsxwriter")
    wb = wb_writer.book
    f = _fmt(wb)

    _sheet_readme(wb, f, bundle)
    _sheet_cop31(wb, f, bundle)
    _sheet_firms(wb, f, bundle)
    _sheet_observations(wb, f, bundle)
    _sheet_product_packaging(wb, f, bundle)
    _sheet_model_ready(wb, f, bundle)
    _sheet_audit_labels(wb, f, bundle)
    _sheet_evaluation(wb, f, bundle)
    _sheet_gekap_rates(wb, f, bundle)
    _sheet_macro(wb, f, bundle)
    _sheet_climate(wb, f, bundle)
    _sheet_sources(wb, f, bundle)
    _sheet_data_dictionary(wb, f, bundle)
    _sheet_methodology(wb, f, bundle)
    _sheet_gov_map(wb, f, bundle)
    _sheet_quality(wb, f, bundle)

    wb_writer.close()
    return out_path


# --------------------------------------------------------------------------
def _sheet_readme(wb, f, b):
    ws = wb.add_worksheet("README")
    ws.set_column(0, 0, 30)
    ws.set_column(1, 1, 115)
    ws.hide_gridlines(2)
    r = 0
    ws.write(r, 0, "GUS-DEDEKTIV", f["title"])
    ws.write(r, 1, "GEKAP Beyan Tutarliligi, Denetim Onceliklendirme ve Iklim Etki Platformu", f["title"]); r += 1
    ws.write(r, 0, "Takim", f["txt_nb"]); ws.write(r, 1, "KinetiX - TEKNOFEST 2026 Sifir Atik ve Dongusel Ekonomi", f["txt_nb"]); r += 2

    ws.merge_range(r, 0, r + 2, 1,
                   "UYARI - BU DATASET SENTETIKTIR.\n"
                   "Firma kayitlari, beyanlar ve denetim sonuclari TAMAMEN URETILMISTIR; hicbir gercek firmayi, "
                   "gercek GEKAP beyanini veya gercek denetim sonucunu temsil etmez. Bu veri uzerinde olculen model "
                   "performansi GERCEK KAMU PERFORMANSI OLARAK SUNULAMAZ.",
                   f["banner"]); r += 4

    rows = [
        ("Amac", "Kamu denetcisine, hangi firma-donem GEKAP beyaninin once incelenmesi gerektigini "
                 "GEREKCESIYLE gosteren karar destek sisteminin gelistirilmesi ve degerlendirilmesi icin "
                 "tekrar uretilebilir bir veri altyapisi saglamak."),
        ("Sistemin YAPMADIGI", "Firma adina beyanname hazirlamaz. Muhasebe programi degildir. Firmayi suclu ilan etmez. "
                               "Otomatik ceza karari vermez. Denetcinin yerini almaz. Hukuki delil uretme iddiasinda degildir."),
        ("0-100 puanin anlami", "OPERASYONEL INCELEME ONCELIGIDIR. Suc veya usulsuzluk OLASILIGI DEGILDIR."),
        ("Dataset surumu", b.manifest["dataset_version"]),
        ("Sema surumu", b.manifest["schema_version"]),
        ("Random seed", str(b.manifest["seed"])),
        ("Analiz birimi", "FIRMA-CEYREK (firma-yil degil)"),
        ("Firma sayisi", f"{b.manifest['n_firms']:,}".replace(",", ".")),
        ("Firma-ceyrek kayit", f"{b.manifest['n_observations']:,}".replace(",", ".")),
        ("SKU / ambalaj satiri", f"{b.manifest['n_skus']:,}".replace(",", ".")),
        ("Donem araligi", f"{b.manifest['periods'][0]} - {b.manifest['periods'][-1]} ({len(b.manifest['periods'])} ceyrek)"),
        ("Bolunme", "history=2023Q1-2023Q4 (yalnizca gecmis/ozellik uretimi, skorlanmaz) | "
                    "train=2024Q1-2025Q2 | valid=2025Q3-2025Q4 (kalibrasyon) | test=2026Q1-2026Q2 (zamansal holdout)"),
        ("Gercek anomali prevalansi", f"{b.manifest['prevalence_overall']:.4f}"),
    ]
    for k, v in rows:
        ws.write(r, 0, k, f["txt_nb"]); ws.write(r, 1, v, f["txt_nb"]); r += 1
    r += 1

    ws.write(r, 0, "UC VERI KATMANI", f["subtitle"]); r += 1
    layers = [
        ("Katman A - official_open", "Gercek acik veriler. GEKAP tarifeleri (Resmi Gazete), ambalaj atigi istatistikleri "
                                     "(CSB), geri kazanim oranlari, EPA WARM iklim faktorleri, COP31 bilgileri. "
                                     "Sayfalar: GEKAP_Rates, Macro_Anchors, Climate_Factors, Source_Registry.", f["official"]),
        ("Katman B - synthetic", "Gercek verilerden kalibre edilmis sentetik firma ve firma-ceyrek verisi. "
                                 "Sayfalar: Firms, Observations, Product_Packaging, Model_Ready.", f["synth"]),
        ("Katman C - synthetic label", "Sentetik audit ground-truth. Model girdilerinden AYRI sayfada tutulur; "
                                       "Model_Ready'ye sizdirilmaz. Sayfa: Audit_Labels.", f["synth"]),
        ("derived", "Yukaridakilerden formulle turetilmis alanlar (orn. potansiyel CO2e senaryolari).", f["derived"]),
    ]
    for k, v, fmt in layers:
        ws.write(r, 0, k, fmt); ws.write(r, 1, v, fmt); r += 1
    r += 1

    ws.write(r, 0, "SAYFA REHBERI", f["subtitle"]); r += 1
    guide = [
        ("COP31_Dashboard", "Dogrulanabilir metrikler ile SENARYO metriklerini AYRI bloklarda gosterir. COP31 hedef eslesmesi."),
        ("Firms", "Sentetik firma ana tablosu (Katman B)."),
        ("Observations", "Firma-ceyrek ham gozlem verisi - denetciye gorunen alanlar (Katman B)."),
        ("Product_Packaging", "SKU / urun agaci / GTIP baglami / ambalaj agirlik matrisi (Katman B)."),
        ("Model_Ready", "Model egitiminde kullanilabilecek ozellikler. GROUND TRUTH ICERMEZ."),
        ("Audit_Labels", "Sentetik ground-truth ve denetim sonuclari (Katman C). Egitimde girdi olarak KULLANILMAZ."),
        ("Evaluation", "Referans baseline skorlari, metrik protokolu ve test siralamasi."),
        ("GEKAP_Rates", "Resmi donemlere gore GEKAP tarifeleri (Katman A)."),
        ("Macro_Anchors", "Resmi makro kalibrasyon gostergeleri (Katman A)."),
        ("Climate_Factors", "CO2e ve geri kazanim senaryosu faktorleri (Katman A + derived)."),
        ("Source_Registry", "Butun kaynaklar ve DOGRUDAN LINKLER."),
        ("Data_Dictionary", "Butun sutunlarin aciklamasi ve veri sinifi."),
        ("Methodology", "Sentetik veri uretim kurallari, dagilimlar, varsayimlar, sinirliliklar."),
        ("Government_Integration_Map", "Devletin kendi verisini hangi alana baglayacagini gosteren harita."),
        ("Quality_Checks", "Eksik deger, dublikat, dagilim, mantik, sizinti ve gercekcilik kontrolleri."),
    ]
    for k, v in guide:
        ws.write(r, 0, k, f["txt_nb"]); ws.write(r, 1, v, f["txt_nb"]); r += 1
    r += 1

    ws.write(r, 0, "NASIL KULLANILIR", f["subtitle"]); r += 1
    how = [
        "1. Egitim: Model_Ready sayfasindan split='train' satirlarini alin. Hedef degiskeni Audit_Labels sayfasindan "
        "observation_id ile eslestirin.",
        "2. Kalibrasyon: split='valid' satirlarini conformal kalibrasyon icin ayirin. Egitimde KULLANMAYIN.",
        "3. Degerlendirme: split='test' (2026Q1-2026Q2) zamansal holdout'tur. Model gelistirme sirasinda ACMAYIN.",
        "4. split='history' (2023) satirlari yalnizca gecikmeli ozellik uretimi icindir; skorlanmaz ve degerlendirilmez. "
        "2023 GEKAP tarifeleri birincil kaynaktan dogrulanamadigi icin bu donemde parasal tutar HESAPLANMAMISTIR.",
        "5. Sizinti kontrolu: Model_Ready icinde truth/anomaly/audit/label iceren sutun BULUNMAMALIDIR. "
        "validate_dataset.py bunu otomatik dogrular.",
        "6. Yeniden uretim: python src/generate_dataset.py --seed 20260902 --firms 600",
    ]
    for h in how:
        ws.write(r, 1, h, f["txt_nb"]); r += 1
    r += 1

    ws.merge_range(r, 0, r + 1, 1,
                   "ONEMLI: Beyan duzeltmesi FIZIKSEL GERI DONUSUM DEGILDIR. Bu dosyadaki CO2e ve geri kazanim "
                   "rakamlari POTANSIYEL SENARYODUR (Potential scenario - not verified impact), gerceklesmis azaltim degildir.",
                   f["banner"])


# --------------------------------------------------------------------------
def _sheet_cop31(wb, f, b):
    ws = wb.add_worksheet("COP31_Dashboard")
    ws.hide_gridlines(2)
    ws.set_column(0, 0, 42); ws.set_column(1, 1, 52); ws.set_column(2, 2, 16)
    ws.set_column(3, 3, 14); ws.set_column(4, 4, 60); ws.set_column(5, 5, 46)
    r = 0
    ws.write(r, 0, "COP31 Packaging Transparency & Climate Impact Dashboard", f["title"]); r += 1
    ws.write(r, 0, "Onerilen pilot adi", f["txt_nb"])
    ws.write(r, 1, "Turkiye Packaging Transparency Pilot - COP31 Antalya Demonstration", f["txt_nb"]); r += 2

    ws.merge_range(r, 0, r + 2, 5,
                   "COP31 ile RESMI BIR ORTAKLIK YOKTUR. COP31 logosu kullanilmamistir. Asagidaki hedefler "
                   "COP31 BASKANLIK GUNDEMI niteligindedir; muzakere edilmis baglayici COP karari DEGILDIR "
                   "(bkz. Source_Registry SRC-009, SRC-010). Bu panel bir uyum/uygunluk beyani degil, "
                   "projenin bu gundemle NASIL ILISKILENDIGINI gosteren bir eslesme tablosudur.",
                   f["banner"]); r += 4

    cop = pd.DataFrame([
        {"COP31 baglami": "Tarih ve yer",
         "Aciklama": "9-20 Kasim 2026, Antalya EXPO Center, Turkiye",
         "Statu": "Dogrulandi", "source_id": "SRC-011",
         "GUS-DEDEKTIV ile iliski": "Pilot demonstrasyon takvimi bu tarihe gore planlanmistir.",
         "url": "https://unfccc.int/cop31/ifp"},
        {"COP31 baglami": "Baskanlik duzenlemesi",
         "Aciklama": "Turkiye ev sahibi ulke; muzakere baskanligi Avustralya ile ortak yurutulmektedir",
         "Statu": "Dogrulandi", "source_id": "SRC-011",
         "GUS-DEDEKTIV ile iliski": "Sunumda 'Turkiye COP31 baskani' ifadesi KULLANILMAMALIDIR.",
         "url": "https://unfccc.int/cop31/ifp"},
        {"COP31 baglami": "Kuresel atik artisinin 2035'e kadar YARIYA indirilmesi",
         "Aciklama": "Baskanlik gundemi hedefi. Taban yil ve kapsanan atik turleri tanimli DEGILDIR.",
         "Statu": "Baskanlik gundemi - baglayici karar degil", "source_id": "SRC-009 / SRC-010",
         "GUS-DEDEKTIV ile iliski": "Proje atigi fiziksel olarak azaltmaz; piyasaya surulen ambalaj miktarinin "
                                    "DAHA DOGRU GORUNMESINI saglar. Dogru olculmeyen atik azaltilamaz.",
         "url": "https://unfccc.int/news/cop31-presidency-announces-new-targets-on-global-electrification-cutting-waste-resilient-cities"},
        {"COP31 baglami": "Kuresel dongusel malzeme kullanim oraninin en az %15'e cikarilmasi",
         "Aciklama": "Baskanlik gundemi hedefi (2035).",
         "Statu": "Baskanlik gundemi - baglayici karar degil", "source_id": "SRC-009 / SRC-010",
         "GUS-DEDEKTIV ile iliski": "Dongusel malzeme kullanim orani PAYDA olarak dogru ambalaj arz verisine "
                                    "ihtiyac duyar. Proje paydayi iyilestirir; payi (fiili geri donusum) DOGRUDAN artirmaz.",
         "url": "https://healthpolicy-watch.news/cop31-electricity-waste-and-construction-sector-to-top-cop31-agenda/"},
        {"COP31 baglami": "Sifir atik ve atik kaynakli metan azaltiminin iklim eyleminin merkezine alinmasi",
         "Aciklama": "COP31 Eylem Gundemi onceliklerinden.",
         "Statu": "Baskanlik gundemi - baglayici karar degil", "source_id": "SRC-009 / SRC-010",
         "GUS-DEDEKTIV ile iliski": "Ambalaj akisinin gorunurlugu, uretici sorumlulugu politikalarinin daha "
                                    "kaliteli veriye dayanmasini saglar. METAN uzerinde DOGRUDAN etki iddia EDILMEMEKTEDIR.",
         "url": "https://unfccc.int/news/cop31-presidency-announces-new-targets-on-global-electrification-cutting-waste-resilient-cities"},
        {"COP31 baglami": "Taahhutten uygulamaya ve olculebilir sonuca gecis",
         "Aciklama": "Baskanlik soylemi.",
         "Statu": "Baskanlik gundemi", "source_id": "SRC-009",
         "GUS-DEDEKTIV ile iliski": "Panelin sol blogu (DOGRULANABILIR) tam olarak bu talebe cevap verir: "
                                    "her rakam bir kayda, bir denetci onayina ve bir karar kimligine baglanir.",
         "url": "https://unfccc.int/cop31/the-road-to-antalya"},
    ])
    last = _write_table(wb, ws, cop, f, start_row=r, freeze=False)
    r = last + 3

    dash = b.cop31_dashboard
    ws.write(r, 0, "BLOK 1 - DOGRULANABILIR METRIKLER (sentetik veri uzerinde dogrudan olculur)", f["banner_ok"])
    ws.set_row(r, 22); r += 1
    ver = dash[dash["blok"].str.startswith("DOGRULANABILIR")][["gosterge", "deger", "birim", "kaynak_hesap"]]
    last = _write_table(wb, ws, ver.reset_index(drop=True), f, start_row=r, autofilter=False, freeze=False)
    r = last + 3

    ws.write(r, 0, "BLOK 2 - SENARYO METRIKLERI (Potential scenario - not verified impact)", f["banner"])
    ws.set_row(r, 22); r += 1
    sc = dash[dash["blok"].str.startswith("SENARYO")][["gosterge", "deger", "birim", "kaynak_hesap"]]
    last = _write_table(wb, ws, sc.reset_index(drop=True), f, start_row=r, autofilter=False, freeze=False)
    r = last + 2
    ws.merge_range(r, 0, r + 1, 5,
                   "Senaryo zinciri: dogrulanmis_duzeltme_ton x varsayilan_geri_kazanim_orani x malzeme_payi x "
                   "WARM v16 faktoru = potansiyel_CO2e. Faktorler ABD ozgudur ve KISA TON biriminden metrik tona "
                   "cevrilmistir. Ayrinti ve duyarlilik araligi icin Climate_Factors sayfasina bakiniz.",
                   f["banner"]); r += 3

    # --- Grafik: malzeme bazli beyan tonaji (test donemi) ---
    mat_rows = dash[dash["gosterge"].str.startswith("Beyan edilen tonaj -")]
    if len(mat_rows):
        srow = r
        ws.write(srow, 0, "Malzeme", f["h"]); ws.write(srow, 1, "Ton (test donemi)", f["h"])
        for i, rec in enumerate(mat_rows.itertuples()):
            ws.write_string(srow + 1 + i, 0, rec.gosterge.replace("Beyan edilen tonaj - ", "").replace(" (test)", ""), f["txt"])
            ws.write_number(srow + 1 + i, 1, float(rec.deger), f["num2"])
        ch = wb.add_chart({"type": "column"})
        ch.add_series({
            "name": "Beyan edilen ambalaj tonaji (test donemi, sentetik)",
            "categories": ["COP31_Dashboard", srow + 1, 0, srow + len(mat_rows), 0],
            "values": ["COP31_Dashboard", srow + 1, 1, srow + len(mat_rows), 1],
            "fill": {"color": C_ACCENT},
        })
        ch.set_title({"name": "Malzeme turune gore beyan edilen ambalaj tonaji (SENTETIK)"})
        ch.set_legend({"none": True})
        ch.set_size({"width": 560, "height": 300})
        ws.insert_chart(srow, 3, ch)

        # Senaryo grafigi
        cs = b.climate_scenarios
        srow2 = srow + len(mat_rows) + 20
        ws.write(srow2, 0, "Senaryo", f["h"]); ws.write(srow2, 1, "Potansiyel CO2e (ton)", f["h"])
        for i, rec in enumerate(cs.itertuples()):
            ws.write_string(srow2 + 1 + i, 0, str(rec.senaryo), f["txt"])
            ws.write_number(srow2 + 1 + i, 1, float(rec.potansiyel_CO2e_ton), f["num2"])
        ch2 = wb.add_chart({"type": "bar"})
        ch2.add_series({
            "name": "POTANSIYEL CO2e - dogrulanmis azaltim DEGILDIR",
            "categories": ["COP31_Dashboard", srow2 + 1, 0, srow2 + len(cs), 0],
            "values": ["COP31_Dashboard", srow2 + 1, 1, srow2 + len(cs), 1],
            "fill": {"color": "#9C6F19"},
        })
        ch2.set_title({"name": "Potansiyel CO2e senaryolari (NOT VERIFIED IMPACT)"})
        ch2.set_legend({"none": True})
        ch2.set_size({"width": 560, "height": 260})
        ws.insert_chart(srow2, 3, ch2)


# --------------------------------------------------------------------------
def _sheet_firms(wb, f, b):
    ws = wb.add_worksheet("Firms")
    _write_table(wb, ws, b.firms_public, f, note=(
        "KATMAN B - SENTETIK. Tum firmalar hayali ve anonimdir; firm_id tokenize takma kimliktir. "
        "Gercek firma adi, marka veya vergi kimlik numarasi KULLANILMAMISTIR."))


def _sheet_observations(wb, f, b):
    ws = wb.add_worksheet("Observations")
    df = b.observations
    last = _write_table(wb, ws, df, f, note=(
        "KATMAN B - SENTETIK firma-ceyrek gozlemleri. Bunlar denetciye/sisteme GORUNEN alanlardir. "
        "gekap_rate_status='history_not_priced' olan 2023 satirlarinda parasal GEKAP tutari BILINCLI OLARAK BOSTUR "
        "(2023 tarifesi birincil kaynaktan dogrulanamadi)."))

    cols = list(df.columns)
    # Kosullu bicimlendirme: dusuk veri guveni
    if "data_confidence_level" in cols:
        j = cols.index("data_confidence_level")
        ws.conditional_format(3, j, last, j, {
            "type": "text", "criteria": "containing", "value": "dusuk",
            "format": wb.add_format({"bg_color": "#F8D7DA", "font_color": "#7A1720", "border": 1})})
        ws.conditional_format(3, j, last, j, {
            "type": "text", "criteria": "containing", "value": "yuksek",
            "format": wb.add_format({"bg_color": "#D8EFDC", "font_color": "#14532D", "border": 1})})
    if "data_quality_score" in cols:
        j = cols.index("data_quality_score")
        ws.conditional_format(3, j, last, j, {"type": "3_color_scale",
                                              "min_color": "#F4B6B6", "mid_color": "#FFF0B3", "max_color": "#B7E4C7"})
    if "declared_packaging_tonnage" in cols:
        j = cols.index("declared_packaging_tonnage")
        ws.conditional_format(3, j, last, j, {"type": "data_bar", "bar_color": C_ACCENT})

    # Data validation (kategorik alanlar)
    if "data_confidence_level" in cols:
        j = cols.index("data_confidence_level")
        ws.data_validation(3, j, last, j, {"validate": "list", "source": ["dusuk", "orta", "yuksek"]})
    if "gekap_rate_status" in cols:
        j = cols.index("gekap_rate_status")
        ws.data_validation(3, j, last, j, {"validate": "list",
                                           "source": ["official_verified", "history_not_priced"]})


def _sheet_product_packaging(wb, f, b):
    ws = wb.add_worksheet("Product_Packaging")
    _write_table(wb, ws, b.packaging, f, note=(
        "KATMAN B - SENTETIK urun agaci / ambalaj agirlik matrisi. "
        "GTIP KODU YALNIZCA URUN SINIFLANDIRMA BAGLAMIDIR; ambalaj agirligi GTIP kodundan TURETILMEMISTIR. "
        "Agirliklar SYN-BOM-01 uzman aralik tahmininden log-normal dagilimla cekilmistir "
        "(mu=ln(p50), sigma=(ln(p90)-ln(p10))/(2*1,2816)). Pilotta kurumun GERCEK BOM verisiyle degistirilmelidir."))


def _sheet_model_ready(wb, f, b):
    ws = wb.add_worksheet("Model_Ready")
    _write_table(wb, ws, b.model_ready, f, note=(
        "MODEL GIRDILERI. GROUND TRUTH ICERMEZ. Ozellikler sekiz ayri kanit sinyaliyle eslesecek sekilde "
        "f_s1..f_s8 on ekiyle adlandirilmistir. Hicbir ozellik gelecege bakmaz: gecikmeli degerler firma icinde "
        "zaman sirali, emsal istatistikleri t-1 doneminden hesaplanmistir. "
        "f_avail_s1..f_avail_s8 = ilgili sinyalin bu kayitta KULLANILABILIR olup olmadigi. "
        "Eksik sinyal DUSUK RISK anlamina GELMEZ; veri guven duzeyini dusurur."))


def _sheet_audit_labels(wb, f, b):
    ws = wb.add_worksheet("Audit_Labels")
    df = b.audit_labels
    last = _write_table(wb, ws, df, f, note=(
        "KATMAN C - SENTETIK GROUND TRUTH. EGITIMDE GIRDI OLARAK KULLANILAMAZ; yalnizca hedef degisken ve "
        "degerlendirme icindir. truth_anomaly_flag=1 <=> kayitta GERCEK ve onemlilik esigini asan bir beyan eksigi "
        "MEKANIZMASI vardir. Yalnizca olcum gurultusu nedeniyle dusuk gorunen kayitlar truth=0 kalir - bunlar "
        "bilincli YANLIS-POZITIF uretecleridir."))
    cols = list(df.columns)
    if "truth_anomaly_flag" in cols:
        j = cols.index("truth_anomaly_flag")
        ws.conditional_format(3, j, last, j, {"type": "cell", "criteria": "==", "value": 1,
                                              "format": wb.add_format({"bg_color": "#F8D7DA", "bold": True, "border": 1})})
    if "anomaly_type" in cols:
        j = cols.index("anomaly_type")
        ws.data_validation(3, j, last, j, {"validate": "list", "source": list(ANOMALY_TYPES.keys())})
    if "legitimate_cause" in cols:
        j = cols.index("legitimate_cause")
        ws.data_validation(3, j, last, j, {"validate": "list", "source": [""] + list(LEGITIMATE_CAUSES)})

    # Anomali tipi sozlugu
    r = last + 3
    ws.write(r, 0, "ANOMALI TIPI SOZLUGU", f["subtitle"]); r += 1
    dic = pd.DataFrame([
        {"anomaly_type": k, "truth_anomaly_flag": v["truth"], "aciklama": v["aciklama"]}
        for k, v in ANOMALY_TYPES.items()
    ])
    _write_table(wb, ws, dic, f, start_row=r, autofilter=False, freeze=False)


def _sheet_evaluation(wb, f, b):
    ws = wb.add_worksheet("Evaluation")
    ws.set_column(0, 0, 34)
    r = 0
    ws.write(r, 0, "Degerlendirme protokolu ve REFERANS baseline sonuclari", f["title"]); r += 2
    ws.merge_range(r, 0, r + 2, 7,
                   "Buradaki skorlar GUS-DEDEKTIV MODELI DEGILDIR. Bunlar, datasetin trivial olmadigini gostermek ve "
                   "model asamasinda asilmasi gereken ALT SINIRI tanimlamak icin uretilmis referans baseline'lardir. "
                   "Nihai model (LightGBM quantile + conformal kalibrasyon + 8 sinyal birlesimi) Asama 4 kapsamindadir.",
                   f["banner"]); r += 4

    ws.write(r, 0, "BLOK 1 - Baseline metrikleri (split = test, 2026Q1-2026Q2)", f["subtitle"]); r += 1
    last = _write_table(wb, ws, b.evaluation, f, start_row=r, autofilter=False, freeze=False)
    r = last + 3

    ws.write(r, 0, "BLOK 2 - Zorluk / sizinti probu", f["subtitle"]); r += 1
    d = b.difficulty.T.reset_index()
    d.columns = ["alan", "deger"]
    last = _write_table(wb, ws, d, f, start_row=r, autofilter=False, freeze=False)
    r = last + 3

    ws.write(r, 0, "BLOK 3 - Metrik protokolu (model asamasinda uygulanacak)", f["subtitle"]); r += 1
    proto = pd.DataFrame([
        {"metrik": "Precision@25 / @50 / @100", "amac": "Sinirli denetim kapasitesiyle ilk K dosyada ne kadar isabet",
         "not": "Birincil karar metrigi. K, kurumun gercek denetim kapasitesine gore secilmelidir."},
        {"metrik": "Recall@25 / @50 / @100", "amac": "Ilk K dosyada tum gercek vakalarin ne kadari yakalandi", "not": ""},
        {"metrik": "Lift@K", "amac": "Rastgele secime gore kac kat iyilesme", "not": "Lift = Precision@K / prevalans. "
                                                                                    "Prevalans ve guven araligi VERILMEDEN raporlanamaz."},
        {"metrik": "PR-AUC", "amac": "Dengesiz sinifta genel siralama kalitesi", "not": "Birincil ozet metrik."},
        {"metrik": "ROC-AUC", "amac": "Genel ayirt edicilik", "not": "YALNIZCA EK GOSTERGE. Dengesiz veride yaniltici olabilir."},
        {"metrik": "Tahmin araligi kapsama orani", "amac": "Conformal kalibrasyonun gecerliligi",
         "not": "'%95 kesinlik' veya '%95 garanti' DENMEZ. Dogru ifade: 'belirlenen varsayimlar altinda hedef "
                "kapsama duzeyi ve test verisinde GOZLENEN kapsama orani'."},
        {"metrik": "Tahmin araligi genisligi", "amac": "Belirsizligin operasyonel maliyeti", "not": ""},
        {"metrik": "Yanlis-pozitif / yanlis-negatif sayisi", "amac": "Denetci is yuku ve kacirilan vaka",
         "not": "N10_mesru_gorunum kayitlari uzerinde ayrica olculur."},
        {"metrik": "Audit basina dogrulanmis fark / duzeltilmis tonaj / ek GEKAP", "amac": "Operasyonel getiri",
         "not": "Audit_Labels: confirmed_correction_tonnage ve audit_cost_try uzerinden."},
        {"metrik": "Alt grup sonuclari (sektor, olcek, veri guveni)", "amac": "Yanlilik kontrolu",
         "not": "Mikro olcek ve dusuk veri guveni gruplarinda performans ayrica raporlanmalidir."},
        {"metrik": "Kalibrasyon", "amac": "Skorun olasilikla tutarliligi", "not": "Reliability diagram + Brier."},
        {"metrik": "Ablation testi", "amac": "Her sinyalin gercek katkisi", "not": "Sekiz sinyal tek tek cikarilarak."},
        {"metrik": "Bootstrap guven araligi", "amac": "Sonucun belirsizligi", "not": "Tum Top-K metrikleri icin zorunlu."},
    ])
    last = _write_table(wb, ws, proto, f, start_row=r, autofilter=False, freeze=False)
    r = last + 3

    ws.write(r, 0, "BLOK 4 - Baseline (bl_naive_8signal) ile test siralamasinda ilk 100 kayit", f["subtitle"]); r += 1
    ws.write(r, 0, "REFERANS SIRALAMADIR - GUS-DEDEKTIV skoru degildir. 0-100 olcegi OPERASYONEL INCELEME "
                   "ONCELIGIDIR, suc olasiligi DEGILDIR.", f["warn"]); r += 2

    mr = b.model_ready
    import numpy as _np
    from . import quality as _q
    bl = _q.compute_baseline_scores(mr, _np.random.default_rng(1))
    bl = bl[bl["split"] == "test"].copy()
    lo, hi = bl["bl_naive_8signal"].quantile(0.01), bl["bl_naive_8signal"].quantile(0.99)
    bl["referans_oncelik_0_100"] = ((bl["bl_naive_8signal"] - lo) / max(hi - lo, 1e-9) * 100).clip(0, 100).round(1)
    top = bl.sort_values("referans_oncelik_0_100", ascending=False).head(100)
    top = top.merge(b.audit_labels[["observation_id", "truth_anomaly_flag", "anomaly_type",
                                    "audit_outcome", "confirmed_correction_tonnage"]],
                    on="observation_id", how="left")
    top = top[["observation_id", "firm_id", "period", "referans_oncelik_0_100",
               "truth_anomaly_flag", "anomaly_type", "audit_outcome", "confirmed_correction_tonnage"]]
    top.insert(0, "sira", range(1, len(top) + 1))
    last = _write_table(wb, ws, top.reset_index(drop=True), f, start_row=r, freeze=False)

    cols = list(top.columns)
    j = cols.index("referans_oncelik_0_100")
    ws.conditional_format(r + 1, j, last, j, {"type": "3_color_scale",
                                              "min_color": "#B7E4C7", "mid_color": "#FFE08A", "max_color": "#F4978E"})
    j2 = cols.index("truth_anomaly_flag")
    ws.conditional_format(r + 1, j2, last, j2, {"type": "cell", "criteria": "==", "value": 1,
                                                "format": wb.add_format({"bg_color": "#F8D7DA", "bold": True, "border": 1})})


def _sheet_gekap_rates(wb, f, b):
    ws = wb.add_worksheet("GEKAP_Rates")
    df = b.reference.gekap_rates.drop(columns=["tutar_tl_num"], errors="ignore")
    last = _write_table(wb, ws, df, f, note=(
        "KATMAN A - OFFICIAL_OPEN. 2026 ve 2025 tutarlari Resmi Gazete teblig metninden BIREBIR dogrulanmistir. "
        "2024 tutarlari ikincil kaynaktan alinmis ve yeniden degerleme orani zinciri ile capraz dogrulanmistir. "
        "2023 tutarlari bu calismada DOGRULANAMAMISTIR (yil ortasinda Cumhurbaskani Karari ile degistigi icin) ve "
        "datasette KULLANILMAMISTIR. DIKKAT: Ahsap ambalaj tarifesi ADET bazlidir, kg bazli DEGILDIR."))
    # Yeniden degerleme dogrulamasi - FORMULLE
    r = last + 3
    ws.write(r, 0, "TARIFE ZINCIRI DOGRULAMASI (formulle hesaplanir)", f["subtitle"]); r += 1
    hdr = ["Malzeme (kg bazli)", "2024 (kr)", "2025 (kr)", "2026 (kr)",
           "2025 beklenen = 2024 x 1,4393", "2026 beklenen = 2025 x 1,2549", "Sapma %5 kesir kurali icinde mi"]
    for j, h in enumerate(hdr):
        ws.write(r, j, h, f["h"])
    ws.set_column(0, 0, 26); ws.set_column(1, 6, 26)
    vals = {"plastik": (400, 570, 700), "metal": (470, 670, 800), "kompozit": (470, 670, 800),
            "kagit_karton": (190, 270, 330), "cam": (190, 270, 330)}
    i = 0
    for mat, (v24, v25, v26) in vals.items():
        rr = r + 1 + i
        ws.write_string(rr, 0, mat, f["txt"])
        ws.write_number(rr, 1, v24, f["num2"]); ws.write_number(rr, 2, v25, f["num2"]); ws.write_number(rr, 3, v26, f["num2"])
        ws.write_formula(rr, 4, f"=B{rr+1}*1.4393", f["num2"])
        ws.write_formula(rr, 5, f"=C{rr+1}*1.2549", f["num2"])
        ws.write_formula(rr, 6, f'=IF(AND((E{rr+1}-C{rr+1})<=0.05*E{rr+1},(F{rr+1}-D{rr+1})<=0.05*F{rr+1}),"EVET","HAYIR")', f["txt"])
        i += 1
    ws.write(r + i + 2, 0,
             "2872 sayili Kanun ek 11: tutarlar her yil yeniden degerleme oraninda artirilir ve "
             "hesaplanan tutarlarin %5'ini asmayan kesirler dikkate alinmaz. Yukaridaki kolon bu kurali dogrular.",
             f["txt_nb"])


def _sheet_macro(wb, f, b):
    ws = wb.add_worksheet("Macro_Anchors")
    _write_table(wb, ws, b.reference.macro_anchors, f, note=(
        "KATMAN A - OFFICIAL_OPEN. 'TO_BE_FILLED' isaretli satirlar BILINCLI OLARAK BOS BIRAKILMISTIR: "
        "TUIK Sanayi Uretim Endeksi ve Dis Ticaret serileri bu calismada sayisal olarak cekilememistir. "
        "Veri BULUNMUS GIBI GOSTERILMEMISTIR. Dataset bu seriler yerine dokumante edilmis sentetik trend ve "
        "mevsimsellik kullanmaktadir (bkz. Methodology)."))


def _sheet_climate(wb, f, b):
    ws = wb.add_worksheet("Climate_Factors")
    df = b.reference.climate_factors.drop(columns=["faktor_metrik_ton_num"], errors="ignore")
    last = _write_table(wb, ws, df, f, note=(
        "KATMAN A (yabanci kaynak) + DERIVED. Butun satirlar 'Potential scenario - not verified impact' etiketlidir. "
        "Faktorler US EPA WARM v16 Exhibit 2-2'den alinmistir ve ABD OZGUDUR; Turkiye'ye ozgu faktor mevcut degildir. "
        "Birim KISA TONDUR ve 0,907185 ile metrik tona cevrilmistir."))
    r = last + 3
    ws.write(r, 0, "SENARYO HESAPLARI (test donemi, sentetik)", f["subtitle"]); r += 1
    _write_table(wb, ws, b.climate_scenarios, f, start_row=r, autofilter=False, freeze=False)


def _sheet_sources(wb, f, b):
    ws = wb.add_worksheet("Source_Registry")
    _write_table(wb, ws, b.reference.sources, f, note=(
        "BUTUN KAYNAKLAR VE DOGRUDAN LINKLER. birincil_ikincil sutunu kaynagin birincil mi ikincil mi oldugunu; "
        "dogrulama_durumu sutunu verinin bu calismada nasil teyit edildigini gosterir. "
        "'ALINAMADI' veya 'KISMI' isaretli satirlar, resmi teyit istenmesi gereken ACIK MADDELERDIR."))


def _sheet_data_dictionary(wb, f, b):
    rows: List[Dict] = []

    desc = {
        "observation_id": ("Firma-donem birincil anahtari (firm_id + period)", "derived"),
        "firm_id": ("Tokenize edilmis sentetik firma kimligi", "synthetic"),
        "period": ("Beyan donemi (yil + ceyrek). GEKAP beyani uc aylik donemler halinde verilir.", "synthetic"),
        "split": ("history / train / valid / test - zamansal bolunme", "derived"),
        "sector": ("BEYAN EDILEN sektor. sector_code_error_flag=TRUE olan firmalarda gercek sektorden farklidir.", "synthetic"),
        "size_band": ("Calisan sayisi bandi (mikro/kucuk/orta/buyuk). Resmi KOBI ciro esikleri KULLANILMAMISTIR.", "synthetic"),
        "production_qty": ("Ceyreklik uretim/piyasaya arz gostergesi (sentetik urun adedi)", "synthetic"),
        "import_qty": ("Ceyreklik ithalat miktari", "synthetic"),
        "export_qty": ("Ceyreklik ihracat miktari. Ihrac edilen urunlerin ambalaji GEKAP kapsami DISINDADIR (SRC-012).", "synthetic"),
        "return_qty": ("Iade miktari", "synthetic"),
        "correction_qty": ("Onceki donemden tasinan duzeltme tonaji (gec duzeltme beyannamesi)", "synthetic"),
        "exemption_flag": ("Yasal muafiyet/istisna var mi", "synthetic"),
        "domestic_supply_qty_derived": ("Yurt ici piyasaya arz = uretim + ithalat - ihracat - iade", "derived"),
        "declared_packaging_tonnage": ("BEYAN EDILEN toplam ambalaj tonaji (ton)", "synthetic"),
        "bom_expected_tonnage_observable": ("Sistemde KAYITLI urun agacindan hesaplanan beklenen tonaj. "
                                            "Yalnizca BOM kapsami olan kismi gorur; gercek tonajin tamami DEGILDIR.", "derived"),
        "bom_coverage_ratio": ("Firmanin urun agacinin sisteme tanimli olma orani", "synthetic"),
        "weight_matrix_vintage_year": ("Ambalaj agirlik matrisinin surum yili. Eski matris sistematik sapma yaratir.", "synthetic"),
        "external_evidence_tonnage": ("ERP / onceki denetim kaydindan gelen bagimsiz tonaj olcumu", "synthetic"),
        "gekap_rate_status": ("official_verified = tarifesi birincil/ikincil kaynaktan dogrulanmis yil; "
                              "history_not_priced = 2023, tarife dogrulanamadigi icin parasal tutar HESAPLANMAMISTIR", "derived"),
        "gekap_amount_try": ("Beyan tonaji x donemin GEKAP tarifesi. Ahsap DAHIL DEGILDIR (tarifesi adet bazlidir).", "derived"),
        "data_quality_score": ("0-1 veri kalitesi puani (eksik alan sayisi, BOM kapsami, tazelik)", "derived"),
        "data_confidence_level": ("dusuk / orta / yuksek. EKSIK VERI DUSUK RISK ANLAMINA GELMEZ.", "derived"),
        "truth_anomaly_flag": ("1 = kayitta GERCEK ve onemlilik esigini asan beyan eksigi mekanizmasi vardir", "synthetic_label"),
        "anomaly_type": ("Anomali/negatif mekanizma tipi (A01-A08 = gercek eksiklik, N09/N10/N00 = eksiklik yok)", "synthetic_label"),
        "true_expected_tonnage": ("LATENT gercek beklenen tonaj. Modele GIRDI OLARAK VERILEMEZ.", "synthetic_label"),
        "confirmed_correction_tonnage": ("Denetimde DOGRULANABILEN duzeltme tonaji (gercek acigin tamami degil)", "synthetic_label"),
        "audit_outcome": ("dogrulandi_eksik_beyan / kismi_dogrulandi / aciklandi_uygun / veri_incelemesi_gerekli / bulgu_yok", "synthetic_label"),
        "label_confidence": ("Etiketin guvenilirligi. Gercek denetim kayitlarinda da hata olur.", "synthetic_label"),
    }
    signal_map = {
        "f_s1": "S1 - Tarihsel alt sinir ihlali",
        "f_s2": "S2 - Emsal alt sinir ihlali",
        "f_s3": "S3 - Beklenen ile gerceklesen ambalaj tonaji farki",
        "f_s4": "S4 - Faaliyet esnekligi uyumsuzlugu",
        "f_s5": "S5 - Dis ticaret ve duzeltme dengesi",
        "f_s6": "S6 - Donemsel davranis kirilmasi",
        "f_s7": "S7 - Urun agaci ve ambalaj matrisi uyumsuzlugu",
        "f_s8": "S8 - Dis dogrulama kaniti",
        "f_avail": "Sinyal kullanilabilirligi",
    }

    tables = [
        ("Firms", b.firms_public), ("Observations", b.observations),
        ("Product_Packaging", b.packaging), ("Model_Ready", b.model_ready),
        ("Audit_Labels", b.audit_labels),
    ]
    for tname, df in tables:
        for c in df.columns:
            d, cls = desc.get(c, ("", ""))
            if not cls:
                if tname == "Audit_Labels":
                    cls = "synthetic_label"
                elif c.startswith("f_"):
                    cls = "derived"
                elif c in ("data_source_type", "generation_method", "source_ids", "is_synthetic"):
                    cls = "provenance"
                else:
                    cls = "synthetic"
            sig = ""
            for k, v in signal_map.items():
                if c.startswith(k):
                    sig = v
                    break
            rows.append({
                "sayfa": tname, "sutun": c,
                "veri_tipi": str(df[c].dtype),
                "veri_sinifi": cls,
                "ilgili_sinyal": sig,
                "aciklama": d or ("Sekiz sinyal ozelligi - bkz. Methodology" if c.startswith("f_") else ""),
                "bos_oran": round(float(df[c].isna().mean()), 4),
                "essiz_deger": int(df[c].nunique(dropna=True)),
            })
    ws = wb.add_worksheet("Data_Dictionary")
    _write_table(wb, ws, pd.DataFrame(rows), f, note=(
        "veri_sinifi: official_open = gercek acik veri | synthetic = sentetik | derived = turetilmis | "
        "synthetic_label = sentetik ground truth (EGITIM GIRDISI OLAMAZ) | provenance = koken bilgisi"))


def _sheet_methodology(wb, f, b):
    ws = wb.add_worksheet("Methodology")
    ws.set_column(0, 0, 40); ws.set_column(1, 1, 118)
    ws.hide_gridlines(2)
    r = 0
    ws.write(r, 0, "Sentetik veri uretim metodolojisi", f["title"]); r += 2

    blocks = [
        ("1. Determinizm",
         f"Kok seed = {b.manifest['seed']}. Her alt asama (firms, packaging, latent, anomalies, observed, labels, "
         "baseline) SHA-256 ile kokten turetilmis BAGIMSIZ bir akis kullanir. Ayni seed + ayni config = ayni dataset. "
         "Uretim komutu: python src/generate_dataset.py --seed 20260902 --firms 600"),
        ("2. Donguselligin engellenmesi",
         "Anomali URETICI (anomalies.py) LATENT buyuklukler uzerinde calisir; dedektor ise yalnizca GOZLENEN "
         "alanlari gorur ve latent beklentiyi CIKARSAMAK zorundadir. features.py, anomalies modulunu ITHAL ETMEZ ve "
         "bu kural validate_dataset.py tarafindan otomatik dogrulanir. Ureticinin kurallari ile dedektorun sinyal "
         "kurallari ozdes DEGILDIR."),
        ("3. Zamansal ayrisma",
         "history(2023) -> train(2024Q1-2025Q2) -> valid(2025Q3-2025Q4) -> test(2026Q1-2026Q2). Test donemi zamansal "
         "holdout'tur. A08 (dis kanit uyumsuzlugu) mekanizmasi egitimde NADIR, testte DAHA SIK uretilir; "
         "boylece kavramsal kayma (concept drift) dayanikliligi olculebilir."),
        ("4. Uretim ve mevsimsellik",
         "production = olcek x (1+trend)^(t/4) x [1 + genlik*cos(2*pi*(q-faz)/4)] x seviye x exp(AR(1) sok). "
         "AR(1): rho=0,55, sigma=0,10. Firmalarin %9'unda rastgele bir ceyrekte yapisal kirilma (x0,55-0,80 veya "
         "x1,25-1,55) uygulanir. Sektor trend ve mevsim parametreleri config.SECTORS icinde acikca tanimlidir."),
        ("5. Olcek dagilimi",
         "Ceyreklik uretim olcegi log-normaldir: mikro mu=9,2 s=0,55 | kucuk mu=10,6 s=0,50 | orta mu=12,0 s=0,45 | "
         "buyuk mu=13,4 s=0,42. Bant paylari: 0,34 / 0,36 / 0,22 / 0,08."),
        ("6. Dis ticaret",
         "ihracat_payi ~ Beta(sektore ozgu), ceyreklik sigma=0,035 gurultu ve %3 olasilikla +/-0,10-0,30 siçrama. "
         "ithalat = uretim x Beta(sektore ozgu) x exp(N(0;0,18)). iade ~ Beta(1,2;60). "
         "Muafiyet: %5 olasilik, muaf pay 0,08-0,35."),
        ("7. Ambalaj agirlik matrisi (SYN-BOM-01)",
         "Her SKU icin birim agirlik log-normal cekilir: mu=ln(p50), sigma=(ln(p90)-ln(p10))/(2 x 1,2816). "
         "p10/p50/p90 araliklari sektor bilgisi ve kamuya acik urun olculerinden derlenmis UZMAN TAHMINIDIR; "
         "tek bir birincil kaynaga dayanmaz. GTIP kodu yalnizca urun siniflandirma baglamidir ve agirlik "
         "TURETIMINDE KULLANILMAZ. Firmalarin %18'inde matris eskimistir ve gercek agirligi %6-22 fazla gosterir."),
        ("8. Gercek ambalaj tonaji (latent)",
         "true_tonnage = yurt_ici_vergilenebilir_arz x SUM(sku_payi x gercek_birim_agirlik) / 1.000.000. "
         "Sisteme kayitli beklenti ise KAYITLI agirlikla ve yalnizca BOM kapsami kadar hesaplanir; "
         "bu bilincli bilgi acigi modelin isini gercekci sekilde zorlastirir."),
        ("9. Beyan uretimi",
         "declared = true_tonnage x (1 - eksiklik) x exp(N(-sigma^2/2; sigma)). sigma bant bazlidir "
         "(mikro 0,150 | kucuk 0,115 | orta 0,085 | buyuk 0,062); 'ozensiz' firmalarda x1,45. "
         "Gurultu ORTALAMASI 1 olacak sekilde merkezlenmistir."),
        ("10. Anomali (Katman C)",
         "Firma bazli egilim: uyumlu 0,020 | ozensiz 0,055 | gec_duzeltici 0,045 | sistematik_eksik 0,310. "
         "Onceki donem anomaliyse olasilik x2,4 (kaliciligi yansitir). Eksiklik siddeti: "
         "0,05 + 0,50 x Beta(1,6;2,6) -> zayif anomaliler daha siktir ve gurultuyle ORTUSUR. "
         "ONEMLILIK ESIGI: aciklik >= max(0,30 ton; %3 x true_tonnage). Esigi asmayan niyet denetimde "
         "dogrulanmaz ve truth=0 kalir."),
        ("11. Yanlis-pozitif ureteci (N10)",
         "Kayit truth=0 iken hem MESRU BIR NEDEN tasiyor hem de firmanin son 4 donem ortalamasinin %82'sinin "
         "altina dusmusse N10_mesru_gorunum atanir. Nedenler: ihracat agirlikli donem, yasal muafiyet, "
         "gec duzeltme beyannamesi, mevsimsel uretim duraklamasi, yeni firma/kisa tarihce, sektor kodu hatasi, "
         "eskimis ambalaj agirlik matrisi, urun gami degisikligi."),
        ("12. Eksik veri mekanizmasi (MAR)",
         "Eksiklik olasiligi firmanin veri olgunluguna baglidir (buyuk firmalar daha az eksik). "
         "Ithalat/ihracat temel oran 0,12; uretim 0,05; dis dogrulama kaydi bulunma orani 0,18. "
         "Kritik alanlari eksik olan truth=0 kayitlarin %62'si N09_veri_eksikligi kuyruguna alinir. "
         "EKSIK VERI DUSUK RISK OLARAK DEGERLENDIRILMEZ."),
        ("13. Etiket gurultusu",
         "Kayitlarin %3'unde etiket ters cevrilir ve label_confidence='dusuk' yapilir. Gercek denetim "
         "kayitlarinda da hata bulunur; mukemmel etiket varsayimi gercekci degildir."),
        ("14. Kullanilmayan/doldurulmayan veriler",
         "TUIK Sanayi Uretim Endeksi ve Dis Ticaret serileri sayisal olarak cekilememistir (Macro_Anchors: "
         "TO_BE_FILLED). Ambalaj Atiklarinin Kontrolu Yonetmeligi ek tablolari PDF'ten cikarilamamistir. "
         "2023 GEKAP tarifeleri dogrulanamamistir. Bu veriler BULUNMUS GIBI GOSTERILMEMISTIR."),
        ("15. Bilinen sinirliliklar",
         "(a) Sentetik performans gercek kamu performansi degildir. "
         "(b) Ambalaj agirlik araliklari uzman tahminidir. "
         "(c) Emsal gruplama sektor x olcek bandidir; gercekte urun grubu ve cografya da gerekir. "
         "(d) Malzeme paylari resmi ATIK BEYAN evreniyle birebir ortusmez - iki evren farklidir. "
         "(e) Ahsap ambalaj tarifesi ADET bazli oldugu icin parasal hesaba dahil edilmemistir. "
         "(f) Plastik poset (satis noktasi yukumlulugu) bu datasette modellenmemistir."),
    ]
    for k, v in blocks:
        ws.write(r, 0, k, f["subtitle"]); ws.write(r, 1, v, f["txt_nb"])
        ws.set_row(r, max(16, 13 * (len(v) // 110 + 1)))
        r += 1


def _sheet_gov_map(wb, f, b):
    ws = wb.add_worksheet("Government_Integration_Map")
    rows = [
        ("firm_id", "Vergi Kimlik No / MERSIS", "Gelir Idaresi Baskanligi",
         "Kurum ici kimlik eslemesi. Sistemde YALNIZCA tokenize kimlik tutulur; gercek VKN kurum sinirlari icinde kalir.",
         "KVKK - veri minimizasyonu, amacla sinirli kullanim", "Yuksek"),
        ("declared_packaging_tonnage, declared_ton_*", "GEKAP Beyannamesi ambalaj tablolari",
         "Gelir Idaresi Baskanligi (e-Beyanname)",
         "Dogrudan beyan verisi. Sistemin ANA GIRDISIDIR. Uc aylik donemler halinde alinir.",
         "GEKAP Beyannamesi Genel Tebligi (Sira No 1) - SRC-013", "Kritik"),
        ("correction_qty", "Duzeltme beyannamesi kayitlari", "Gelir Idaresi Baskanligi",
         "Gec duzeltmelerin yanlis-pozitif uretmesini engeller.", "Ayni teblig", "Yuksek"),
        ("bom_expected_tonnage_observable, Product_Packaging", "Ambalaj Bilgi Sistemi / firma urun agaci beyanlari",
         "Cevre Sehircilik ve Iklim Degisikligi Bakanligi",
         "Sentetik SYN-BOM-01 matrisinin YERINI ALIR. Projenin en kritik veri ihtiyacidir.",
         "Ambalaj Atiklarinin Kontrolu Yonetmeligi - SRC-015", "Kritik"),
        ("production_qty", "Sanayi uretim/kapasite kayitlari veya Yillik Sanayi ve Hizmet Istatistikleri",
         "TUIK / Sanayi ve Teknoloji Bakanligi",
         "Faaliyet esnekligi sinyalinin (S4) temelidir.", "Resmi istatistik mevzuati - SRC-016", "Kritik"),
        ("import_qty, export_qty", "GTIP bazli dis ticaret ve gumruk beyannameleri", "Ticaret Bakanligi / TUIK",
         "Ihrac edilen urunlerin ambalaji GEKAP disinda oldugu icin S5 sinyalinin dogrulugu buna baglidir.",
         "Gumruk mevzuati - SRC-017", "Kritik"),
        ("exemption_flag, exempt_share", "Muafiyet/istisna ve ihrac kayitli teslim kayitlari",
         "Gelir Idaresi Baskanligi / Ticaret Bakanligi",
         "Mesru dusuk beyanlarin yanlis-pozitif uretmesini engeller.", "SRC-012", "Yuksek"),
        ("external_evidence_tonnage", "Onceki denetim raporlari, saha inceleme kayitlari, ERP mutabakatlari",
         "Cevre Sehircilik ve Iklim Degisikligi Bakanligi il mudurlukleri",
         "S8 dis dogrulama sinyali. Kapsami dusuk oldugu icin eksikligi ozellikle modellenmistir.",
         "Cevre Kanunu denetim yetkisi", "Orta"),
        ("sector, nace_code, size_band", "NACE kodu ve olcek bilgisi", "TUIK / Ticaret Sicil / SGK",
         "Emsal gruplamanin (S2) dogrulugu icin zorunludur. Yanlis sektor kodu yanlis-pozitif uretir.",
         "Resmi istatistik mevzuati", "Yuksek"),
        ("Geri kazanim ve atik akisi", "Sifir Atik Bilgi Sistemi, Atik Beyan Sistemi (TABS), MoTAT",
         "Cevre Sehircilik ve Iklim Degisikligi Bakanligi",
         "COP31 panelindeki senaryo metriklerinin GERCEK verilerle degistirilmesini saglar.",
         "Sifir Atik Yonetmeligi", "Orta"),
        ("GEKAP tarifeleri", "Yillik GEKAP teblig tutarlari", "Cevre Sehircilik ve Iklim Degisikligi Bakanligi",
         "Zaten kamuya aciktir; sistemde GEKAP_Rates sayfasindan otomatik guncellenebilir.",
         "2872 sayili Kanun ek 11 - SRC-001/002/003", "Hazir"),
        ("Karar kaydi, itiraz izi", "Kurum denetim is akisi ve karar kayit sistemi", "Ilgili kamu kurumu",
         "Her skor icin karar kimligi, model surumu, veri surumu ve denetci onayi kaydedilir. "
         "Model tek basina ceza veya olumsuz idari karar URETEMEZ.",
         "Idari usul + KVKK otomatik karar hukumleri", "Kritik"),
    ]
    df = pd.DataFrame(rows, columns=[
        "Dataset alani", "Devletin gercek veri kaynagi", "Veri sahibi kurum",
        "Entegrasyon notu", "Hukuki dayanak / mevzuat", "Kritiklik"])
    last = _write_table(wb, ws, df, f, note=(
        "BU HARITA, devletin KENDI VERISINI sisteme nasil baglayacagini gosterir. Sentetik alanlar pilotta "
        "karsilik gelen resmi kaynakla DEGISTIRILIR; sistem mimarisi ve sinyal mantigi degismez. "
        "GUS-DEDEKTIV veri TOPLAMAZ; kurumun kendi verisini kurumun kendi ortaminda degerlendirir."))
    ws.data_validation(3, 5, last, 5, {"validate": "list", "source": ["Kritik", "Yuksek", "Orta", "Hazir"]})
    ws.conditional_format(3, 5, last, 5, {"type": "text", "criteria": "containing", "value": "Kritik",
                                          "format": wb.add_format({"bg_color": "#F8D7DA", "bold": True, "border": 1})})


def _sheet_quality(wb, f, b):
    ws = wb.add_worksheet("Quality_Checks")
    df = b.quality_checks
    last = _write_table(wb, ws, df, f, note=(
        "Otomatik kalite, mantik, sizinti ve gercekcilik kontrolleri. "
        "'KALDI' durumundaki her satir dataset yayinlanmadan once cozulmelidir."))
    cols = list(df.columns)
    j = cols.index("durum")
    ws.conditional_format(3, j, last, j, {"type": "text", "criteria": "containing", "value": "KALDI",
                                          "format": wb.add_format({"bg_color": "#F8D7DA", "font_color": "#7A1720", "bold": True, "border": 1})})
    ws.conditional_format(3, j, last, j, {"type": "text", "criteria": "containing", "value": "GECTI",
                                          "format": wb.add_format({"bg_color": "#D8EFDC", "font_color": "#14532D", "border": 1})})
    ws.conditional_format(3, j, last, j, {"type": "text", "criteria": "containing", "value": "UYARI",
                                          "format": wb.add_format({"bg_color": "#FFF3CD", "font_color": "#7A5B00", "border": 1})})
