# GÜS-DEDEKTİV — Sistem Mimarisi ve Teknoloji Planı

**Sürüm:** 1.0 (onay bekliyor) · **Tarih:** 2026-09-02 · **Takım:** KinetiX
**Kapsam:** Bu doküman, geliştirmeye başlamadan önce onaylanması istenen mimari ve teknoloji seçimlerini içerir.

---

## 0. Bu dokümanın ön değerlendirme puanlarıyla ilişkisi

| Ön değerlendirme başlığı | Puan | Bu dokümandaki karşılığı |
|---|---|---|
| Kullanılacak Teknolojiler | **0,00 / 5** | §4 — her teknoloji için 9 soruluk tam eşleştirme tablosu |
| Teknik Mimari | 7,50 / 8 | §2, §3, §6 — katman diyagramı, veri modeli, API sözleşmesi |
| Projenin Geliştirme Seviyesi | 7,00 / 8 | §7 — MVP / pilot / üretim ayrımı ve olgunluk seviyeleri |
| Gerçek Hayat Uygulaması | 7,00 / 8 | §5 — denetçi iş akışı ve ekranlar; §8 — devlet entegrasyon haritası |
| Beklenen Etki | 7,00 / 8 | §9 — COP31 modülü, doğrulanabilir/senaryo ayrımı |

### 4. bölüm neden bu kadar detaylı?

Raporda teknoloji **isimleri** vardı ama puan 0 geldi. Bunun tek başına bir değerlendirici hatası
olduğunu varsaymak risklidir. Muhtemel nedenler ve aldığımız önlem:

| Olası neden | Önlem |
|---|---|
| Teknoloji listesi var ama **hangi işlevi** karşıladığı yazılmamış | §4'te her satırda "Hangi işlev" sütunu |
| **Neden bu teknoloji** ve alternatifi belirtilmemiş | "Neden / Alternatif" sütunları |
| **Sürüm ve lisans** verilmemiş | "Sürüm / Lisans" sütunları |
| Teknolojiler **mimarideki yere** bağlanmamış | §2 katman diyagramı + §4'te "Katman" sütunu |
| **Performans testi** ve kamu kurulumu anlatılmamış | "Nasıl test edilir / Kamu kurulumu" sütunları |
| MVP ile üretim **karıştırılmış** (ör. SQLite ulusal ölçek gibi sunulmuş) | §7'de açık ayrım; SQLite yalnızca MVP |
| Bölüm rapor içinde **dağınık** yer almış, tek başlık altında toplanmamış | Tek tablo, tek başlık |

> **Not:** Bu bir varsayımdır. Değerlendirme gerekçesi bize yazılı olarak bildirilmediyse,
> organizasyondan gerekçe talep edilmesi ayrıca önerilir (§11).

---

## 1. Sistemin sınırları — ne yapar, ne yapmaz

**Birincil kullanıcı:** GEKAP, çevre ve ambalaj yükümlülükleri konusunda inceleme yapan
yetkili kamu uzmanı / denetçisi.

**Değer önerisi:** *Aynı denetim kapasitesiyle doğru firmayı, daha erken ve gerekçesiyle incelemek.*

| Yapar | Yapmaz |
|---|---|
| Hangi firma-dönem kaydının önce incelenmesi gerektiğini gösterir | Firma adına GEKAP beyannamesi hazırlamaz |
| Sonucun nedenlerini denetçiye açık biçimde sunar | GEKAP muhasebe programı değildir |
| Belirsizliği (tahmin aralığı, veri güveni) birlikte verir | Firmayı suçlu / kaçakçı / dolandırıcı ilan etmez |
| Nihai kararı insan denetçiye bırakır | Otomatik ceza kararı vermez |
| Karar kaydı ve itiraz izi tutar | Kamu denetçisinin yerini almaz |
| — | Hukuki delil üretme iddiasında değildir |

**0–100 puan = operasyonel inceleme önceliğidir. Suç veya usulsüzlük olasılığı DEĞİLDİR.**
Bu ifade arayüzde, API yanıtında, model kartında ve sunumda birebir aynı kalır.

### Firma-dönem başına üretilen 12 çıktı

