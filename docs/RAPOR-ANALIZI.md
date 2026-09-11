# Aşama 1 — Şartname ve Rapor İncelemesi

**Tarih:** 2026-09-02 · **Takım:** KinetiX · **Başvuru ID:** 5386692
**İncelenen belgeler:** TEKNOFEST 2026 Sıfır Atık & Döngüsel Ekonomi Yarışması Şartnamesi (17 s.) ·
GÜS-DEDEKTİV Proje Ön Değerlendirme Raporu v1.0 / 30.07.2026 (12 s.)

---

## 0. ACİL — TAKVİM

Şartname Tablo 1 ve raporunuzun kendi §14 takvimi aynı tarihleri veriyor:

| Tarih | Olay | Bugüne kalan |
|---|---|---|
| 21.08.2026 | Ön elemeyi geçen takımların açıklanması | ✅ geçti |
| 26.08 – 09.09.2026 | Çevrimiçi eğitim ve mentorluk | devam ediyor |
| **04.09.2026** | **Proje Sunumu Son Teslim Tarihi** | **2 gün** |
| **09.09.2026** | **Proje Sunumu (Final) — jüri önünde** | **7 gün** |
| 11.09.2026 | Finalistlerin açıklanması | 9 gün |
| 30 Eylül – 4 Ekim 2026 | TEKNOFEST 2026 festivali | — |

Şartname §5.2: **her takım en az 4 kez mentor görüşmesine katılmakla yükümlüdür.**
Bu yükümlülüğün tamamlanıp tamamlanmadığını kontrol edin — eksikse teslimden önce kapatılmalı.

Bundan sonraki tüm öneriler **"2 günde yapılabilir mi?"** filtresinden geçirilerek sıralanmıştır.

---

## 1. Şartname özeti — bağlayıcı gereksinimler

### 1.1 Değerlendirme ağırlıkları

| Aşama | Kriter | Ağırlık |
|---|---|---|
| **Ön eleme** (Tablo 2) | Teknik Yeterlilik ve İşlevsellik | %40 |
| | Tema ile Uyum ve Kamuya Katkı Potansiyeli | %35 |
| | Özgünlük ve Yenilikçilik | %25 |
| **Final** (Tablo 3) | Teknik Yeterlilik ve İşlevsellik | **%35** |
| | Tema ile Uyum ve Kamuya Katkı Potansiyeli | **%30** |
| | Özgünlük ve Yenilikçilik | **%20** |
| | Sunum Kalitesi ve Proje Anlatımı | **%15** |

### 1.2 §10.3 — Teknik teslim paketi (bağlayıcı liste, 8 kalem)

1. Kaynak kodları
2. Kurulum dokümanı
3. Kullanıcı kılavuzu
4. Teknik mimari dokümanı
5. **Veri modeli açıklaması**
6. **Kullanılan kütüphane ve lisans listesi**
7. Demo videosu
8. Çalıştırılabilir uygulama paketi

> "Teslim edilen proje, jüri veya teknik komite tarafından **bağımsız bir ortamda kurulabilir
> ve çalıştırılabilir olmalıdır.**"

**Düzeltme:** "API dokümantasyonu" ve "model kartı" §10.3'te ayrı kalem *değildir* —
sırasıyla §10.8 (API yapısı) ve §10.5 (YZ beyanı) altında zorunludur. İkisi de yapılmalı,
ama teslim listesi bu 8 kalemdir.

### 1.3 §10.4 — Açık kaynak ve lisans uygunluğu

Kullanılan **tüm** açık kaynak yazılım, model, veri seti, API, kütüphane ve üçüncü taraf
bileşenin lisansı **beyan edilmek zorundadır**. GPL, AGPL, ticari kullanımı sınırlı,
attribution gerektiren veya kapalı lisanslı bileşenler **ayrıca** belirtilecektir.

### 1.4 §10.5 — Yapay zekâ kullanımı beyanı (7 zorunlu alan)

