# Güvenlik

## Sürümler

| Sürüm | Destek |
| --- | --- |
| `main` | ✅ |
| Diğer daller | ❌ |

Bu bir **MVP / prototiptir**. Üretim kurulumu için tasarlanmış bir dağıtım
paketi değildir; kurum ortamına alınmadan önce §Bilinen sınırlar okunmalıdır.

## Açık bildirimi

Güvenlik açığını **herkese açık bir konu (issue) olarak açmayın.**
GitHub üzerinden **Security → Report a vulnerability** ile özel bildirim
gönderin, ya da depo sahibiyle doğrudan iletişime geçin.

Bildiriminizde şunlar olsun: etkilenen dosya veya uç nokta, yeniden üretme
adımları, gözlenen ve beklenen davranış, etkisine dair değerlendirmeniz.

İlk yanıt için hedefimiz **3 iş günü**, düzeltme planı için **10 iş günüdür**.

## Bilinen sınırlar

Prototipin bilerek yapmadığı ve kurum kurulumunda karşılanması gerekenler:

- **Kimlik doğrulama ve yetkilendirme yoktur.** API açıktır; denetçi kimliği
  istek gövdesinden gelir. Kurum kurulumunda kurumsal SSO ve rol tabanlı erişim
  arkasına alınmalıdır.
- **CORS geliştirme için gevşektir** (`CORS_ORIGINS` ile daraltılır).
- **SQLite yalnızca MVP içindir.** Üretimde PostgreSQL ve şifreli depolama.
- **Denetim zinciri kurcalamayı görünür kılar, engellemez.** Üretimde WORM
  depolama veya kurumun log altyapısıyla desteklenmelidir.
- **Gemini asistanı dışarıya istek atar.** Anahtar yokken kapalıdır. Kamu
  verisiyle çalışırken kurum içi (on-premise) bir modelle değiştirilmelidir;
  asistan skor üretmez, karar vermez.

## Veri

Depodaki firma kayıtları, beyanlar ve denetim sonuçları **tamamen sentetiktir**.
Gerçek VKN, gerçek beyan veya gerçek denetim sonucu depoya — teste, örneğe,
sabit değere — **hiçbir biçimde girmez**. Gerçek veri içeren bir katkı geri
çevrilir.
