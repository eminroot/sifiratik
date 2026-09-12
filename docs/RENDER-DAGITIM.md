# Render'a dağıtım

GÜS-DEDEKTİV'i Render üzerinde yayına almak için adım adım kılavuz. Depoda
`Dockerfile` ve `render.yaml` hazır olduğu için Render'da elle kurulacak bir şey
yoktur: blueprint dosyası okunur, servis kendini kurar.

Baştan sona **15–20 dakika** sürer; bunun 5–8 dakikası ilk imaj derlemesidir.

---

## Başlamadan önce

| Gereken | Not |
|---|---|
| GitHub hesabı | `eminroot/zerowaste` deposuna erişimi olan hesap |
| Kredi kartı | Standard örnek ücretlidir; Render kartı kayıt sırasında ister |
| 15–20 dakika | İlk derleme beklemeli bir adımdır |

Dağıtılacak dal **`main`**, commit **`51c0bc9`** veya üstü olmalıdır. Kontrol:

```bash
git log --oneline -1 origin/main
```

Çıktıda `Dağıtımı hazırla ve ölçek varsayan biçimlendirmeleri düzelt` görünmelidir.

---

## 1. GitHub ile Render'a giriş

1. <https://dashboard.render.com/register> adresine gidin.
2. **GitHub** düğmesine basın.
3. GitHub, Render'a izin vermenizi ister — **Authorize Render** deyin.

Render hesabınız GitHub e-postanızla açılır. Bu adımda henüz kart istenmez.

> Aynı e-postayla daha önce Render hesabı açtıysanız Render sizi doğrudan o
> hesaba alır, yeni hesap oluşturmaz.

---

## 2. Render'a depo erişimi verin

Giriş sırasında Render, GitHub uygulamasını kurmanızı isteyecektir. İstemezse
<https://github.com/apps/render/installations/new> adresinden elle yapın.

**Repository access** bölümünde iki seçenek vardır:

- **All repositories** — hepsi
- **Only select repositories** — seçtikleriniz ← **bunu seçin**, sonra
  `eminroot/zerowaste` deposunu ekleyin

**Install** deyin. Yalnızca gereken depoya erişim vermek, sonradan geri almak
zorunda kalmayacağınız tek ayardır.

---

## 3. Blueprint'i oluşturun

1. Render panosunda sağ üstten **New +** > **Blueprint**.
2. Depo listesinden `eminroot/zerowaste` yanındaki **Connect** düğmesine basın.
3. Karşınıza çıkan form üç şey sorar:

| Alan | Girilecek değer |
|---|---|
| **Blueprint Name** | `gus-dedektiv` (serbest, yalnızca panoda görünür) |
| **Branch** | `main` |
| **Blueprint Path** | `render.yaml` — zaten varsayılandır, dokunmayın |

Render dosyayı okur ve oluşturacağı kaynakları listeler. Görmeniz gereken:

```
gus-dedektiv     Web Service     Docker     Frankfurt     Standard
```

Başka bir kaynak (veritabanı, Redis, ikinci servis) **görünmemelidir**. Görünüyorsa
yanlış dalı ya da yanlış dosyayı seçmişsinizdir.

---

## 4. İki ortam değişkeni — dikkatli olun

`render.yaml` iki değişkeni `sync: false` ile işaretler, yani değerlerini depoya
yazmaz, size sorar. Formda ikisi de karşınıza çıkar.

### İkisini de BOŞ bırakın.

Boş bırakmak çalışan bir yapılandırmadır, eksik bir yapılandırma değil. Render
boş kabul etmezse **tek boşluk karakteri** yazın — kod her ikisini de kırpar,
sonuç boşla aynıdır.

| Değişken | Boş bırakılırsa | Yer tutucu yazılırsa |
|---|---|---|
| `API_KEYS` | Yazan uç noktalar açık kalır; jüri karar kaydedebilir | **Servis açılmaz.** `key:user` biçiminde olmayan her değer servisi başlangıçta durdurur |
| `GEMINI_API_KEY` | Asistan paneli görünmez, gerisi normal çalışır | Panel görünür ve ilk soruda hata verir |

> **`API_KEYS` alanına `x`, `change-me` ya da benzeri bir şey yazmayın.**
> Kod, bozuk bir anahtar girdisini atlamak yerine servisi durdurur: kapalı
> sanırken açık kalmış bir kapı olmasın diye böyle yazılmıştır. Sonucu, açılmayan
> bir servis ve `API_KEYS entry 1 is not in key:user form` hatasıdır.