Kullanılan modelin **adı · lisansı · eğitim/veri kaynağı · dış API kullanımı · çıktı doğrulama
yöntemi · hata/yanlılık riski · açıklanabilirlik yaklaşımı** proje dokümanında beyan edilecektir.
Bakanlık verisi açık izin olmaksızın üçüncü taraf YZ servislerine gönderilemez.

### 1.5 §10.7 — KVKK

> "Demo ortamlarında **anonimleştirilmiş, sentetik** veya maskeleme uygulanmış veri
> kullanılması **esastır**."

**Bu bizim lehimize:** sentetik dataset şartnamenin tercih ettiği yaklaşımdır, bir eksiklik değildir.
§5.2 ve §5.3 de "sentetik veri setleri … kullanabileceklerdir" diyor — **kaynak belirtmek şartıyla**.

### 1.6 §10.8 / §10.9 — Mimari ve çevresel etki

§10.8: bileşenler, veri akışı, API yapısı, **kullanıcı rolleri**, veritabanı tasarımı,
entegrasyon noktaları ve ölçeklenebilirlik dokümante edilecek; REST API benzeri servis
yaklaşımı ve taşınabilir veri formatları öncelikli.
§10.9: çevresel fayda iddiaları **varsayım, yöntem ve veri kaynağı ile birlikte** sunulacak.

### 1.7 Final ortamı

- §5.3: "**Ortak bir sunucu altyapısı sunulmayacaktır.**"
- §5.4: "Takımlar … geliştirdikleri algoritmayı **kendi bilgisayarlarında** çalıştıracaklardır."

→ Demo **internetsiz, kendi laptopunuzda** çalışmalı. Bu, SQLite + yerel Parquet tercihini
doğruluyor; mimaride bu gerekçeyi açıkça yazın.

### 1.8 Fikri mülkiyet — dikkat

§5.5: "Yarışmacılar tarafından geliştirilen teknolojik ürünlerin **kullanım hakları ve
sahiplikleri Kuruma bedelsiz olarak devredilecektir.**"
§9.2: ticarileştirme/kamu kullanımı için ayrıca protokol düzenlenir.
§10: yarışma sonrası **1 yıl** boyunca tanıtım işbirliği ve projeyi üçüncü taraflara sunmadan
önce Bakanlığa bilgi verme taahhüdü.

### 1.9 Şartname içi çelişkiler — DOĞRULANDI

| # | Çelişki | Nerede |
|---|---|---|
| 1 | **Sunum süresi:** "5 dakikalık sunum süresi" ↔ "7 dakikadan fazla sürmeyecek + 3 dk S/C = toplam 10 dk" | §2.6.2 ↔ §5.4 |
| 2 | **Finalist sayısı:** "75 kişi, **en fazla 15 takım**" ↔ "**ilk 10 proje** seçilecektir" | §4 (s.10) ↔ §5.3 |

Her ikisi de aynı belgede mevcut. **Yorum yapmayın — organizasyondan yazılı teyit isteyin.**
Bu arada **hem 5 hem 7 dakikalık sürüm hazır olmalı.** §5.4 daha spesifik ve final bölümünde
olduğu için 7+3 daha olası; ama 5 dakikalık sürüm olmadan gitmeyin.

---

## 2. Rapor özeti

**Ne:** GEKAP beyan eden işletmelerin beyan ettiği ambalaj tonajının gerçek üretim/ithalat
hacmiyle örtüşmesini değerlendiren, denetim önceliklendirme sistemi.
**Nasıl:** İki LightGBM kantil regresyon modeli (tarihsel + emsal) → Mondrian conformal
kalibrasyon → sekiz sinyal (E1–E8) → üç grup ağırlığı (kalıntı %50 / davranış %37,5 /
dış kanıt %12,5) → dondurulmuş eğri ile 0–100 öncelik puanı.
**Mimari:** 5 katman — arayüz (React 19/Vite) → servis (FastAPI/Pydantic v2/SQLite) →
AI/ML boru hattı (Python 3.13/LightGBM/scikit-learn) → veri (Parquet) → denetlenebilirlik
(hash zinciri, 18 fail-fast kuralı).
**Durum:** Uçtan uca çalışan MVP mevcut. Sentetik 2.500 firma × 8 yıl = 20.000 firma-yıl.
**İkinci değer önerisi:** Ek tahsilatın bir kısmının ~500 bin kayıt dışı atık toplayıcısının
sigortalı istihdamını finanse eden fona yönlendirilmesi.

