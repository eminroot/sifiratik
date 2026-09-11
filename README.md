<div align="center">

<img src="assets/banner.png" alt="GÜS-DEDEKTİV — GEKAP beyanları için denetim önceliklendirme" width="100%">

<br><br>

**GEKAP ambalaj beyanlarında hangi işletmenin önce incelenmesi gerektiğini,
kanıtı ve belirsizliğiyle birlikte söyleyen karar destek platformu.**

Takım **KinetiX** · TEKNOFEST 2026 Sıfır Atık ve Döngüsel Ekonomi

<br>

### Servis ve Model

![Python](https://img.shields.io/badge/PYTHON%203.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FASTAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Pydantic](https://img.shields.io/badge/PYDANTIC%20V2-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLALCHEMY%202.0-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![LightGBM](https://img.shields.io/badge/LIGHTGBM-9ACD32?style=for-the-badge&logoColor=white)

### Veri ve Bilim

![NumPy](https://img.shields.io/badge/NUMPY-013243?style=for-the-badge&logo=numpy&logoColor=white)
![pandas](https://img.shields.io/badge/PANDAS-150458?style=for-the-badge&logo=pandas&logoColor=white)
![scikit-learn](https://img.shields.io/badge/SCIKIT--LEARN-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white)
![SciPy](https://img.shields.io/badge/SCIPY-8CAAE6?style=for-the-badge&logo=scipy&logoColor=white)
![Parquet](https://img.shields.io/badge/PARQUET-50ABF1?style=for-the-badge&logo=apacheparquet&logoColor=white)

### Arayüz

![React](https://img.shields.io/badge/REACT%2019-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Vite](https://img.shields.io/badge/VITE%206-646CFF?style=for-the-badge&logo=vite&logoColor=white)
![React Router](https://img.shields.io/badge/REACT%20ROUTER%207-CA4245?style=for-the-badge&logo=reactrouter&logoColor=white)
![Framer Motion](https://img.shields.io/badge/FRAMER%20MOTION-0055FF?style=for-the-badge&logo=framer&logoColor=white)
![Lucide](https://img.shields.io/badge/LUCIDE-F56565?style=for-the-badge&logo=lucide&logoColor=white)

### Depolama, Test ve Asistan

![SQLite](https://img.shields.io/badge/SQLITE-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/POSTGRESQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Alembic](https://img.shields.io/badge/ALEMBIC-6BA81E?style=for-the-badge&logoColor=white)
![pytest](https://img.shields.io/badge/PYTEST-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)
![Gemini](https://img.shields.io/badge/GOOGLE%20GEMINI-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)

<br>

[![CI](https://github.com/eminroot/zerowaste/actions/workflows/ci.yml/badge.svg)](https://github.com/eminroot/zerowaste/actions/workflows/ci.yml)
![Platform](https://img.shields.io/badge/PLATFORM-WEB-2b2b31?style=flat-square&labelColor=1a1a1d)
![Lisans](https://img.shields.io/badge/LİSANS-MIT-14603d?style=flat-square&labelColor=1a1a1d)
![Dil](https://img.shields.io/badge/ARAYÜZ-TÜRKÇE%20%7C%20İNGİLİZCE-1d4674?style=flat-square&labelColor=1a1a1d)
![Model](https://img.shields.io/badge/MODEL-gus--ml--1.0.0-7a4d0a?style=flat-square&labelColor=1a1a1d)
![Durum](https://img.shields.io/badge/DURUM-MVP%20%2F%20PROTOTİP-8e2323?style=flat-square&labelColor=1a1a1d)

</div>

---

> [!IMPORTANT]
> **0–100 puan operasyonel bir inceleme önceliğidir. İhlal, suç veya usulsüzlük
> olasılığı değildir.** Sistem otomatik ceza kararı üretmez; nihai karar yetkili
> insan denetçiye aittir. Depodaki firma kayıtları, beyanlar ve denetim sonuçları
> **tamamen sentetiktir** — hiçbir gerçek firmayı temsil etmez. Buna karşılık
> GEKAP tarifeleri, ambalaj atığı istatistikleri, geri kazanım oranları ve iklim
> faktörleri **gerçek, kaynağı belirtilmiş açık verilerdir**
> (bkz. [`ml/data/reference/source_registry.csv`](ml/data/reference/source_registry.csv)).

---

## İçindekiler

- [Problem](#problem)
- [Ne yapar, ne yapmaz](#ne-yapar-ne-yapmaz)
- [Prototip](#prototip)
- [Algoritma akışı](#algoritma-akışı)
- [Sekiz kanıt sinyali](#sekiz-kanıt-sinyali)
- [Kurulum ve çalıştırma](#kurulum-ve-çalıştırma)
- [Depo yapısı](#depo-yapısı)
- [API](#api)
- [Testler](#testler)
- [Ölçülen sonuçlar](#ölçülen-sonuçlar)
- [Dokümanlar](#dokümanlar)
- [Takım ve lisans](#takım-ve-lisans)

---

## Problem

GEKAP (Geri Kazanım Katılım Payı) beyanlarını inceleyecek denetim kapasitesi
sınırlıdır. Bugün hangi işletmenin inceleneceği büyük ölçüde ihbara, rastgele
seçime veya tek bir eşik kuralına bağlıdır. Sonuç: **doğru işletme geç bulunur,
yanlış kapı çalınır.**

GÜS-DEDEKTİV aynı denetim kapasitesiyle **doğru firmayı, daha erken ve
gerekçesiyle** incelemeyi hedefler. Firma-çeyrek bazında bir beyanı dört ayrı
referansla karşılaştırır — firmanın kendi geçmişi, üretiminin ima ettiği hacim,
benzediği firmalar ve eşleşen gümrük satırları — ve ortaya çıkan sekiz kanıtı tek
bir 0–100 inceleme önceliğine çevirir. Her sonucun yanında **hangi kanıtın ne
kadar katkı verdiği** ve **hangi kontrolün neden çalıştırılamadığı** yazılıdır.

## Ne yapar, ne yapmaz

| Yapar | Yapmaz |
| --- | --- |
| Hangi firma-dönem kaydının önce incelenmesi gerektiğini gösterir | Firma adına GEKAP beyannamesi hazırlamaz |
| Sonucun nedenlerini denetçiye açık biçimde sunar | GEKAP muhasebe programı değildir |
| Belirsizliği (tahmin aralığı, veri güveni) birlikte verir | Firmayı suçlu ilan etmez |
| Nihai kararı insan denetçiye bırakır | Otomatik ceza kararı vermez |
| Karar kaydı ve itiraz izi tutar | Kamu denetçisinin yerini almaz |
| Kurumun kendi verisini kendi ortamında değerlendirir | Veri **toplamaz**, dışarıya kayıt göndermez |

---

## Prototip

Dokuz ekran, tek bir denetçi iş akışı: **kuyruk → dosya → gerekçe → veri güveni →
karar → kayıt.** Arayüz Türkçe ve İngilizce çalışır; aşağıdaki görüntüler çalışan
prototipten alınmıştır.

<div align="center">

**Genel görünüm** — dönemin nerede durduğu, öncelik dağılımı ve risk tutarı

<img src="assets/ekran-goruntuleri/01-genel-gorunum.png" alt="Genel görünüm ekranı" width="90%">

<br><br>

**Firma dosyası** — puan, beklenen aralık, beyan ve sonucun künyesi

<img src="assets/ekran-goruntuleri/03-firma-dosyasi.png" alt="Firma dosyası ekranı" width="90%">

<br><br>

**Gerekçe paneli** — sekiz kontrolün tamamı, katkısı ve *çalıştırılamayanın nedeni*

<img src="assets/ekran-goruntuleri/10-gerekce-paneli.png" alt="Gerekçe paneli" width="90%">

</div>

<details>
<summary><b>Diğer altı ekran</b></summary>

<br>

| Ekran | Görüntü |
| --- | --- |
| **Denetim kuyruğu** — filtreli, sayfalı, sıralı | <img src="assets/ekran-goruntuleri/02-kuyruk.png" width="420"> |
| **Firma geçmişi** — her dönem, o gün beklenen aralıkla | <img src="assets/ekran-goruntuleri/04-firma-gecmisi.png" width="420"> |
| **Veri kalitesi** — platformun ne görüp ne göremediği | <img src="assets/ekran-goruntuleri/05-veri-kalitesi.png" width="420"> |
| **COP31 etki paneli** — tonaj, katkı payı, emisyon | <img src="assets/ekran-goruntuleri/06-etki-paneli.png" width="420"> |
| **Pilot** — yapılandırılmış pilot senaryosunun çalıştırılması | <img src="assets/ekran-goruntuleri/07-pilot.png" width="420"> |
| **Denetim izi** — hash-chain karar kaydı ve doğrulama | <img src="assets/ekran-goruntuleri/08-denetim-izi.png" width="420"> |
| **Şeffaflık** — kapsam, ilkeler, politika, motorlar | <img src="assets/ekran-goruntuleri/09-seffaflik.png" width="420"> |

</details>

---

## Algoritma akışı

> 📄 **Ayrı doküman:** [`docs/ALGORITMA-AKISI.md`](docs/ALGORITMA-AKISI.md) ·
> 🖨️ **Baskıya uygun PDF:** [`docs/ALGORITMA-AKISI.pdf`](docs/ALGORITMA-AKISI.pdf)

<div align="center">
<img src="assets/algoritma-akisi.png" alt="GÜS-DEDEKTİV uçtan uca algoritma akışı" width="82%">
</div>

### Bir kayıt nasıl puanlanır

```mermaid
flowchart TD
    A["<b>1 · Bağlam</b><br/>ScoringContext — firma · beyan geçmişi<br/>emsal · saha · GTİP · veri kalitesi"]
    B["<b>2 · Özellik satırı</b><br/>manifest.feature_order bağlayıcı<br/>hesaplanamayan özellik eksik bırakılır"]
    C["<b>3 · Beklenen aralık</b><br/>iki quantile başlığı → harman (w = 0,95)<br/>Mondrian CQR ile kalibrasyon"]
    D{"<b>4 · Sekiz kontrol</b><br/>E1 … E8"}
    E["<b>tetiklendi / sessiz</b><br/>0–100 sinyal puanı"]
    F["<b>çalıştırılamadı</b><br/>ağırlık paydadan düşer<br/>sıfır sayılmaz"]
    G["<b>5 · Birleştirme</b><br/>ağırlıklı ortalama ⊕ en güçlü bulgu<br/>puan = 0,65 · ortalama + 0,35 · en güçlü"]
    H["<b>6 · Gerekçe</b><br/>TreeSHAP katkısı → şablonlu cümle"]
    I["<b>7 · Karar kaydı</b><br/>decision_id + SHA-256 hash-chain"]

    A --> B --> C --> D
    D -->|"girdi var"| E
    D -->|"girdi yok"| F
    E --> G
    F -->|"dayanak kapsamı düşer"| G
    G --> H --> I
```

**Beklenen aralık.** İki LightGBM quantile başlığı ayrı ayrı tahmin verir —
biri firmanın kendi beyan geçmişinden, diğeri emsallerinden ve üretim hacminden.
İkincisi **firmanın kendi geçmişini hiç görmez**, böylece yıllardır eksik beyan
veren bir firma kendi beklentisini aşağı çekemez. İkisi log uzayında harmanlanır
ve aralık, **Mondrian konformal** yöntemle sektör, ölçek bandı ve veri güvenine
göre kalibre edilir.

```
ŷ      = exp( w · log1p(ŷ_hist) + (1−w) · log1p(ŷ_peer) ) − 1 ,  w = 0,95
[a, b] = ŷ ± konformal_genişlik( sektör, ölçek, veri_güveni )
```

**Puan.** Çalışabilen kontrollerin ağırlıklı ortalaması, en güçlü tek bulguyla
sabit bir oranda harmanlanır. Harman olmasaydı tek bir konuda sürekli hatalı olan
bir firma, dört konuda az hatalı olan bir firmanın altında sıralanırdı — bir
denetim ekibi böyle triyaj yapmaz.

```
puan = (1 − p) · ağırlıklı_ortalama + p · en_güçlü ,  p = 0,35
```

**Eksik veri aklanma değildir.** Çalıştırılamayan bir kontrolün ağırlığı paydadan
düşürülür; sıfır sayılmaz. Bunun yerine **dayanak kapsamı** düşer ve bu, puanın
yanında yazılır. Model ayrıca, kontrol edilemeyen dosyaların daha sık eksik beyan
taşıdığını veriden öğrenir — panel bunu kelimelerle söyler, sessizce "temiz"
saymaz.

---

## Sekiz kanıt sinyali

Her kontrol üç durumdan birini bildirir: **tetiklendi**, **sessiz**,
**çalıştırılamadı** — ve son ikisi aynı şey değildir.

| Kod | Kontrol | Neyle karşılaştırır | Ağırlık |
| --- | --- | --- | ---: |
| `E1` | Geçmişe göre eksik beyan | Beyanı, firmanın kendi geçmiş beyan örüntüsüyle | 0,20 |
| `E2` | Yapısal eksik beyan | Beyanı, üretiminin ima ettiği hacimle | 0,18 |
| `E3` | Emsalden sapma | Ambalaj yoğunluğunu, aynı sektör ve ölçek sınıfıyla | 0,15 |
| `E4` | Üretim ile beyan uyumsuzluğu | Üretimdeki hareketi, beyandaki hareketle | 0,14 |
| `E5` | Dönemler arası tutarsızlık | Yoğunluğun dönemler boyunca kararlılığını | 0,09 |
| `E7` | Saha çelişkisi | Saha gözlemlerini, beyan edilenle | 0,09 |
| `E8` | Gümrük tarife kanıtı | GTİP satırlarının ima ettiği ambalajı, beyanla | 0,08 |
| `E6` | Beyan örüntüsü | Yuvarlama, tekrar ve eşik davranışını | 0,07 |

Eşikler, ağırlıklar ve harman oranı **politikadır, kod değildir**. Yetkili kurum
bunları kaynak koda dokunmadan `GET`/`PUT /api/scoring/policy` üzerinden
değiştirebilir. Politikada kapatılan bir sinyal **modelde de kapanır**.

---

## Kurulum ve çalıştırma

**Gereksinimler:** Python 3.11+ · Node.js 20+

### Windows — tek tık

```bat
start.bat
```

API'yi ve arayüzü birlikte başlatır, ikisi de gerçekten cevap verene kadar
bekler, tarayıcıyı açar ve iki logu tek pencereye akıtır. `Ctrl+C` veya `Q`
ikisini birden durdurur.

### Elle — iki süreç

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

| | Adres |
| --- | --- |
| Arayüz | <http://localhost:5173> |
| API | <http://localhost:8000> |
| API referansı (OpenAPI) | <http://localhost:8000/docs> |

Veritabanı **ilk açılışta kendini kurar**: `ml/data/output/csv` altındaki panel
içe aktarılır ve her dönem puanlanır. Sıfırdan kurmak için:

```bash
cd backend && python -m app.database.gus_import --reset
```

### Model motoru

Model artefaktları `backend/models/` altında depoyla birlikte gelir; `lightgbm`
kurulu olduğunda **model motoru doğrudan devreye girer**. Artefaktlar veya
lightgbm yoksa `resolve_engine` deterministik kural motoruna düşer ve **her yanıt
hangi motorun ürettiğini söyler**. Seçim `SCORING_ENGINE=ml|mock` ile yapılır.

```bash
curl http://localhost:8000/api/health
# {"status":"ok","engine":"ml","model_version":"gus-ml-1.0.0"}
```

### Uygulama içi asistan

Ekrandaki dönem hakkındaki soruları yanıtlar. Gemini anahtarı yokken **kapalıdır
ve bunu söyler**, sessizce hata vermez.

```bash
cp backend/.env.example backend/.env
# GEMINI_API_KEY=...
```

Her istek, ekrandaki dönemden derlenen bir brifing taşır — bant dağılımı, risk
tutarı, alan kapsamı, sekiz kontrol, kuyruğun başı ve varsa görüntülenen firma —
böylece cevap, sayfanın gösterdiği rakamların aynısını alıntılar. Brifing
**referans veri** olarak geçirilir, talimat olarak değil.

### PostgreSQL

`DATABASE_URL` ayarlanır ve migrasyonlar uygulanır. Başka hiçbir şey değişmez;
modellerdeki her sütun tipi iki arka uçta da vardır.

```bash
export DATABASE_URL=postgresql+psycopg://gus:gus@localhost:5432/gus_dedektiv
alembic upgrade head
python -m app.database.gus_import
```

---

## Depo yapısı

```
zerowaste/
├── backend/                  FastAPI servisi
│   ├── app/
│   │   ├── main.py             uygulama, CORS, router bağlama
│   │   ├── config.py           ayarlar ve kurumun ayarlayabileceği puanlama politikası
│   │   ├── reference.py        GEKAP tarifeleri, sektör katsayıları, sinyal kataloğu
│   │   ├── i18n.py             API'nin yazdığı Türkçe metin
│   │   ├── routers/            panel · firmalar · kuyruk · etki · şeffaflık · asistan
│   │   ├── schemas/            tel üstü sözleşme (Pydantic v2)
│   │   ├── services/           sorgular, iş akışı, hash-chain, etki, pilot
│   │   ├── scoring/            motor arayüzü ve iki uygulaması
│   │   ├── models/             SQLAlchemy tabloları
│   │   └── database/           motor, oturum, panel içe aktarma
│   ├── models/               teslim edilen model artefaktları (LightGBM + kalibrasyon)
│   ├── tests/                motor özellikleri ve API sözleşmesi
│   └── alembic/              migrasyonlar (PostgreSQL kurulumu için)
│
├── frontend/                 React 19 + Vite denetçi arayüzü
│   └── src/
│       ├── pages/              dokuz ekran
│       ├── components/         dock, tablolar, grafikler, karar sayfası, asistan
│       ├── lib/                API istemcisi, biçimlendirme, TR/EN sözlük
│       └── styles/             tasarım jetonları, bileşenler, dock, asistan
│
├── ml/                       veri üretimi ve model eğitimi
│   ├── src/gus_generator/      sentetik panel üretici (gözlenen ≠ gizil ayrımı)
│   ├── src/gus_model/          quantile başlıkları, konformal, sinyaller, SHAP, rapor
│   ├── data/reference/         GERÇEK açık veri: tarifeler, iklim faktörleri, kaynak kütüğü
│   ├── data/output/            üretilen panel (CSV + Parquet + Excel)
│   ├── models/                 eğitim çıktısı artefaktlar
│   └── reports/                model kartı, metrikler, 12 değerlendirme tablosu
│
├── docs/                     ALGORITMA-AKISI (md + pdf) · MIMARI · RAPOR-ANALIZI
├── assets/                   logo, ikon, banner, akış diyagramı, ekran görüntüleri
│   └── src/                    banner ve ikonun HTML kaynağı (yeniden üretmek için)
└── scripts/                  Windows başlatıcı
```

---

## API

```
GET  /api/health                         hangi motor devrede
GET  /api/dashboard                      dönemin nerede durduğu
GET  /api/inspection-queue               operasyonel kuyruk, filtreli ve sayfalı
GET  /api/companies/{id}                 puan, aralık, sinyaller, kanıt
GET  /api/companies/{id}/history         her dönem, o gün beklenen aralıkla
GET  /api/companies/{id}/signals
POST /api/companies/{id}/review          karar kaydet
GET  /api/companies/{id}/reviews
GET  /api/companies/{id}/audit-history
GET  /api/data-quality                   platformun ne görüp ne göremediği
GET  /api/climate-impact                 tonaj, katkı payı, emisyon, toplayıcılar
GET  /api/cop31/pilot                    pilot yapılandırması
POST /api/cop31/pilot/run                pilotu çalıştır ve kaydet
GET  /api/transparency                   kapsam, ilkeler, politika, motorlar
POST /api/scoring/run                    bir dönemi yeniden puanla
GET  /api/scoring/engines
GET  /api/scoring/policy                 PUT ile eşikler ve ağırlıklar değiştirilir
GET  /api/audit/events                   karar kaydı
GET  /api/audit/verify                   zincirdeki her bağı yeniden hesapla
GET  /api/meta/reference                 filtre değerleri ve etiketler
GET  /api/assistant/status               Gemini anahtarı yapılandırılmış mı
GET  /api/assistant/suggestions          mevcut dönemin cevaplayabileceği sorular
POST /api/assistant/chat                 dönem brifingine dayalı tek tur
```

Türkçe yanıt için `?lang=tr`. Tanınmayan bir dil, hata vermek yerine İngilizceye
düşer; böylece eski bir istemci çalışmaya devam eder.

### Denetim izi

Kararlar eklenir, hiçbir zaman düzenlenmez. Her olay kendisinden önceki olayın
SHA-256 özetini taşır — firma, denetçi, işlem, iki yandaki durum, not ve zaman
damgası özetin içindedir. Geçmiş bir kararı değiştirmek veya silmek, o kaydın ve
**ondan sonraki her bağın** özetini değiştirir; `GET /api/audit/verify` zincirin
kendisiyle uyuşmayı bıraktığı **ilk sıra numarasını** bildirir.

---

## Testler

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

Kapsam: motorun değişmezleri (eksik girdi → *çalıştırılamadı*, aralığın veri
güvenine göre genişlemesi, kapatılan sinyalin puana girmemesi) ve API
sözleşmesinin her uç noktada beklenen şekli döndürmesi.

---

## Ölçülen sonuçlar

> [!WARNING]
> Aşağıdaki sayılar **sentetik** bir panel üzerinde, zamansal bir holdout ile
> ölçülmüştür: 2025Q2'ye kadar eğitim, 2025Q3–Q4 kalibrasyon, 2026Q1–Q2 üzerinde
> **bir kez** ölçüm. Bunlar henüz gerçek beyanlar üzerindeki performansın kanıtı
> değildir.
>
> **Hedefimiz, üretimde kurumun kendi ortamında tutulan gerçek ve
> anonimleştirilmiş beyan verisiyle aynı sonuçlara ulaşmaktır.** Pilot dönemde
> aynı zamansal holdout protokolü — aynı bölümleme, aynı metrikler, aynı bootstrap
> güven aralıkları — gerçek veri üzerinde tekrarlanacak ve ölçümler bu tabloda
> yan yana yayımlanacaktır.

| Ölçüt | GÜS-DEDEKTİV | En iyi basit taban | Kat |
| --- | ---: | ---: | ---: |
| Precision@100 | **0,360** | 0,190 | 4,5× |
| Precision@50 | **0,500** | — | 6,2× |
| PR-AUC | **0,328** | 0,159 | 2,1× |
| Recall@100 | 0,371 | — | — |
| Konformal kapsama (test) | 0,883 | hedef 0,900 | — |
| Beklenen kalibrasyon hatası | 0,022 | — | — |

En yüksek sıradaki 100 dosyanın **36'sında** doğrulanmış eksik beyan vardı;
taban oran %8,08. Eğitim penceresinde yalnızca 246 pozitif örnek bulunduğu için
Precision@100 bootstrap güven aralığıyla birlikte raporlanır: `[0,26 – 0,45]`.

**Veri kümesi:** 600 firma · 14 çeyrek · 8.244 firma-çeyrek gözlemi · 3.439 SKU ·
8 sektör · 20 il · 6 malzeme türü.

Tam model kartı ve 12 değerlendirme tablosu:
[`ml/reports/`](ml/reports/) · [`ml/reports/MODEL_KARTI.md`](ml/reports/MODEL_KARTI.md)

---

## Dokümanlar

| Doküman | İçerik |
| --- | --- |
| [`docs/ALGORITMA-AKISI.md`](docs/ALGORITMA-AKISI.md) | Algoritma akışı — katmanlar, formüller, değişmezler |
| [`docs/ALGORITMA-AKISI.pdf`](docs/ALGORITMA-AKISI.pdf) | Aynısının baskıya uygun 8 sayfalık A4 sürümü |
| [`docs/MIMARI.md`](docs/MIMARI.md) | Sistem mimarisi ve teknoloji seçimlerinin tam gerekçesi |
| [`docs/RAPOR-ANALIZI.md`](docs/RAPOR-ANALIZI.md) | Ön değerlendirme raporunun analizi ve alınan önlemler |
| [`ml/README.md`](ml/README.md) | Veri altyapısı: üretim, doğrulama, kaynak kütüğü |
| [`ml/reports/MODEL_KARTI.md`](ml/reports/MODEL_KARTI.md) | Model kartı: sınırlılıklar, bölümleme, metrikler |
| [`backend/models/README.md`](backend/models/README.md) | Artefakt listesi ve yeniden üretme |

---

## Takım ve lisans

**Takım KinetiX** — TEKNOFEST 2026, Sıfır Atık ve Döngüsel Ekonomi kategorisi.

Bu depo [MIT Lisansı](LICENSE) ile dağıtılmaktadır. `ml/data/reference/` altındaki
açık veriler kendi kaynaklarının koşullarına tabidir; her satırın kaynağı ve
erişim tarihi [`source_registry.csv`](ml/data/reference/source_registry.csv)
içinde kayıtlıdır.