1. `priority_score` — 0–100 inceleme önceliği
2. `data_confidence` — düşük / orta / yüksek
3. `expected_range` — beklenen beyan aralığı (q05, q50, q95; konformal kalibre)
4. `gap` — beklenen ile gerçek beyan arasındaki mutlak ve oransal fark
5. `reasons[]` — sonucu oluşturan ana gerekçeler (insan diliyle)
6. `signals_used[]` — kullanılan kanıt sinyalleri ve katkıları
7. `signals_unavailable[]` — eksik veya kullanılamayan sinyaller ve **nedeni**
8. `data_asof` / `data_quality` — veri tarihi ve kalitesi
9. `model_version` — model sürümü
10. `data_version` — veri sürümü
11. `decision_id` — karar kimliği (hash-chain'e bağlı)
12. `auditor_action` — denetçinin işlem ve karar kaydı

---

## 2. Katman mimarisi

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  KATMAN 0 — VERİ KAYNAKLARI  (kurum içinde kalır, sistem veri TOPLAMAZ)      │
│  GİB GEKAP beyannamesi · Ambalaj Bilgi Sistemi · TÜİK · Ticaret Bak. GTİP   │
│  Sıfır Atık Bilgi Sistemi · Önceki denetim kayıtları · (MVP'de: sentetik)    │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │ toplu yükleme (batch) / kurum içi API
┌────────────────────────────────▼─────────────────────────────────────────────┐
│  KATMAN 1 — VERİ ALIM ve DOĞRULAMA  (ingestion)                              │
│  Şema doğrulama · tokenizasyon (VKN → firm_token) · birim normalizasyonu     │
│  veri kalite puanı · eksik alan tespiti · veri sürümü damgası                │
│  → Çıktı: versiyonlanmış Parquet ambarı                                      │
└────────────────────────────────┬─────────────────────────────────────────────┘
┌────────────────────────────────▼─────────────────────────────────────────────┐
│  KATMAN 2 — ÖZELLİK ÜRETİMİ  (feature store)                                 │
│  Firma-çeyrek paneli · gecikmeli değerler · emsal istatistikleri (t-1)       │
│  ürün ağacı beklentisi · dış ticaret dengesi · mevsimsellik                  │
│  ⚠ İleriye bakış yasağı burada zorunlu kılınır                              │
└────────────────────────────────┬─────────────────────────────────────────────┘
┌────────────────────────────────▼─────────────────────────────────────────────┐
│  KATMAN 3 — MODEL                                                            │
│  ┌────────────────────┐  ┌────────────────────┐                              │
│  │ Tarihsel model     │  │ Emsal model        │  LightGBM quantile           │
│  │ (kendi geçmişi)    │  │ (benzer firmalar)  │  q05 / q50 / q95             │
│  └─────────┬──────────┘  └─────────┬──────────┘                              │
│            └───────────┬───────────┘                                          │
│              Konformal kalibrasyon (valid bölümünde)                          │
│              → kalibre edilmiş tahmin aralığı + gözlenen kapsama oranı        │
└────────────────────────────────┬─────────────────────────────────────────────┘
┌────────────────────────────────▼─────────────────────────────────────────────┐
│  KATMAN 4 — SEKİZ AYRI KANIT SİNYALİ ve BİRLEŞTİRME                          │
│  S1 tarihsel · S2 emsal · S3 beklenen-gerçekleşen · S4 faaliyet esnekliği    │
│  S5 dış ticaret/düzeltme · S6 dönemsel kırılma · S7 ürün ağacı · S8 dış kanıt│
│  Kullanılamayan sinyal → yeniden ölçekleme + veri güveni düşürme             │
│  → priority_score (0–100) + gerekçeler                                       │
└────────────────────────────────┬─────────────────────────────────────────────┘
┌────────────────────────────────▼─────────────────────────────────────────────┐
│  KATMAN 5 — AÇIKLAMA ve KARAR KAYDI                                          │
│  SHAP tabanlı katkı · şablonlu gerekçe metni · karar kimliği                 │
│  hash-chain denetim kaydı · itiraz ve yeniden inceleme izi                   │
│  (opsiyonel) RAG: yalnızca onaylı mevzuat dokümanlarında kaynaklı arama      │
└────────────────────────────────┬─────────────────────────────────────────────┘
┌────────────────────────────────▼─────────────────────────────────────────────┐
│  KATMAN 6 — API (REST) ve DENETÇİ ARAYÜZÜ                                    │
│  Kuyruk · dosya detayı · gerekçe paneli · veri güven ekranı                  │
│  denetçi kararı · COP31 etki paneli                                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Kritik mimari kural: döngüsellik koruması

Veri üretici (`anomalies.py`) **latent** büyüklükler üzerinde çalışır; dedektör yalnızca
**gözlenen** alanları görür. `features.py`, `anomalies.py`'yi ithal etmez ve bu kural
`validate_dataset.py` içinde AST analiziyle otomatik doğrulanır. Aksi halde sentetik
değerlendirme döngüsel ve aşırı iyimser olurdu.

---

## 3. Veri modeli

**Analiz birimi: `firma-çeyrek`** (firma-yıl değil — GEKAP beyanı üç aylık dönemler halinde verilir).

| Tablo | Anahtar | Rol |
|---|---|---|
| `Firms` | `firm_id` | Firma ana tablosu (tokenize kimlik) |
| `Product_Packaging` | `sku_id` → `firm_id` | SKU / ürün ağacı / ambalaj ağırlık matrisi |
| `Observations` | `observation_id` = `firm_id`+`period` | Firma-çeyrek ham gözlem (denetçiye görünen) |
| `Model_Ready` | `observation_id` | Model özellikleri — **ground truth içermez** |
| `Audit_Labels` | `observation_id` | Ground truth / denetim sonucu — **ayrı sayfa** |
| `GEKAP_Rates` | `rate_id` | Resmî tarifeler (Katman A) |
| `Macro_Anchors` | `anchor_id` | Makro çıpalar (Katman A) |
| `Climate_Factors` | `factor_id` | CO₂e faktörleri (Katman A + derived) |
| `Source_Registry` | `source_id` | Tüm kaynaklar + doğrudan URL |

Her tabloda `data_source_type` (`official_open` / `synthetic` / `derived`), `generation_method`
ve `source_ids` alanları zorunludur.

### Sekiz ayrı kanıt sinyali

> "Sekiz **bağımsız** sinyal" **denmez** — sinyaller korelasyonludur. "Sekiz **ayrı kanıt sinyali**" denir.

| # | Sinyal | Sorduğu soru | Besleyen özellik öneki |
|---|---|---|---|
| S1 | Tarihsel alt sınır ihlali | Firma kendi geçmiş beyan davranışından ne kadar sapıyor? | `f_s1_*` |
| S2 | Emsal alt sınır ihlali | Benzer firmaların beklenen aralığının ne kadar altında? | `f_s2_*` |
| S3 | Beklenen–gerçekleşen tonaj farkı | Ürün ağacından beklenen ile beyan arasındaki fark? | `f_s3_*` |
| S4 | Faaliyet esnekliği uyumsuzluğu | Üretim artarken beyan makul ölçüde değişiyor mu? | `f_s4_*` |
| S5 | Dış ticaret ve düzeltme dengesi | İthalat/ihracat/iade/mahsup/muafiyet beyanla uyumlu mu? | `f_s5_*` |
| S6 | Dönemsel davranış kırılması | Çeyreklik kalıpta açıklanamayan kırılma var mı? | `f_s6_*` |
| S7 | Ürün ağacı / ambalaj matrisi uyumsuzluğu | SKU ve ağırlık matrisi beyanı destekliyor mu? | `f_s7_*` |
| S8 | Dış doğrulama kanıtı | ERP / önceki denetim kayıtlarıyla uyumsuzluk var mı? | `f_s8_*` |

**Sinyal kullanılamıyorsa:** `f_avail_sN = 0` → sinyal "kullanılamıyor" işaretlenir, aktif
sinyaller önceden tanımlı kuralla yeniden ölçeklenir, `data_confidence` düşürülür.
Kritik alanlar eksikse kayıt **düşük risk sayılmaz**, "veri incelemesi gerekli" kuyruğuna gider.

**Sinyaller arası ilişki şu yöntemlerle ölçülür:** korelasyon matrisi · ablation testi ·
SHAP katkı analizi · alt grup performansı · duyarlılık analizi.

---

## 4. Kullanılacak teknolojiler — tam eşleştirme

> Bu bölüm ön değerlendirmede 0/5 alan başlığın doğrudan karşılığıdır.
> Her teknoloji dokuz soruya birden cevap verir.

### 4.1 Veri ve model katmanı

| # | Teknoloji | Sürüm | Lisans | Katman | Hangi işlev | Neden bu | Alternatifler | Hangi veri | Performans testi | Kamu ortamında kurulum | Üretimde yerini alacak |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | **Python** | 3.11–3.13 | PSF (BSD uyumlu) | 1–5 | Tüm veri ve model iş yükü | Kamu veri analitiğinde standart; kütüphane olgunluğu; ekip yetkinliği | R, Julia, Scala | Tüm tablolar | `pytest` + `validate_dataset.py` (38 kontrol) | Kurum onaylı imaj, offline wheel deposu | Aynı (LTS sürüm sabitlenir) |
| T2 | **pandas** | ≥2.2 (test: 3.0.5) | BSD-3-Clause | 1–2 | Panel dönüşümü, birleştirme, özellik üretimi | Firma-çeyrek panel işlemleri için en olgun API | Polars, DuckDB, PySpark | `Observations`, `Model_Ready` | 8.244 kayıt < 20 sn uçtan uca | Ek servis gerektirmez | **Polars veya DuckDB** — ulusal ölçekte bellek verimliliği |
| T3 | **NumPy** | ≥1.26 (test: 2.5.2) | BSD-3-Clause | 1–4 | Vektörel hesap, RNG (`default_rng`) | Deterministik `PCG64` akışı; SHA-256 ile alt akış türetme | — | Sentetik üretim | Determinizm testi: aynı seed → aynı hash | — | Aynı |
| T4 | **SciPy** | ≥1.11 | BSD-3-Clause | 3–4 | İstatistiksel dağılımlar, kalibrasyon testleri | Standart bilimsel yığın | statsmodels | Model çıktıları | Kapsama oranı testleri | — | Aynı |
| T5 | **LightGBM** | ≥4.3 | MIT | 3 | **Quantile regression** (q05/q50/q95) — beklenen beyan aralığı | Tablo verisinde hız/doğruluk; kategorik desteği; `objective="quantile"` yerleşik | XGBoost, CatBoost, scikit-learn GBM | `Model_Ready` (train) | Pinball loss + kapsama oranı + Precision@K | Tek `.txt`/`.pkl` model dosyası; internet gerekmez | Aynı + **model kayıt sistemi** (MLflow/kurum muadili) |
| T6 | **scikit-learn** | ≥1.4 | BSD-3-Clause | 3–4 | Baseline'lar (IsolationForest, HistGB), kalibrasyon, metrikler | Referans baseline üretimi ve ablation altyapısı | — | `Model_Ready` | PR-AUC, Precision@K, bootstrap GA | — | Aynı |
| T7 | **Konformal kalibrasyon** (`MAPIE` veya kendi implementasyonumuz) | MAPIE ≥0.8 / kendi | BSD-3-Clause / proje içi | 3 | Tahmin aralığının **kalibre edilmesi** | Dağılımdan bağımsız, değişim-değişmezlik (exchangeability) varsayımıyla kapsama garantisi | Bayesyen aralıklar, bootstrap | `valid` bölümü (2025Q3–Q4) | **Gözlenen kapsama oranı** ve aralık genişliği | Ek servis yok | Aynı |
| T8 | **PyArrow / Parquet** | ≥15.0 | Apache-2.0 | 1–2 | Sütunlu veri ambarı, sürümleme | Tip güvenliği, sıkıştırma, kısmi okuma | Feather, ORC, CSV | Tüm tablolar | I/O ve boyut ölçümü | Dosya sistemi düzeyinde; ek servis yok | Aynı (+ nesne depolama) |
| T9 | **XlsxWriter / openpyxl** | ≥3.2 / ≥3.1 | BSD-2 / MIT | 6 | Teslim Excel dosyası (16 sayfa, grafik, koşullu biçimlendirme) | Jüri ve kurum tarafında en yaygın tüketim formatı | pandas `to_excel` (biçimlendirme sınırlı) | Tüm tablolar | Dosya açılış ve formül hata taraması | — | Rapor servisi (opsiyonel) |

### 4.2 Servis ve arayüz katmanı

> Bu katmanın **kodunu geliştirici yazacaktır**; buradaki seçimler mimari sözleşmedir.

| # | Teknoloji | Sürüm | Lisans | Katman | Hangi işlev | Neden bu | Alternatifler | Hangi veri | Performans testi | Kamu ortamında kurulum | Üretimde yerini alacak |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T10 | **FastAPI** | ≥0.110 | MIT | 6 | REST API, otomatik OpenAPI şeması | Pydantic ile şema doğrulama; OpenAPI dokümantasyonu teslim şartıdır | Flask, Django REST, .NET | Skor ve karar kayıtları | `locust`/`k6` yük testi; p95 gecikme hedefi < 300 ms | Uvicorn + reverse proxy; kurum WAF arkasında | Aynı + **kurumsal API ağ geçidi** |
| T11 | **Pydantic** | ≥2.6 | MIT | 6 | API sözleşmesi ve tip doğrulama | Şema ihlallerini çalışma anında yakalar | marshmallow | API girdi/çıktı | Şema uyum testleri | — | Aynı |
| T12 | **React** | 19.x | MIT | 6 | Denetçi arayüzü | Bileşen ekosistemi; ekip yetkinliği | Vue, Svelte, Angular | API yanıtları | Lighthouse + erişilebilirlik denetimi | Statik build; kurum sunucusundan servis | Aynı |
| T13 | **Vite** | ≥5 | MIT | 6 | Frontend derleme | Hızlı build; küçük çıktı | Webpack, Next.js | — | Build süresi ve bundle boyutu | Offline `npm ci` (kurum kayıt sunucusu) | Aynı |
| T14 | **React Router** | ≥6 | MIT | 6 | Ekranlar arası yönlendirme | Standart | TanStack Router | — | — | — | Aynı |
| T15 | **SQLite** | 3.4x | Kamu malı (public domain) | 1, 5 | **YALNIZCA MVP** — yerel karar kaydı ve meta veri | Sıfır kurulum; tek dosya; demoda internetsiz çalışır | DuckDB | Karar kayıtları | Küçük ölçek işlem testi | Tek dosya | ⚠ **PostgreSQL veya kurumun kurumsal veritabanı** |
| T16 | **PostgreSQL** | ≥16 | PostgreSQL Lisansı | 1, 5 | **Pilot/üretim** veritabanı | Rol tabanlı erişim, denetim kaydı, yedekleme, ölçek | Oracle, MSSQL (kurum standardına göre) | Tüm operasyonel veri | Yük ve kurtarma testi | Kurum içi küme, şifreli depolama | — |

> **SQLite ulusal ölçekli üretim veritabanı olarak sunulmaz.** Yalnızca kolay kurulabilen
> MVP/demo teknolojisidir. Bu ayrım sunumda da açıkça korunur.

### 4.3 Açıklanabilirlik ve mevzuat modülü

| # | Teknoloji | Sürüm | Lisans | Katman | Hangi işlev | Neden bu | Alternatifler | Hangi veri | Performans testi | Kamu ortamında kurulum | Üretimde yerini alacak |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T17 | **SHAP** | ≥0.45 | MIT | 5 | Sinyal katkılarının hesaplanması | Ağaç modelleri için TreeSHAP hızlı ve tutarlı | Permutation importance, LIME | `Model_Ready` | Ablation testiyle çapraz doğrulama | Ek servis yok | Aynı |
| T18 | **Şablonlu gerekçe üretimi** | proje içi | proje içi | 5 | SHAP katkılarını insan diline çevirme | **Deterministik ve denetlenebilir**; halüsinasyon riski yok | LLM ile serbest üretim | Skor çıktıları | Metin-katkı tutarlılık testi | — | Aynı |
| T19 | **RAG / LLM (opsiyonel)** | kurum onaylı model | duruma göre | 5 | **Yalnızca** onaylı mevzuat dokümanlarında kaynaklı arama | Denetçinin mevzuat referansına hızlı erişimi | Klasik tam metin arama (Elasticsearch/Whoosh) | Yalnızca mevzuat dokümanları | Kaynak isabet oranı, halüsinasyon denetimi | **Kurum içinde (on-premise)**; kamu verisi dış servise gönderilmez | Kurum onaylı model |

**LLM/RAG kısıtları (bağlayıcı):**
skor **üretmez** · karar **vermez** · yalnızca onaylı mevzuat dokümanlarında arama yapar ·
her cevapta **kaynak gösterir** · tercihen kurum içinde çalışır · kamu verisini izinsiz dış
servise **göndermez**. Çekirdek karar mekanizması **değildir**; devre dışı bırakıldığında
sistem tam işlevle çalışmaya devam eder.

### 4.4 Bütünlük, güvenlik ve operasyon

| # | Teknoloji | Sürüm | Lisans | Katman | İşlev | Kamu ortamında kurulum | Üretimde yerini alacak |
|---|---|---|---|---|---|---|---|
| T20 | **Hash-chain denetim kaydı** (SHA-256, `hashlib`) | stdlib | PSF | 5 | Kayıt değişikliğini görünür kılar | Ek bağımlılık yok | + WORM depolama / kurum log altyapısı |
| T21 | **Karar kimliği (`decision_id`)** | proje içi | proje içi | 5 | Her skoru model+veri sürümüne bağlar | — | Aynı |
| T22 | **Docker / OCI imaj** | ≥24 | Apache-2.0 | tümü | Bağımsız kurulabilirlik (teslim şartı) | Kurum onaylı temel imaj, offline paket deposu | Kurum konteyner platformu |
| T23 | **pytest** | ≥8 | MIT | tümü | Birim ve bütünleşme testleri | CI içinde | Aynı |
| T24 | **Veri ve model sürümleme** | proje içi manifest → DVC/MLflow | Apache-2.0 | 1, 3 | `data_version`, `model_version` izlenebilirliği | Dosya tabanlı manifest | **Model kayıt sistemi** |

---

## 5. Denetçi iş akışı ve ekranlar

```
[1] Kuyruk ekranı           → dönem/sektör/il filtresi, öncelik sırası, veri güveni rozeti
     │                         ⚠ "İnceleme önceliği — suç olasılığı değildir" uyarısı sabit
     ▼
[2] Dosya detayı            → beklenen aralık (q05–q95) vs beyan, fark, zaman serisi
     │
     ▼
[3] Gerekçe paneli          → hangi sinyaller ne kadar katkı verdi (SHAP), insan diliyle
     │                         + hangi sinyaller KULLANILAMADI ve neden
     ▼
[4] Veri güven ekranı       → eksik alanlar, veri tarihi, BOM kapsamı, kalite puanı
     │
     ▼
[5] Denetçi kararı          → incele / açıklandı-uygun / veri talep et / erteleme
     │                         gerekçe metni zorunlu → karar kaydına yazılır
     ▼
[6] Karar kaydı + itiraz izi → decision_id, model_version, data_version, zaman damgası
```

Ayrıca: **COP31 etki paneli** (§9) — doğrulanabilir ve senaryo metrikleri ayrı bloklarda.

---

## 6. API sözleşmesi (özet)

| Yöntem | Uç nokta | İşlev |
|---|---|---|
| `POST` | `/v1/score/batch` | Firma-dönem kayıtları için toplu skorlama |
| `GET` | `/v1/queue` | Önceliklendirilmiş inceleme kuyruğu (filtre + sayfalama) |
| `GET` | `/v1/observations/{observation_id}` | Tek kayıt detayı + 12 çıktı |
| `GET` | `/v1/observations/{observation_id}/explanation` | Sinyal katkıları ve gerekçeler |
| `POST` | `/v1/decisions` | Denetçi kararının kaydı (hash-chain'e eklenir) |
| `GET` | `/v1/decisions/{decision_id}` | Karar kaydı ve izleme |
| `GET` | `/v1/cop31/dashboard` | Doğrulanabilir + senaryo metrikleri |
| `GET` | `/v1/meta/versions` | `model_version`, `data_version`, tarife sürümü |
| `GET` | `/v1/health` | Servis sağlığı |

**Örnek yanıt (`/v1/observations/{id}`):**

```json
{
  "observation_id": "SYN-FRM-000123-2026Q1",
  "priority_score": 78.4,
  "priority_score_meaning": "Operasyonel inceleme onceligi. Suc veya usulsuzluk olasiligi DEGILDIR.",
  "data_confidence": "orta",
  "expected_range": { "q05": 41.2, "q50": 63.8, "q95": 92.1, "unit": "ton",
                      "calibration": "conformal", "target_coverage": 0.90,
                      "observed_coverage_on_test": 0.887 },
  "declared": 28.6,
  "gap": { "absolute_ton": 35.2, "relative": 0.552 },
  "reasons": [
    "Firma kendi son 4 ceyrek ortalamasinin %55 altinda beyan verdi (S1)",
    "Uretim yillik %12 artarken ambalaj beyani %31 azaldi (S4)",
    "Urun agacindan beklenen tonaj beyanin 2,1 kati (S3)"
  ],
  "signals_used": [
    { "signal": "S1", "contribution": 0.31 },
    { "signal": "S3", "contribution": 0.27 },
    { "signal": "S4", "contribution": 0.19 }
  ],
  "signals_unavailable": [
    { "signal": "S5", "reason": "ithalat ve ihracat verisi eksik" },
    { "signal": "S8", "reason": "dis dogrulama kaydi bulunmuyor" }
  ],
  "data_asof": "2026-07-31", "data_quality_score": 0.61,
  "model_version": "gus-lgbm-quantile-1.0.0", "data_version": "dataset-1.0.0",
  "decision_id": "dec_01J9F2...", "auditor_action": null
}
```

---

## 7. Olgunluk seviyeleri — MVP / Pilot / Üretim

| Boyut | **MVP (TEKNOFEST demosu)** | **Kamu pilotu** | **Üretim (ulusal ölçek)** |
|---|---|---|---|
| Çalışma ortamı | Yerel makine / tek konteyner | Kurum içi test ortamı | Kurum onaylı üretim altyapısı |
| Veri | Sentetik (bu depo) | Kurumun gerçek verisi, sınırlı kapsam | Kurumun tam verisi |
| Veritabanı | **SQLite** | PostgreSQL | Kurumun kurumsal veritabanı |
| Veri işleme | pandas + Parquet | pandas/Polars + Parquet | Polars/DuckDB veya kurum veri platformu |
| Kimlik doğrulama | Yok (yerel demo) | Kurum SSO (test) | Merkezî kimlik doğrulama + **MFA** |
| Yetkilendirme | Yok | Rol tabanlı erişim (RBAC) | RBAC + kayıt bazlı yetki |
| Model yönetimi | Dosya + manifest | Model kayıt sistemi | Model kayıt + otomatik geri alma |
| Denetim kaydı | Hash-chain (SQLite) | Hash-chain + PostgreSQL | Değiştirilemez (WORM) depolama |
| İzleme | Log dosyası | Metrik + uyarı | Tam gözlemlenebilirlik + olay müdahale planı |
| Yedekleme | Yok | Günlük | Kurum politikası + felaket kurtarma |
| Güvenlik testi | Bağımlılık taraması | Sızma testi | Kurum standardına uygun tam test |

---

## 8. Devletin kendi verisini bağlaması

Sistem **veri toplamaz**; kurumun kendi verisini kurumun kendi ortamında değerlendirir.
Sentetik alanlar pilotta karşılık gelen resmî kaynakla değiştirilir — **mimari ve sinyal
mantığı değişmez**. Tam eşleşme tablosu Excel'deki `Government_Integration_Map` sayfasındadır.

| Dataset alanı | Devletin gerçek kaynağı | Kurum | Kritiklik |
|---|---|---|---|
| `declared_packaging_tonnage`, `declared_ton_*` | GEKAP Beyannamesi ambalaj tabloları | GİB | Kritik |
| `bom_expected_tonnage_observable` | Ambalaj Bilgi Sistemi / ürün ağacı beyanları | ÇŞİDB | Kritik |
| `production_qty` | Sanayi üretim/kapasite kayıtları | TÜİK / Sanayi ve Tek. Bak. | Kritik |
| `import_qty`, `export_qty` | GTİP bazlı dış ticaret ve gümrük beyannameleri | Ticaret Bak. / TÜİK | Kritik |
| `correction_qty` | Düzeltme beyannamesi kayıtları | GİB | Yüksek |
| `exemption_flag` | Muafiyet / ihraç kayıtlı teslim | GİB / Ticaret Bak. | Yüksek |
| `external_evidence_tonnage` | Önceki denetim ve saha kayıtları | ÇŞİDB il müdürlükleri | Orta |
| Geri kazanım akışı | Sıfır Atık Bilgi Sistemi, TABS, MoTAT | ÇŞİDB | Orta |
| GEKAP tarifeleri | Yıllık tebliğ tutarları | ÇŞİDB | **Zaten hazır** |

---

## 9. COP31 modülü

**Modül adı:** COP31 Packaging Transparency & Climate Impact Dashboard
**Önerilen pilot adı:** Türkiye Packaging Transparency Pilot — COP31 Antalya Demonstration

**Doğrulanan gerçekler:** COP31, 9–20 Kasım 2026, Antalya EXPO Center. Türkiye **ev sahibi
ülke**; müzakere başkanlığı **Avustralya ile ortak** yürütülmektedir — sunumda "Türkiye COP31
başkanı" ifadesi kullanılmaz.

**COP31 atık hedefleri** (küresel atık artışının 2035'e kadar yarıya indirilmesi, döngüsel
malzeme kullanım oranının en az %15'e çıkarılması, sıfır atık ve atık kaynaklı metanın iklim
eyleminin merkezine alınması) **başkanlık gündemi** niteliğindedir; müzakere edilmiş bağlayıcı
COP kararı **değildir** ve taban yıl tanımlı değildir.

**Bağlayıcı kısıtlar:** resmî COP31 ortaklığı varmış gibi konuşulmaz · logo izinsiz
kullanılmaz · beyan düzeltmesi fiziksel geri dönüşüm sayılmaz · potansiyel CO₂e gerçekleşmiş
azaltım gibi gösterilmez · Türkiye'ye özgü faktör yoksa uluslararası faktör kesin sonuç olarak
sunulmaz.

| Doğrulanabilir metrikler | Yalnızca senaryo metrikleri |
|---|---|
| Analiz edilen firma / beyan sayısı | Potansiyel resmî geri kazanım tonajı |
| Önceliklendirilen dosya sayısı | Potansiyel CO₂e etkisi |
| Top-K içindeki doğrulanmış sonuç | Potansiyel hammadde tasarrufu |
| 100 denetim başına doğrulanmış vaka | Potansiyel döngüsel malzeme katkısı |
| Düzeltilen ambalaj tonajı + malzeme kırılımı | |
| Ek GEKAP tutarı, inceleme süresi, kapsam | |

Her senaryo göstergesinde: faktör kaynağı · faktör yılı · coğrafi kapsam · sistem sınırı ·
dönüşüm formülü · varsayım · belirsizlik · `Potential scenario - not verified impact` etiketi.

**Senaryo zinciri:**
`doğrulanmış_düzeltme_ton × varsayılan_geri_kazanım_oranı × malzeme_payı × WARM v16 faktörü = potansiyel_CO₂e`
Faktörler ABD'ye özgüdür ve **kısa tondan** metrik tona çevrilmiştir. Kâğıt-kartonda azaltımın
~%97'si ABD ormancılığına özgü orman karbon depolamasından gelir; bu nedenle **orman karbonu
hariç muhafazakâr senaryo** ayrıca raporlanır.

---

## 10. Hukuk, güvenlik ve kamu kullanımı

KVKK uyumu · veri minimizasyonu · amaçla sınırlı kullanım · tokenize firma kimliği
(gerçek VKN kurum sınırları içinde kalır) · aktarımda ve depoda şifreleme · rol tabanlı erişim ·
çok faktörlü kimlik doğrulama · model ve veri sürümleme · karar kayıtları · saklama ve imha
politikası · **insan denetçi onayı** · itiraz ve yeniden inceleme izi · harici yapay zekâ
servisine izinsiz kamu verisi gönderilmemesi.

> **Model tek başına ceza veya olumsuz idari karar üretemez.**
> Ek GEKAP gelirinin otomatik olarak atık toplayıcılarına aktarılacağı **iddia edilmez** —
> bu bütçe ve mevzuat kararı gerektirir. Atık toplayıcılarının resmîleştirilmesi yalnızca
> ayrı bir belediye/kamu politika pilotu olarak sunulabilir.

---

## 11. Açık maddeler — kararınız gereken noktalar

| # | Konu | Durum |
|---|---|---|
| 1 | **Şartname ve rapor dosyaları elime ulaşmadı** — Aşama 1 (belge incelemesi, puan analizi, çelişki taraması) yapılamadı | Dosya bekleniyor |
| 2 | Sunum süresi (5 dk ↔ 7 dk + 3 dk S/C) çelişkisi | Organizasyondan resmî açıklama istenmeli |
| 3 | Finalist sayısı (10 ↔ en fazla 15) çelişkisi | Organizasyondan resmî açıklama istenmeli |
| 4 | "Kullanılacak Teknolojiler" 0/5 gerekçesi | Organizasyondan yazılı gerekçe istenmeli |
| 5 | 2023 GEKAP tarifeleri (yıl ortasında CB kararıyla değişti) | Birincil metinden doğrulanmalı; şu an kullanılmıyor |
| 6 | TÜİK Sanayi Üretim Endeksi ve Dış Ticaret serileri | `TO_BE_FILLED` — veri portalından çekilmeli |
| 7 | COP31 hedeflerinin birincil UNFCCC metninden teyidi | UNFCCC sayfası otomatik çekimde boş döndü |
| 8 | GEKAP beyannamesinin satır/sütun düzeni | Pilot öncesi GİB ile teyit edilmeli |
| 9 | Türkiye'ye özgü ambalaj CO₂e faktörü | Mevcut değil — ABD faktörü sınırlılık notuyla kullanılıyor |

---

## 12. Sonraki adım

Bu mimari onaylandığında geliştirmeye şu sırayla devam edilir
(**backend/frontend kodu geliştirici tarafından yazılacaktır**):

1. **Aşama 4 — Model ve doğrulama:** baseline'lar → LightGBM quantile → konformal kalibrasyon →
   8 sinyal birleştirme → ablation → alt grup testi → Precision/Recall/Lift@K → yanlış-pozitif
   ve yanlış-negatif analizi → **model kartı**
2. **Aşama 5 — Ürün tasarımı:** API sözleşmesinin tam OpenAPI şeması, ekran akışları,
   karar kaydı şeması, güvenlik tasarımı
3. **Aşama 6 — Final hazırlığı:** 5 ve 7 dakikalık sunum, 2 dakikalık canlı demo,
   3 dakikalık S/C, jüri soru bankası, söylenmemesi gereken ifadeler listesi,
   final teslim kontrol listesi