---

## 3. Puan analizi

| Bölüm | Puan | Kayıp | Yorum |
|---|---|---|---|
| Kısa Özet | 9,00 / 10 | 1,00 | İyi; "%32 doğruluk" ve "bağımsız sinyal" ifadeleri risk |
| Çözülmesi Hedeflenen Problem | 9,00 / 10 | 1,00 | Güçlü; 500 bin rakamı birincil kaynaksız |
| Çözüm Yaklaşımı | 9,50 / 10 | 0,50 | Raporun en güçlü bölümü |
| Yenilikçi Yönler | 9,00 / 10 | 1,00 | Rakip analizi yok |
| **Kullanılacak Teknolojiler** | **0,00 / 5** | **5,00** | **§4'te ayrıntılı analiz** |
| Teknik Mimari | 7,50 / 8 | 0,50 | İyi; kullanıcı rolleri ve VT tasarımı eksik (§10.8) |
| Geliştirme Seviyesi | 7,00 / 8 | 1,00 | Sayısal çelişki (§5.2) güven kırıyor |
| Bugüne Kadar Neler Tamamlandı | 4,50 / 5 | 0,50 | — |
| Gerçek Hayat Uygulaması | 7,00 / 8 | 1,00 | Senaryolar iyi; fon senaryosu spekülatif |
| Beklenen Etki | 7,00 / 8 | 1,00 | Ölçüm yöntemi/varsayım yok → §10.9 ihlali |
| Ölçeklenebilirlik | 4,50 / 5 | 0,50 | — |
| Riskler | 4,50 / 5 | 0,50 | İyi yazılmış |
| Takım Yetkinliği | 3,50 / 4 | 0,50 | 3 kişi = şartname minimumu |
| Proje Takvimi | 4,00 / 4 | 0,00 | Tam puan |
| **Toplam** | **86,00 / 100** | **14,00** | |

**Kaybın %36'sı tek bölümden geliyor.** Teknoloji bölümü düzeltilirse 91/100 seviyesine
çıkılır — ve finalde bu bölüm "Teknik Yeterlilik %35" altında yeniden değerlendirilecek.

---

## 4. "Kullanılacak Teknolojiler 0/5" — kanıta dayalı teşhis

Raporun §5'i 7 maddelik bir teknoloji listesidir. İsimler **var**. Buna rağmen 0 alınmış.
Şartname metniyle karşılaştırınca en olası nedenler:

| # | Bulgu | Şartname dayanağı | Ağırlık |
|---|---|---|---|
| 1 | **Hiçbir bileşenin lisansı beyan edilmemiş.** Listede tek bir lisans adı geçmiyor. | §10.4 — "lisanslarını **beyan etmek zorundadır**" | 🔴 Çok yüksek |
| 2 | **LLM katmanı beyansız.** "Yapay Zekâ Destekli Asistan — getirim tabanlı soru-cevap modülü, ayrı bağlanan üretim (LLM) katmanı" — model adı yok, lisans yok, dış API kullanımı yok, çıktı doğrulama yok, yanlılık riski yok, açıklanabilirlik yok. §10.5'in **7 alanının 7'si de eksik**. | §10.5 | 🔴 Çok yüksek |
| 3 | **Sürüm bilgisi yok.** §5'te yalnızca "React 19" var; Python 3.13 ve Pydantic v2 §6'da geçiyor, §5'te değil. Diğer 15+ bileşenin sürümü yok. | §10.3/§10.4 | 🟠 Yüksek |
| 4 | **Gerekçe ve alternatif yok.** Neden LightGBM (XGBoost/CatBoost değil), neden FastAPI, neden SQLite — hiçbiri yazılmamış. | Teknik yeterlilik | 🟠 Yüksek |
| 5 | **SQLite düz "Veri Tabanı" olarak sunulmuş.** MVP/üretim ayrımı yok. Ulusal ölçekli kamu sistemi iddiasıyla çelişiyor. | §10.8 ölçeklenebilirlik | 🟠 Yüksek |
| 6 | **Performans testi yöntemi yok.** Hiçbir teknoloji için "nasıl test edilecek" yazmıyor. | §10.5 çıktı doğrulama | 🟡 Orta |
| 7 | **Kullanıcı rolleri ve VT tasarımı yok.** §10.8 bunları açıkça istiyor. | §10.8 | 🟡 Orta |
| 8 | Bölüm 5 satır; diğer bölümler 3–4 paragraf. Değerlendirici "yalnızca liste" olarak okumuş olabilir. | — | 🟡 Orta |