Gemini anahtarını sonradan eklemek isterseniz 8. adıma bakın.

---

## 5. Deploy Blueprint

Listeyi doğruladıktan sonra **Deploy Blueprint** düğmesine basın.

Render kartınızı burada ister, çünkü `render.yaml` ücretli bir örnek tipi
belirtir. Kart bilgilerini **Render'ın kendi ödeme formuna siz girin.**

### Ücret

| Kalem | Aylık |
|---|---|
| Standard web servisi (1 CPU, 2 GB) | **25 USD** |
| Hobby çalışma alanı | 0 USD |

Çalışma alanı planını yükseltmeniz **gerekmez**. Render'da iki ayrı katman
vardır — çalışma alanı planı ve servis hesaplama planı — ve ücretli bir servis
çalıştırmak için Hobby çalışma alanı yeterlidir.

Daha ucuza denemek isterseniz Render panosunda servisin **Settings > Instance
Type** ayarını **Starter**'a (0,5 CPU / 512 MB, 7 USD) çekebilirsiniz. Puanlama
300 MB'a yaklaştığı için sınıra yakın çalışır ama ayağa kalkar.

---

## 6. İlk derlemeyi izleyin

Derleme 5–8 dakika sürer. Kayıtlarda sırayla şunları görürsünüz:

```
==> Building Docker image...
  npm ci                                  (arayüz bağımlılıkları)
  vite build                              (arayüz derlemesi)
  pip install -r requirements.txt         (servis bağımlılıkları)
  python -m app.database.gus_import       (veritabanı imaja tohumlanıyor)
    2026Q2: 600 scored by ml in ... ms
==> Build successful
==> Deploying...
INFO:     Serving the interface from /app/frontend/dist
WARNING:  Writing endpoints are OPEN: no API_KEYS configured.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:10000
==> Your service is live 🎉
```

Bu satırların anlamı:

- **`600 scored by ml`** — model motoru derleme sırasında çalıştı, veritabanı
  imaja tohumlandı. Açılış artık hazır bir veritabanını açmaktan ibaret.
- **`Serving the interface from /app/frontend/dist`** — arayüz bulundu ve
  API ile aynı adresten servis ediliyor.
- **`Writing endpoints are OPEN`** — beklenen uyarı; 4. adımda bilerek böyle
  bıraktınız.

Derleme için 120 dakika sınırı vardır; bu dağıtım onun çok altındadır.

---

## 7. Yayındaki sürümü doğrulayın

Adresiniz `https://gus-dedektiv.onrender.com` biçiminde olacak; kesin adresi
panonun üstünde görürsünüz.

Sırayla şunları açın:

| Adres | Beklenen |
|---|---|
| `/api/health` | `{"status":"ok","engine":"ml","model_version":"gus-ml-1.0.0","writes":"open"}` |
| `/` | Genel görünüm, 600 firma |
| `/queue` | Denetim kuyruğu, dolu tablo |
| `/pilot` | 8. adımda `272 TL at stake` — `0.0M TL` **değil** |
| `/audit-trail` | Zincir `Intact`, 599 karar |
| `/docs` | OpenAPI arayüzü |

**En önemli kontrol `engine":"ml"`.** `"engine":"mock"` görüyorsanız model
artefaktları imaja girmemiş demektir; kural motoru devrededir ve puanlar
farklıdır.

Bir de derin bağlantı deneyin: `/queue` adresini açıp **sayfayı yenileyin**.
Kuyruk yeniden gelmelidir. 404 alıyorsanız arayüz tek kökenden servis
edilmiyordur.

---

## 8. Gemini asistanını sonradan açmak (isteğe bağlı)

1. <https://aistudio.google.com/apikey> adresinden anahtar alın.
2. Render panosunda servis > **Environment** > `GEMINI_API_KEY` satırını bulun.
3. Gerçek anahtarı yapıştırın, **Save, rebuild, and deploy** deyin.

Asistan paneli sağ altta belirir. Her soru sizin anahtarınızdan ücretli bir
çağrıdır; `render.yaml` toplam tavanı dakikada 30 soruya sabitler.

> Tavan kişi başına değil, **hepsi için toplamdır.** Servis, ters vekil arkasında
> bir ziyaretçiyi diğerinden ayırmak için çağıranın kendi yazdığı bir başlığa
> güvenmek zorunda kalacağı için bunu denemez. Sonuç, faturanızdaki en kötü
> durumun bilinir olmasıdır.

---

## 9. Jüriye vermeden önce

