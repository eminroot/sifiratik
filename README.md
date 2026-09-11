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

Bu proje, GEKAP beyanlarındaki olası uyumsuzlukları **farklı kamu verileriyle
karşılaştırarak** denetlenmesi gereken firmaları önceliklendiren, **açıklanabilir**
bir karar-destek sistemidir. Nihai karar her zaman **denetçi tarafında kalır**;
skorlar **TreeSHAP** ile açıklanır ve eksik veri doldurulmaz — *çalıştırılamadı*
olarak işaretlenip nedeniyle birlikte denetçiye bildirilir.

---

## İçindekiler

- [Problem](#problem)
- [Ne yapar, ne yapmaz](#ne-yapar-ne-yapmaz)
- [Prototip akışı](#prototip-akışı)
- [Açıklanabilirlik](#açıklanabilirlik-her-puan-neden-o-puan)
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

## Prototip akışı

Bir denetçinin ekranda izlediği yol, baştan sona. Dokuz ekranın tamamı çalışan
prototipten alınmıştır; arayüz **açık ve koyu temada**, **Türkçe ve İngilizce**
çalışır.

<div align="center">

<h3>1 · Genel görünüm</h3>

Dönem nerede duruyor: kaç firma puanlandı, öncelik nasıl dağıldı, risk altındaki
tonaj ve katkı payı ne kadar. Denetçi güne buradan başlar.

<img src="assets/ekran-goruntuleri/acik/01-genel-gorunum.png" alt="Genel görünüm ekranı" width="88%">

<h2>↓</h2>

<h3>2 · Denetim kuyruğu</h3>

600 firma, öncelik puanına göre sıralı. Her satır başlıca gerekçesini, veri
kalitesini ve iş akışı durumunu taşır; sektör, il, dönem ve bant üzerinden
filtrelenir.

<img src="assets/ekran-goruntuleri/acik/02-kuyruk.png" alt="Denetim kuyruğu ekranı" width="88%">

<h2>↓</h2>

<h3>3 · Firma dosyası</h3>

Tek bir firma-çeyrek kaydı: 0–100 öncelik puanı, **beklenen aralık** ile beyanın
karşılaştırması, açıklanamayan tonaj ve sonucun künyesi — hangi motor, hangi
model sürümü, hangi politika.

<img src="assets/ekran-goruntuleri/acik/03-firma-dosyasi.png" alt="Firma dosyası ekranı" width="88%">

<h2>↓</h2>

<h3>4 · Gerekçe paneli</h3>

Puanın **neden o puan** olduğu. Sekiz kontrolün tamamı, her birinin TreeSHAP
katkısı, ağırlığı ve durumu. `E7`'ye dikkat: **çalıştırılamadı** — ve sessizce
temiz sayılmadığı kutunun içinde yazıyor.

<img src="assets/ekran-goruntuleri/acik/10-gerekce-paneli.png" alt="Gerekçe paneli" width="88%">

<h2>↓</h2>

<h3>5 · Veri kalitesi</h3>

Platformun ne görüp ne göremediği. Hangi alanlar eksik, hangi kontroller bu
yüzden çalışamıyor, dayanak kapsamı ne durumda. Denetçi, puana ne kadar
güvenebileceğini buradan tartar.

<img src="assets/ekran-goruntuleri/acik/05-veri-kalitesi.png" alt="Veri kalitesi ekranı" width="88%">

<h2>↓</h2>

<h3>6 · Karar ve denetim izi</h3>

Denetçi kararını yazar — incele, açıklandı-uygun, veri talep et, ertele.
Karar **eklenir, hiçbir zaman düzenlenmez**: her olay bir öncekinin SHA-256
özetini taşır ve `/api/audit/verify` zincirin tamamını yeniden hesaplar.

<img src="assets/ekran-goruntuleri/acik/08-denetim-izi.png" alt="Denetim izi ekranı" width="88%">

</div>

<details>
<summary><b>Diğer üç ekran</b></summary>

<br>

<div align="center">

**Firma geçmişi** — her dönem, o gün beklenen aralığın içinde

<img src="assets/ekran-goruntuleri/acik/04-firma-gecmisi.png" width="88%">

<br><br>

**COP31 etki paneli** — doğrulanabilir tonaj, katkı payı, emisyon ve senaryolar

<img src="assets/ekran-goruntuleri/acik/06-etki-paneli.png" width="88%">

<br><br>

**Şeffaflık** — kapsam, ilkeler, aktif politika ve devredeki motor

<img src="assets/ekran-goruntuleri/acik/09-seffaflik.png" width="88%">

</div>

</details>

<details>
<summary><b>Koyu tema</b></summary>

<br>

<div align="center">

<img src="assets/ekran-goruntuleri/koyu/01-genel-gorunum.png" width="88%">

<br><br>

<img src="assets/ekran-goruntuleri/koyu/10-gerekce-paneli.png" width="88%">

<br><br>

<img src="assets/ekran-goruntuleri/koyu/02-kuyruk.png" width="88%">

</div>

</details>

---

## Açıklanabilirlik: her puan neden o puan

Bir denetçiyi yanlış kapıya gönderen şey yanlış puan değildir; **gerekçesi
okunamayan** puandır. Bu yüzden platformun iki kuralı var.

### Her skor TreeSHAP ile açıklanır

Katkılar, **gerçekten çalışan model üzerinde** TreeSHAP ile hesaplanır, sinyal
düzeyine toplanır ve şablonlu cümlelere dökülür. Panel her kontrolün puana kaç
puan kattığını yüzdesiyle gösterir.

Gerekçe metni **şablonludur; serbest üretimli dil modeli kullanılmaz.** Aynı
girdi aynı cümleyi üretir ve her cümle arkasındaki sayıyı taşır:

> *"Gümrük satırları 2.125 t ambalaj ima ediyor (aralığın %67'si kapsandı),
> beyan 1.328 t — aralığın %38 altında."*

Bu, bir denetçinin dosyayı açtığında **doğrulayabileceği** bir cümledir.
Halüsinasyon riski yoktur, çünkü üreten bir dil modeli yoktur.

### Eksik veri doldurulmaz — işaretlenir ve denetçiye bildirilir

Hesaplanamayan bir özellik **eksik bırakılır**. Nötr bir değere doldurulup
gözlenmiş gibi puanlanmaz. Ona dayanan kontroller üç durumdan üçüncüsünü alır:

| Durum | Puana etkisi | Denetçiye ne denir |
| --- | --- | --- |
| 🔴 **Tetiklendi** | Kendi ağırlığıyla girer | Eşik neden aşıldı, hangi sayılarla |
| 🟢 **Sessiz** | Sıfır katkıyla girer | Kontrol çalıştı, eşik aşılmadı |
| ⚪ **Çalıştırılamadı** | **Ağırlığı paydadan düşer — sıfır sayılmaz** | Hangi girdi eksik, bu yüzden ne bilinemiyor |

Bunun yerine **dayanak kapsamı** düşer ve bu oran puanın hemen yanında yazılır.
Panel, çalıştırılamayan kontrolü kelimelerle anlatır — örneğin:

> *"Bu dönemi kapsayan bir saha kaydı yok. Bu kontrolün çalıştırılamadığı
> dosyalar daha sık doğrulanmış eksik beyan taşıdığı için, kontrolün yokluğu
> önceliği düşürmedi — yükseltti."*
>
> ⚪ **Değerlendirilmedi ve temiz sayılmadı.**

**Eksik veri aklanma değildir.** Çalıştırılamayan bir kontrol puan taşımaz, ama
katkı taşıyabilir: model, kontrol edilemeyen dosyaların daha sık eksik beyan
taşıdığını veriden öğrenir. Denetçi bunu sessiz bir boşluk olarak değil, yazılı
bir uyarı olarak görür.

---

## Algoritma akışı

> 📄 **Ayrı doküman:** [`docs/ALGORITMA-AKISI.md`](docs/ALGORITMA-AKISI.md) ·
> 🖨️ **Baskıya uygun PDF:** [`docs/ALGORITMA-AKISI.pdf`](docs/ALGORITMA-AKISI.pdf)

```
┌────────────────────────────────────────────────────────────────────────┐
│ K0 · VERİ KAYNAKLARI                                kurum içinde kalır │
├────────────────────────────────────────────────────────────────────────┤
│ GİB GEKAP beyannamesi · Ambalaj Bilgi Sistemi · TÜİK serileri          │
│ Ticaret Bakanlığı GTİP · Sıfır Atık Bilgi Sistemi                      │
│ önceki denetim kayıtları · MVP'de: sentetik panel                      │
│                                                                        │
│ Sistem veri TOPLAMAZ. Kurumun kendi verisini kendi                     │
│ ortamında değerlendirir; dışarıya kayıt göndermez.                     │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  toplu yükleme · kurum içi API
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ K1 · ALIM ve DOĞRULAMA                                       ingestion │
├────────────────────────────────────────────────────────────────────────┤
│ şema doğrulama · VKN → firm_token · birim normalizasyonu               │
│ veri kalite puanı · eksik alan tespiti · veri sürümü damgası           │
│                                                                        │
│ Çıktı: sürümlenmiş panel. Her satırda data_source_type,                │
│ generation_method ve source_ids zorunlu.                               │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  firma-çeyrek paneli
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ K2 · ÖZELLİK ÜRETİMİ                                     feature store │
├────────────────────────────────────────────────────────────────────────┤
│ gecikmeli beyan değerleri · emsal istatistikleri (t−1)                 │
│ ürün ağacından beklenti · dış ticaret dengesi · mevsimsellik           │
│ kullanılabilirlik bayrakları f_avail_sN                                │
│                                                                        │
│ İLERİYE BAKIŞ YASAĞI burada zorunlu kılınır: t anındaki bir            │
│ özellik yalnızca t'ye kadar bilinen veriden hesaplanır.                │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  özellik matrisi
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ K3 · BEKLENTİ MODELİ                                 LightGBM quantile │
├────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────┐   ┌─────────────────────────┐              │
│ │ Tarihsel başlık         │   │ Emsal başlık            │              │
│ │ q05 / q50 / q95         │   │ q05 / q50 / q95         │              │
│ │ firmanın kendi geçmişi  │   │ KENDİ GEÇMİŞİ GİRMEZ    │              │
│ └────────────┬────────────┘   └────────────┬────────────┘              │
│              └───────────────┬──────────────┘                          │
│                              ▼                                         │
│         harman: log uzayında ağırlıklı ortalama, w = 0,95              │
│         Mondrian CQR: (sektör, ölçek, veri güveni)                     │
│         grup incelirse → sırayla daha genişine, sonunda global         │
│                                                                        │
│ Çıktı: kalibre edilmiş aralık [q05, q95]. Aralık, zayıf                │
│ kalibrasyonlu gruplarda GENİŞLER.                                      │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  beklenen aralık + beyan
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ K4 · SEKİZ KANIT SİNYALİ ve BİRLEŞTİRME                        E1 … E8 │
├────────────────────────────────────────────────────────────────────────┤
│ ham istatistik → eğitim penceresi yüzdelik rampası → 0–100             │
│ LightGBM tohum topluluğu (5 üye), log-odds ortalaması                  │
│ izotonik kalibrasyon → referans yüzdelik → 0–100                       │
│ çalıştırılamayan sinyalin ağırlığı PAYDADAN DÜŞER                      │
│                                                                        │
│ Çıktı: öncelik puanı, dayanak kapsamı ve her sinyalin durumu:          │
│ tetiklendi · sessiz · çalıştırılamadı                                  │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  puan + sinyal durumları
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ K5 · AÇIKLAMA ve KARAR KAYDI                     TreeSHAP + hash-chain │
├────────────────────────────────────────────────────────────────────────┤
│ TreeSHAP katkısı → sinyal düzeyi → şablonlu gerekçe cümlesi            │
│ decision_id · model_version · data_version                             │
│ SHA-256 hash-chain denetim kaydı · itiraz izi                          │
│                                                                        │
│ Gerekçe metni ŞABLONLUDUR; serbest üretimli dil modeli                 │
│ kullanılmaz. Aynı girdi aynı cümleyi üretir.                           │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  REST / JSON
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ K6 · API ve DENETÇİ ARAYÜZÜ                            FastAPI · React │
├────────────────────────────────────────────────────────────────────────┤
│ kuyruk · dosya detayı · gerekçe paneli · veri güven ekranı             │
│ denetçi kararı · denetim izi · COP31 etki paneli · şeffaflık           │
│                                                                        │
│ Motor değişse bile sözleşme değişmez: kural motoru ve model            │
│ motoru aynı ScoreOutcome şeklini döndürür; yanıt hangisinin            │
│ ürettiğini söyler.                                                     │
└────────────────────────────────────────────────────────────────────────┘
```

### Bir kayıt nasıl puanlanır

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1 · BAĞLAM TOPLANIR                                                    │
├────────────────────────────────────────────────────────────────────────┤
│ Motor veritabanını hiç görmez. Kendisine ScoringContext verilir:       │
│ firma · beyan geçmişi · emsal kohortu · saha gözlemleri                │
│ GTİP satırları · veri kalitesi — düz veri sınıfları olarak.            │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2 · ÖZELLİK SATIRI KURULUR                                             │
├────────────────────────────────────────────────────────────────────────┤
│ manifest.feature_order BAĞLAYICIDIR; çalışma zamanı matrisi            │
│ ondan yeniden kurar, uyuşmazsa yüklenmeyi reddeder.                    │
│                                                                        │
│ Hesaplanamayan bir özellik EKSİK BIRAKILIR — nötr bir değere           │
│ doldurulup gözlenmiş gibi puanlanmaz.                                  │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3 · BEKLENEN ARALIK ÜRETİLİR                                           │
├────────────────────────────────────────────────────────────────────────┤
│ İki LightGBM quantile başlığı: biri firmanın kendi geçmişinden,        │
│ biri emsalinden ve üretiminden (kendi geçmişi bu başlığa girmez).      │
│                                                                        │
│ ŷ      = exp( w·log1p(ŷ_hist) + (1−w)·log1p(ŷ_peer) ) − 1              │
│ [a, b] = ŷ ± konformal_genişlik( sektör, ölçek, veri_güveni )          │
│ w = 0,95                                                               │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 4 · SEKİZ KONTROL ÇALIŞTIRILIR                                 E1 … E8 │
├────────────────────────────────────────────────────────────────────────┤
│ Her kontrol için sorulan tek soru: gereken girdi var mı?               │
└─────────────────┬───────────────────────────────────┬──────────────────┘
                  │ girdi var                         │ girdi yok
                  ▼                                   ▼
  ┌────────────────────────────────┐  ┌────────────────────────────────┐
  │ TETİKLENDİ / SESSİZ            │  │ ÇALIŞTIRILAMADI                │
  ├────────────────────────────────┤  ├────────────────────────────────┤
  │ 0–100 sinyal puanı üretilir.   │  │ Ağırlığı PAYDADAN DÜŞER —      │
  │ Kontrol, puana KENDİ           │  │ sıfır sayılmaz. Dayanak        │
  │ AĞIRLIĞIYLA girer. Sessiz bir  │  │ kapsamı düşer ve durum,        │
  │ kontrol sıfır katkıyla girer.  │  │ nedeniyle birlikte DENETÇİYE   │
  │                                │  │ YAZIYLA bildirilir.            │
  └────────────────┬───────────────┘  └────────────────┬───────────────┘
                   │                                   │
                   └─────────────────┬─────────────────┘
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 5 · PUAN BİRLEŞTİRİLİR                                                 │
├────────────────────────────────────────────────────────────────────────┤
│ Çalışabilen kontrollerin ağırlıklı ortalaması, EN GÜÇLÜ TEK            │
│ BULGUYLA sabit bir oranda harmanlanır.                                 │
│                                                                        │
│ ağırlıklı_ortalama = Σ( aᵢ·wᵢ·sᵢ ) / Σ( aᵢ·wᵢ )                        │
│ puan = (1 − p) · ağırlıklı_ortalama + p · en_güçlü ,  p = 0,35         │
│                                                                        │
│ aᵢ = 1 kontrol çalıştıysa, 0 çalıştırılamadıysa                        │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 6 · GEREKÇE YAZILIR                                                    │
├────────────────────────────────────────────────────────────────────────┤
│ TreeSHAP katkısı, GERÇEKTEN ÇALIŞAN MODEL üzerinde hesaplanır,         │
│ sinyal düzeyine toplanır ve şablonlu cümlelere dökülür.                │
│                                                                        │
│ Serbest üretimli dil modeli kullanılmaz: aynı girdi aynı               │
│ cümleyi üretir ve her cümle arkasındaki sayıyı taşır.                  │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 7 · KARAR KAYDI ZİNCİRE EKLENİR                                        │
├────────────────────────────────────────────────────────────────────────┤
│ Denetçinin kararı eklenir, hiçbir zaman düzenlenmez.                   │
│                                                                        │
│ digestₙ = SHA256( digestₙ₋₁ ‖ firma ‖ denetçi ‖ işlem ‖                │
│                   önceki_durum ‖ yeni_durum ‖ not ‖ zaman )            │
│                                                                        │
│ /api/audit/verify zincirin uyuşmayı bıraktığı İLK SIRA                 │
│ NUMARASINI bildirir.                                                   │
└────────────────────────────────────────────────────────────────────────┘
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
│   └── pdf/                    PDF'in HTML kaynağı (tek kaynak, iki çıktı)
│
├── assets/                   logo, ikon, banner
│   ├── ekran-goruntuleri/      acik/ ve koyu/ — dokuz ekran, iki tema
│   └── src/                    banner ve ikonun HTML kaynağı
│
├── .github/                  CI iş akışı, konu ve PR şablonları, dependabot
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
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Katkı rehberi ve değiştirilemeyecek dört kural |
| [`SECURITY.md`](SECURITY.md) | Açık bildirimi ve prototipin bilinen sınırları |

---

## Takım ve lisans

**Takım KinetiX** — TEKNOFEST 2026, Sıfır Atık ve Döngüsel Ekonomi kategorisi.

Katkı vermek isteyenler için [`CONTRIBUTING.md`](CONTRIBUTING.md); güvenlik
açığı bildirimi için [`SECURITY.md`](SECURITY.md). Atıf bilgisi
[`CITATION.cff`](CITATION.cff) içindedir.

Bu depo [MIT Lisansı](LICENSE) ile dağıtılmaktadır. `ml/data/reference/` altındaki
açık veriler kendi kaynaklarının koşullarına tabidir; her satırın kaynağı ve
erişim tarihi [`source_registry.csv`](ml/data/reference/source_registry.csv)
içinde kayıtlıdır.