**Sonuç:** Bunun bir değerlendirici hatası olduğunu varsaymak risklidir. §10.4 ve §10.5
doğrudan ihlal edilmiş görünüyor; bu iki madde tek başına 0 puanı açıklayabilir.

**Çözüm hazır:** `docs/ARCHITECTURE.md` §4'te 24 teknolojinin her biri için
*hangi işlev / neden / alternatif / sürüm / lisans / hangi veri / nasıl test edilir /
kamu kurulumu / üretimde yerini ne alacak* tablosu bulunuyor. §10.5'in 7 alanı için
ayrı YZ beyanı bloğu da eklenmeli.

---

## 5. En tehlikeli 15 boşluk

Öncelik sırası: **finalde puan kaybettirme × 2 günde düzeltilebilirlik**.

### 🔴 Kritik — teslimden önce mutlaka

**B1. Sayısal çelişki: 8 firma ↔ %32 isabet.**
§10: *"Sentetik test yılında **2.500 firmadan 8'inin** kalibre edilmiş alt sınırın altında
beyanda bulunduğu … tespit edilmiştir"*
§1/§7/§10: *"ilk 100 firmalık dilimde **%32 doğruluk**"*
%32 × 100 = **32 isabet**, ama evrende yalnızca **8** vaka var. Aritmetik olarak imkânsız.
Ayrıca "7 kat" ⇒ prevalans ≈ %4,57 ⇒ 2.500'de ≈ **114** vaka — 8 ile de çelişiyor.
Jüriden biri bu çarpımı yaparsa raporun tüm sayısal güvenilirliği düşer.
→ **Aynı test tanımından tek tutarlı sayı seti üretilmeli.**

**B2. "%32 doğruluk" metrik adı yanlış.**
Bu bir *accuracy* değil, **Precision@100**. Dengesiz sınıfta accuracy zaten anlamsızdır
(hepsine "temiz" derseniz %95+ accuracy alırsınız). Metrik adı düzeltilmeli.

**B3. "Rastgele seçimin yaklaşık yedi katı" — dayanaksız.**
Lift = Precision@K ÷ prevalans. Prevalans, test seti büyüklüğü ve güven aralığı
verilmeden bu sayı savunulamaz. → Prevalans + bootstrap %95 GA ile birlikte verilmeli.

**B4. Lisans listesi yok — §10.4 doğrudan ihlali.**
Teslim paketinde zorunlu kalem. 2 saatte hazırlanabilir.

**B5. YZ beyanı yok — §10.5 doğrudan ihlali.**
7 alanın tamamı eksik. LLM/RAG katmanı için model adı, lisans, dış API kullanımı
(**"kamu verisi dış servise gönderilmiyor" ifadesi kritik**), çıktı doğrulama, yanlılık
riski, açıklanabilirlik yazılmalı.

**B6. "Sekiz bağımsız sinyal" — savunulamaz iddia.**
§1, §3, §4, §8'de tekrarlanıyor. §4'te "**birbirinden kör bağımsız**" deniyor.
Sinyaller aynı beyan ve aynı üretim verisinden türüyor; korelasyonludurlar.
Jüri "bağımsızlığı nasıl test ettiniz?" diye sorarsa cevap yok.
→ **"Sekiz ayrı kanıt sinyali"** olarak değiştirin + korelasyon matrisi + ablation ekleyin.