- [ ] `/api/health` `engine":"ml"` diyor
- [ ] `/pilot` sayfasında tutar `272 TL`, `0.0M TL` değil
- [ ] `/queue` yenilendiğinde 404 vermiyor
- [ ] Bir firmada **Record decision** çalışıyor, karar `/audit-trail` sayfasında görünüyor
- [ ] EN/TR düğmesi çalışıyor

### Bilmeniz gereken iki şey

**Yazan uç noktalar herkese açık.** Adresi bulan herkes karar kaydedebilir ve
puanlama politikasını değiştirebilir. Jürinin düğmelere basabilmesi için bilerek
böyle bırakıldı. Kapatmak isterseniz:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Çıkan değeri Render panosunda `API_KEYS` alanına `üretilen-değer:aydin.m`
biçiminde yazın. Biçim **tam olarak** `anahtar:denetçi` olmalıdır; başka bir şey
servisi durdurur. Anahtar tanımlandığı anda kararı imzalayan, istek gövdesinin
iddia ettiği isim değil, anahtarın sahibidir. Okuma her durumda açık kalır.

**Her dağıtım veritabanını sıfırlar.** Veritabanı imaja gömülü geldiği için her
dağıtım temiz ve bilinen bir gösteri durumundan başlar. Çalışan servis üzerinde
kaydedilen kararlar bir sonraki dağıtıma kadar durur — **jüri değerlendirirken
`main` dalına push yapmayın**, çünkü `autoDeployTrigger: commit` ayarı yeni bir
dağıtım başlatır ve o ana kadar kaydedilen kararlar silinir.

Değerlendirme sırasında otomatik dağıtımı durdurmak için: servis >
**Settings** > **Auto-Deploy** > **No**.

---

## Sorun giderme

### Derleme `npm ci` adımında kırılıyor
`frontend/package-lock.json` ile `package.json` uyuşmuyordur. Yerelde
`npm install` çalıştırıp değişen kilit dosyasını commit'leyin.

### Derleme `gus_import` adımında kırılıyor
Panel CSV'leri depoda eksiktir. Kontrol:

```bash
git ls-files ml/data/output/csv | wc -l   # 9 olmalı
```

### `"engine":"mock"` görünüyor
Model artefaktları imaja girmemiş. Kontrol:

```bash
git ls-files backend/models | wc -l       # 16 olmalı
```

### Servis açılmıyor, kayıtta `API_KEYS entry 1 is not in key:user form`
4. adımdaki tuzağa düştünüz. Render panosunda **Environment** > `API_KEYS`
değerini tamamen silin ya da `anahtar:denetçi` biçimine getirin, sonra
**Save, rebuild, and deploy**.

### Sayfa açılıyor ama boş
Tarayıcı, bir önceki dağıtımın `index.html` dosyasını önbellekten veriyordur.
Sert yenileyin (Ctrl+Shift+R). Sürekli oluyorsa bildirin: kabuk `no-cache` ile
gönderiliyor, tekrarlaması beklenmez.

### Dağıtım sağlık kontrolünde takılıyor
`healthCheckPath` `/api/health` olarak ayarlıdır ve servis `0.0.0.0:$PORT`
adresine bağlanır. Kayıtlarda `Uvicorn running on http://0.0.0.0:10000`
satırını arayın; yoksa servis hiç açılmamıştır ve asıl hata onun üstündedir.

---

## Değiştirmek isteyebileceğiniz ayarlar

Hepsi `render.yaml` içindedir; değiştirip `main` dalına push etmek yeterlidir.

| Ayar | Şu an | Anlamı |
|---|---|---|
| `region` | `frankfurt` | Türkiye'ye en yakın Render bölgesi |
| `plan` | `standard` | 1 CPU / 2 GB. `starter` daha ucuz, sınıra yakın |
| `autoDeployTrigger` | `commit` | Her push yeni dağıtım. `off` durdurur |
| `ASSISTANT_REQUESTS_PER_MINUTE` | `30` | Tüm ziyaretçiler için toplam tavan |
| `healthCheckPath` | `/api/health` | Render'ın canlılık kontrolü |

---

## Kaynaklar

- [Render Blueprints (IaC)](https://render.com/docs/infrastructure-as-code)
- [Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- [Docker on Render](https://render.com/docs/docker)
- [Web Services](https://render.com/docs/web-services)
- [Compute Plans](https://render.com/docs/compute-plans)
- [Deploys](https://render.com/docs/deploys)
- [GitHub entegrasyonu](https://render.com/docs/github)
