# GÜS-DEDEKTİV — Veri Altyapısı

**GEKAP Beyan Tutarlılığı, Denetim Önceliklendirme ve İklim Etki Platformu**
Takım: **KinetiX** · TEKNOFEST 2026 Sıfır Atık ve Döngüsel Ekonomi

---

## ⚠️ Önce bu

Bu depodaki firma kayıtları, beyanlar ve denetim sonuçları **tamamen sentetiktir**.
Hiçbir gerçek firmayı, gerçek GEKAP beyanını veya gerçek denetim sonucunu temsil etmez.
Bu veri üzerinde ölçülen model performansı **gerçek kamu performansı olarak sunulamaz**.

Buna karşılık; GEKAP tarifeleri, ambalaj atığı istatistikleri, geri kazanım oranları,
iklim faktörleri ve COP31 bilgileri **gerçek, kaynağı belirtilmiş açık verilerdir**
(bkz. `data/reference/source_registry.csv` ve Excel'deki `Source_Registry` sayfası).

---

## Ne işe yarar

GÜS-DEDEKTİV, kamu denetçisine **hangi firma-dönem GEKAP beyanının önce incelenmesi
gerektiğini gerekçesiyle** gösteren bir karar destek sistemidir. Bu depo, o sistemin
geliştirilebilmesi ve **dürüstçe değerlendirilebilmesi** için gereken veri altyapısını üretir.

Sistem: firma adına beyanname hazırlamaz · muhasebe programı değildir · firmayı suçlu
ilan etmez · otomatik ceza kararı vermez · denetçinin yerini almaz.
**0–100 puan operasyonel inceleme önceliğidir; suç olasılığı değildir.**

---

## Kurulum

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Linux/macOS için: `source .venv/bin/activate && pip install -r requirements.txt`

## Dataset üretimi

```bash
python src/generate_dataset.py --seed 20260902 --firms 600
```

Çıktılar `data/output/` altına yazılır:

| Çıktı | Açıklama |
|---|---|
| `GUS-DEDEKTIV_Dataset_v1.0.xlsx` | 16 sayfalık ana teslim dosyası |
| `csv/*.csv` | Tüm tablolar (UTF-8-BOM, `;` ayraçlı) |
| `parquet/*.parquet` | Model eğitimi için sütunlu format |
| `manifest.json` | Sürüm, seed, config ve özet istatistikler |

Ölçek `--firms` ile değiştirilebilir (300–2500 önerilir). **Aynı seed + aynı config = aynı dataset.**

## Doğrulama

```bash
python src/validate_dataset.py --firms 600
```

38 kontrol çalışır: referans veri bütünlüğü, GEKAP tarife zinciri (yeniden değerleme + %5
kesir kuralı), mimari sızıntı koruması, sütun/korelasyon sızıntısı, ileriye bakış olmaması,
iş kuralları, prevalans, dataset'in trivial olmaması ve determinizm.

---

## Dizin yapısı

```
data/reference/     Katman A — gerçek açık veriler (kaynaklı, elle bakımlı)
  source_registry.csv        19 kaynak, doğrudan URL + erişim tarihi + sınırlamalar
  gekap_rates.csv            2024/2025/2026 GEKAP tarifeleri (2023 bilinçli olarak YOK)
  macro_anchors.csv          TÜİK/ÇŞİDB makro çıpaları
  climate_factors.csv        EPA WARM v16 faktörleri + senaryo varsayımları
  packaging_weight_ranges.csv  SYN-BOM-01 ambalaj ağırlık aralıkları (sentetik)

src/gus_generator/  Üretici paket
  config.py           Tüm parametreler (tek doğruluk kaynağı)
  reference_data.py   Katman A yükleyici
  entities.py         Katman B — firmalar + SKU/ürün ağacı
  observations.py     Katman B — latent panel + gözlenen tablo
  anomalies.py        Katman C — ground truth (AYRI modül, dedektörden bağımsız)
  features.py         Model_Ready (anomalies'i İTHAL ETMEZ)
  quality.py          Kalite kontrolleri + referans baseline'lar
  pipeline.py         Uçtan uca orkestrasyon + COP31/iklim senaryoları
  excel_builder.py    16 sayfalık .xlsx

src/generate_dataset.py   Üretim komutu
src/validate_dataset.py   Bağımsız doğrulama
docs/ARCHITECTURE.md      Sistem mimarisi ve teknoloji gerekçeleri
```

---

## Üç veri katmanı

| Katman | İşaret | İçerik |
|---|---|---|
| **A** | `official_open` | Gerçek açık veriler. Resmî Gazete GEKAP tebliğleri, ÇŞİDB atık istatistikleri, EPA WARM, COP31. |
| **B** | `synthetic` | Gerçek verilerden kalibre edilmiş sentetik firma ve firma-çeyrek verisi. |
| **C** | `synthetic_label` | Sentetik audit ground-truth. Model girdilerinden **ayrı sayfada** tutulur. |
| — | `derived` | Yukarıdakilerden formülle türetilmiş alanlar. |

## Temel tasarım kararları

**Analiz birimi firma-çeyrek** — firma-yıl değil. GEKAP beyanı üç aylık dönemler halinde verilir.

**Döngüsellik koruması** — Anomali üretici latent büyüklükler üzerinde çalışır; dedektör
yalnızca gözlenen alanları görür ve latent beklentiyi çıkarsamak zorundadır. `features.py`,
`anomalies.py`'yi ithal etmez; bu kural AST analiziyle otomatik doğrulanır.

**Zamansal holdout** — `history` (2023) → `train` (2024Q1–2025Q2) → `valid` (2025Q3–2025Q4)
→ `test` (2026Q1–2026Q2). `A08_dis_kanit_uyumsuz` mekanizması eğitimde nadir, testte sık
üretilir; kavramsal kayma dayanıklılığı ölçülebilir.

**Doğrulanamayan veri uydurulmaz** — 2023 GEKAP tarifeleri birincil kaynaktan
doğrulanamadığı için o dönemde parasal tutar **hesaplanmaz** (`gekap_rate_status =
history_not_priced`). TÜİK Sanayi Üretim Endeksi serileri çekilemediği için
`Macro_Anchors` içinde `TO_BE_FILLED` olarak işaretlidir.

**Eksik veri düşük risk değildir** — Kritik alanları eksik kayıtlar `N09_veri_eksikligi`
kuyruğuna gider, veri güven düzeyi düşürülür, otomatik "temiz" sayılmaz.

**Dataset trivial değil** — Genel amaçlı bir GBM zamansal holdout'ta
`Precision@100 ≈ 0,25`, `Lift@100 ≈ 3,1`, `ROC-AUC ≈ 0,67` alır. Normal ve anomali
dağılımları bilinçli olarak örtüştürülmüştür; Top-100 otomatik %100 çıkmaz.

**GTİP ≠ ambalaj ağırlığı** — GTİP kodu yalnızca ürün sınıflandırma bağlamı sağlar.
Ambalaj ağırlığı ayrı bir sentetik ağırlık matrisinden (SYN-BOM-01) log-normal dağılımla çekilir.

---

## COP31

`COP31_Dashboard` sayfası iki bloğu **kesin olarak ayırır**:

- **Doğrulanabilir metrikler** — analiz edilen firma/beyan sayısı, önceliklendirilen dosya,
  doğrulanmış düzeltme tonajı, malzeme kırılımı, hesaplanan GEKAP tutarı, inceleme süresi.
- **Senaryo metrikleri** — potansiyel geri kazanım tonajı ve potansiyel CO₂e; her biri
  `Potential scenario - not verified impact` etiketli, faktör kaynağı/yılı/coğrafi kapsamı/
  sistem sınırı/dönüşüm formülü/varsayımı/belirsizliği ile birlikte.

COP31 ile **resmî ortaklık yoktur**, logo kullanılmamıştır. COP31 atık hedefleri
**başkanlık gündemi** niteliğindedir; müzakere edilmiş bağlayıcı karar değildir.
Beyan düzeltmesi **fiziksel geri dönüşüm değildir**.

---

## Lisans ve kaynak kullanımı

Kod: proje ekibi tarafından üretilmiştir. Bağımlılık lisansları: pandas/numpy/scipy (BSD-3),
XlsxWriter (BSD-2), openpyxl (MIT), pyarrow (Apache-2.0), scikit-learn (BSD-3).
Katman A kaynaklarının lisans/kullanım koşulları `source_registry.csv` içinde satır bazında kayıtlıdır.