**B7. "Kapsama garantili" / "%95 hedef kapsama" — aşırı iddia.**
Conformal prediction, değişim-değişmezlik (exchangeability) varsayımı altında
*marjinal* kapsama sağlar; firma-dönem panelinde bu varsayım tartışmalıdır.
→ Doğru ifade: **"belirlenen varsayımlar altında hedef kapsama düzeyi %90 ve test
verisinde gözlenen kapsama oranı %88,7"** gibi — hedef ve gözlenen ayrı verilmeli.

### 🟠 Yüksek — finalde puan kaybettirir

**B8. Analiz birimi firma-YIL — raporun kendi içinde çelişiyor.**
§2 doğru şekilde *"üç aylık dönemler halinde beyan etmek"* diyor.
§1/§3/§7 ise *"her firma-yıl"*, *"2.500 firma × 8 yıl"*.
GEKAP beyanı çeyreklik. Yıllık toplulaştırma, dönem içi kaydırma ve gecikmiş düzeltme
davranışını **görünmez kılar** — ki bunlar sistemin yakalaması gereken en tipik örüntüler.
→ Bu, jürinin GEKAP bilen bir üyesinin ilk soracağı şeydir.

**B9. "Her firma-yıl için iki ayrı LightGBM modeli eğitilir" — teknik olarak imkânsız okunuyor.**
20.000 firma-yıl × 2 = 40.000 model. Kastedilen muhtemelen iki **global/segment** model.
→ Cümle düzeltilmeli: *"iki global kantil model eğitilir ve her firma-dönem kaydına uygulanır."*

**B10. GTİP, ambalaj katsayısı kaynağı gibi kullanılmış.**
§3: *"GTİP bazlı ambalaj katsayı referans tablosu"*. §15 bunun sentetik olduğunu kabul ediyor.
GTİP bir **ürün sınıflandırmasıdır**, ambalaj ağırlığı taşımaz. Ambalaj ağırlığı SKU/ürün
ağacı/BOM'dan gelir. → İfade "GTİP ürün bağlamı sağlar; ambalaj ağırlığı ayrı bir
ağırlık matrisinden gelir" olarak düzeltilmeli.

**B11. Atık toplayıcı fonu, çekirdek değer önerisi olarak sunulmuş.**
§1 "ikili işlev", §4 "**en özgün fark**", §10 ekonomik faydanın yarısı.
GEKAP geliri bütçe kalemine bağlıdır; yönlendirilmesi **mevzuat ve bütçe kararı** gerektirir.
Bakanlık jürisi bunu bilir. §12'deki risk satırı var ama §1 ve §4 hâlâ güçlü iddia kuruyor.
→ **Ayrı bir politika önerisi / belediye pilotu** olarak konumlandırın; ana değer önerisinden
çıkarın. Ana değer önerisi zaten güçlü: *"aynı denetim kapasitesiyle doğru firmayı, daha erken
ve gerekçesiyle incelemek."*

**B12. Çevresel etki ölçüm yöntemi yok — §10.9 ihlali.**
§10 "ton başına önlenen sera gazı emisyonu cinsinden ayrıca **raporlanabilir hale getirilecektir**"
diyor — yani henüz yok. §10.9 varsayım + yöntem + veri kaynağı istiyor.
→ Dataset'teki `Climate_Factors` ve `COP31_Dashboard` bunu hazır veriyor
(EPA WARM v16, kısa ton→metrik ton çevrimi, üç senaryo, belirsizlik notları).

**B13. COP31 raporda hiç geçmiyor.**
Final ağırlığının **%30'u "Tema ile Uyum ve Kamuya Katkı"**. COP31 9–20 Kasım 2026'da
Antalya'da ve başkanlık gündeminin ilk sırasında atık kaynaklı metan var. Bu, en ucuz
puan kazancı. → Dataset'te hazır `COP31_Dashboard` sayfası var.
⚠ Türkiye **ev sahibi**; müzakere başkanlığı **Avustralya ile ortak** — "Türkiye COP31 başkanı" demeyin.

