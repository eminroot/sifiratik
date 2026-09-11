# Katkı rehberi

GÜS-DEDEKTİV bir kamu denetim aracıdır. Buradaki kurallar stil tercihi değil,
sistemin güvenilir kalmasının şartıdır.

---

## Önce bunlar

**0–100 puan operasyonel bir inceleme önceliğidir.** İhlal olasılığı değildir.
Arayüzde, API yanıtında, model kartında ve sunumda bu ifade birebir aynı kalır.
Bunu yumuşatan bir değişiklik kabul edilmez.

**Depodaki panel sentetiktir.** Gerçek firma verisi, gerçek VKN veya gerçek
beyan asla depoya girmez — örnek olarak, testte, sabit değer olarak da girmez.

---

## Geliştirme ortamı

```bash
# Servis
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Arayüz
cd frontend
npm install
npm run dev
```

Windows'ta ikisini birden başlatmak için `start.bat`.

Veritabanı ilk açılışta `ml/data/output/csv` altındaki panelden kendini kurar.
Sıfırdan kurmak için:

```bash
cd backend && python -m app.database.gus_import --reset
```

---

## Değiştirilemeyecek altı kural

Bir PR bunlardan birini bozuyorsa, önce bir konu (issue) açıp gerekçesini
tartışın.

1. **Hesaplanamayan özellik, hesaplanmış gibi davranmaz.** Nötr bir değere
   doldurulup gözlenmiş gibi puanlanmaz; ona dayanan kontroller
   *çalıştırılamadı* olur ve nedeni yazılır.

2. **Aralık, kalibrasyon verisi inceldikçe genişler.** Kaydın kendi veri güveni
   konformal gruplama boyutlarından biridir.

3. **Eksik veri aklanma değildir.** Çalıştırılamayan bir kontrolün ağırlığı
   paydadan düşer, sıfır sayılmaz; dayanak kapsamı düşer ve bu denetçiye
   yazıyla bildirilir.

4. **Kimlik özellikleri risk puanına girmez.** İl hiçbir yerde kullanılmaz;
   sektör ve ölçek bandı yalnızca beklenti başlıklarında ve konformal
   gruplamada kullanılır.

5. **Yazan her yeni uç nokta `require_writer` bağımlılığını alır.** Anahtar
   yapılandırılmamışken hiçbir şeyi reddetmez; yapılandırıldığında kapı
   çalışır. Karara ad yazan kod `acting_user(principal, ...)` kullanır —
   istek gövdesindeki adı doğrudan kaydetmez.

6. **Puanı etkileyen her değişiklik zincire yazılır.** Politika değişikliği
   `policy_service.apply_policy` üzerinden geçer; oradan geçmeyen bir yol
   eklenirse skorlar açıklanamaz hale gelir.

Gerekçe metni **şablonludur**. Serbest üretimli bir dil modeli gerekçe
üretmez — aynı girdi aynı cümleyi üretmelidir.

---

## Kod

**Python.** Tip ipuçları (`from __future__ import annotations`), `pathlib`,
dataclass'lar. Puanlama motoru ORM görmez: `ScoringContext` girer,
`ScoreOutcome` çıkar. Yeni bir motor eklerken bu sözleşmeyi koruyun —
`registry.py` seçimi yapar.

**JavaScript.** Fonksiyon bileşenleri, hook'lar. Renk, boşluk ve tipografi
`src/styles/tokens.css` içinden gelir; bileşende sabit renk yazmayın. Renk
yalnızca **durum** anlatır.

**Metin.** Kullanıcıya görünen her dize `src/lib/strings.js` içinde, hem `tr`
hem `en` karşılığıyla bulunur. API'nin yazdığı düz metin `app/i18n.py` içinde.

**Yorumlar** neden'i anlatır, ne'yi değil. Kodun kendisi zaten ne yaptığını
söylüyor.

---

## Testler

```bash
cd backend && python -m pytest
```

Testler elle yazılmış sabit veriyle değil, içe aktarılmış panelle koşar;
kontrol edilmeye değer davranış, motorun **eksik ve tam kayıt karışımıyla** ne
yaptığıdır. Motorun değişmezlerine dokunan her PR, o değişmezi doğrulayan bir
test getirmelidir.

CI ayrıca arayüzü derler (`npm run build`). İkisi de yeşil olmadan birleştirme
yapılmaz.

---

## Commit ve PR

Commit başlığı Türkçe, emir kipi, 72 karakteri geçmeyecek şekilde.
Gövdede **neden** değiştirdiğinizi yazın; diff zaten neyi değiştirdiğinizi
gösteriyor.

```
Konformal grubu incelince global gruba düş

Sektör-ölçek-güven üçlüsünde 40'tan az kalibrasyon kaydı olan gruplarda
aralık gözlenen kapsamayı tutturamıyordu. Artık grup incelince sırayla
daha genişine düşülüyor; test kapsaması 0,84 → 0,88.
```

PR açarken şablondaki kutuları doldurun. Model artefaktlarını değiştiren bir PR,
`ml/reports/MODEL_KARTI.md` ve `ml/reports/metrics.json` dosyalarını da
güncellemelidir — sayılar ile model aynı commit'te yürür.

---

## Model artefaktları

`backend/models/` altındaki dosyalar **bir bütündür**. Tek bir dosyayı
değiştirmeyin; seti bütün olarak yeniden üretin:

```bash
cd ml && python src/train_model.py --export ../backend/models
python src/score_dataset.py --split test --verify
```

`manifest.json` içindeki `feature_order` ve `categories` bağlayıcıdır. Uyuşmazlık
olursa LightGBM yanlış sütunu okur ve saçmadan kendinden emin bir tahmin üretir;
çalışma zamanı bu yüzden manifest olmadan yüklenmeyi reddeder.

---

## Güvenlik

Güvenlik açığı bildirimleri için [`SECURITY.md`](SECURITY.md).