**B14. Rakip analizi yok.**
§4: *"Çoğu önceliklendirme aracı eksik veriyi 0,5 gibi nötr bir değerle doldurur"* —
hangi araçlar? Kaynaksız genelleme. "Rakibimiz yok" izlenimi de risklidir.
→ En az şunlar anılmalı: **VDK-MİHENK** (VDK'nın YZ destekli risk analiz sistemi,
12.08.2026'da devreye alındı), GİB risk analiz sistemleri, KPMG/PwC GEKAP çözümleri,
ERP tabanlı GEKAP modülleri. Bunları *doğrudan rakip / dolaylı / tamamlayıcı / kamu
altyapısı / şirket tarafı* diye sınıflandırın.
🎯 **MİHENK aslında lehinize:** duyuru metninde risk göstergesinin *"tek başına vergisel
uyumsuzluk veya eleştiri anlamına gelmediği"* yazıyor — sizin çerçevenizle birebir aynı.
Devletin gittiği yön ile hizalı olduğunuzu gösterir.

**B15. "~500 bin kayıt dışı atık toplayıcısı" ve "günde 15–20 km" birincil kaynaksız.**
§15 kaynağı "güncel basın haberleri" olarak veriyor. → Ya birincil kaynak bulun ya da
"basında yer alan tahminlere göre" diye açıkça hedge edin.

---

## 6. En güçlü 10 yön — sunumda öne çıkarın

1. **Eksik sinyali nötr değerle doldurmama** ilkesi (§4) — gerçekten ayırt edici ve teknik olarak doğru.
2. **Puanın hüküm değil, gerekçeli sıralama olması** ve bunun her ekranda vurgulanması.
3. **Beş katmanlı tek yönlü mimari**, her katmanın yetkisinin dar tutulması (servis puanı değiştiremez).
4. **Test yılına yalnızca bir kez bakılması** ve kod içi guard ile korunması — metodolojik olgunluk.
5. **Hash zinciri + decision_id + karar günlüğü** — kamu denetim iş akışına uygun izlenebilirlik.
6. **Modelin dondurulup servis başında bir kez yüklenmesi** — üretim yolunda eğitim yok.
7. **Sabit öncelik eğrisi** — aynı firma 100 ve 10.000 firmalık listede aynı puanı alır. Zarif çözüm.
8. **Kendi kör noktalarını raporlaması** (kademeli eksik beyanın zor yakalandığını söylemesi).
9. **Gerekçe kodlarının metne değil koda dayanması** (`STRUCTURAL_SHORTFALL`) — çok dillilik hazır.
10. **Uçtan uca çalışan MVP'nin gerçekten mevcut olması** — §3.4 "çalışan demo zorunludur" şartını karşılıyor.

---

## 7. Kritik karar — sizin vermeniz gerekiyor

Dataset'i **firma-çeyrek** olarak kurdum (B8'i çözmek için). Mevcut kodunuz **firma-yıl**.

| Seçenek | Kazanç | Risk (2 gün) |
|---|---|---|
| **A. Firma-çeyreğe geçin** | B8 çözülür; GEKAP mevzuatıyla birebir uyum; "Teknik Yeterlilik %35"te en büyük tek kazanç | Boru hattı refactor'ü — lag/mevsimsellik özellikleri yeniden yazılır |
| **B. Firma-yıl kalın** | Sıfır refactor; mevcut demo bozulmaz | B8 açık kalır; jüri sorarsa cevap yok |
| **C. İkisi birden** ⭐ | Çeyreklik veri **sunulur** (doğru olan), yıllık toplulaştırma mevcut kodu besler; "çeyrekliğe geçtik, yıllık geriye dönük uyumluluk için duruyor" denir | Düşük — yıllık toplulaştırma sayfasını ben ekleyebilirim |

**Önerim: C.** Yıllık toplulaştırma görünümünü dataset'e eklemem ~20 dakika sürer;
mevcut kodunuz kırılmadan çalışmaya devam eder, sunumda ise doğru olan çeyreklik yapıyı
gösterirsiniz.

---

## 8. 2 günlük eylem sırası

**Gün 1 (03.09)**
1. B4 + B5 — lisans listesi ve YZ beyanı (§10.4/§10.5). **En yüksek getiri/çaba oranı.** (~3 saat)
2. B1 + B2 + B3 — tek tutarlı sayı seti üret; "doğruluk"→"Precision@100"; prevalans + GA ekle. (~3 saat)
3. B6 + B7 — "bağımsız"→"ayrı"; "kapsama garantili"→"hedef ve gözlenen kapsama". Metin taraması. (~1 saat)
4. B11 — atık toplayıcı fonunu ana değer önerisinden ayrı politika önerisine taşı. (~1 saat)

**Gün 2 (04.09) — teslim günü**
5. B13 — COP31 bölümü ekle (dataset'teki dashboard hazır). (~1,5 saat)
6. B12 — çevresel etki ölçüm yöntemi + varsayım + kaynak (Climate_Factors hazır). (~1 saat)
7. B14 — rakip analizi tablosu. (~1,5 saat)
8. §10.3 teslim paketi kontrol listesi — 8 kalemin hepsi tamam mı? Bağımsız ortamda kurulum testi. (~2 saat)
9. Demo videosu + çalıştırılabilir paket.

**05.09 – 08.09 (final hazırlığı)**
10. 7 dk sunum + 5 dk yedek sürüm + 2 dk canlı demo + 3 dk S/C provası
11. Jüri soru bankası ve "söylenmemesi gereken ifadeler" listesi
12. İnternetsiz demo provası (§5.3 — ortak sunucu yok, kendi laptop)

---

## 9. Söylenmemesi gereken ifadeler (sunum ve rapor)

| ❌ Demeyin | ✅ Deyin |
|---|---|
| "Sekiz bağımsız sinyal" | "Sekiz ayrı kanıt sinyali" |
| "%95 kesinlik / garanti" | "Hedef kapsama %90, test verisinde gözlenen kapsama %88,7" |
| "%32 doğruluk" | "Precision@100 = 0,32 (prevalans 0,08; %95 GA …)" |
| "Rastgeleye göre 7 kat" (yalın) | "Lift@100 = 3,1 (prevalans 0,08 üzerinden, bootstrap GA ile)" |
| "Türkiye COP31 başkanı" | "Türkiye ev sahibi ülke; müzakere başkanlığı Avustralya ile ortak" |
| "Beyan düzeltmesi geri dönüşümdür" | "Beyan düzeltmesi ambalaj akışının görünürlüğünü artırır" |
| "X ton CO₂ azalttık" | "Potansiyel senaryo — doğrulanmış etki değildir" |
| "Ek gelir toplayıcılara aktarılacak" | "Ayrı bir politika önerisi olarak belediye pilotuyla test edilebilir" |
| "Türkiye'de rakibimiz yok" | "Kamu denetçisini kullanıcı alan, GEKAP'a özgü doğrudan eşdeğer bir çözüm belgelenmiş şekilde bulunamadı; komşu çözümler şunlardır…" |
| "SQLite ile ulusal ölçekte çalışır" | "SQLite MVP/demo içindir; üretimde PostgreSQL veya kurumun kurumsal veritabanı" |

---

## 10. Organizasyondan resmî teyit istenecekler

1. Final sunum süresi: 5 dk mı, 7 dk + 3 dk S/C mi? (§2.6.2 ↔ §5.4)
2. Finalist sayısı: 10 proje mi, en fazla 15 takım mı? (§5.3 ↔ §4)
3. "Kullanılacak Teknolojiler" bölümünden 0 puan alınmasının gerekçesi
4. §10.3 teslim paketinde ayrı bir "model kartı" ve "API dokümantasyonu" bekleniyor mu?
5. Bakanlığın 25.08'de paylaştığı veri setleri hangi kapsamda — GEKAP beyan verisi içeriyor mu?
