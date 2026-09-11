## Ne değişti

<!-- Bir iki cümle. Diff neyi değiştirdiğini zaten gösteriyor; burada NEDEN'i yazın. -->

## Nasıl doğrulandı

<!-- Hangi komutu çalıştırdınız, ne gördünüz? Ekran görüntüsü varsa ekleyin. -->

- [ ] `cd backend && python -m pytest` geçiyor
- [ ] `cd frontend && npm run build` geçiyor
- [ ] Arayüzü etkiliyorsa ekran görüntüsü eklendi

## Değişmezler

Bu PR aşağıdakilerin hiçbirini bozmuyor:

- [ ] Hesaplanamayan özellik nötr bir değere **doldurulmuyor**; ona dayanan
      kontroller *çalıştırılamadı* olarak işaretlenip nedeni yazılıyor
- [ ] Çalıştırılamayan kontrolün ağırlığı paydadan düşüyor, **sıfır sayılmıyor**
- [ ] Kimlik özellikleri (il) risk puanına girmiyor
- [ ] Gerekçe metni **şablonlu**; serbest üretimli dil modeli kullanılmıyor
- [ ] "0–100 puan inceleme önceliğidir, ihlal olasılığı değildir" ifadesi
      hiçbir yerde yumuşatılmadı

> Biri işaretlenemiyorsa açıklayın — gerekçeli bir istisna olabilir.

## Model artefaktları

- [ ] Bu PR model artefaktlarına dokunmuyor
- [ ] Dokunuyor → set **bütün olarak** yeniden üretildi, `MODEL_KARTI.md` ve
      `metrics.json` aynı commit'te güncellendi

## Veri

- [ ] Gerçek firma verisi, gerçek VKN veya gerçek beyan eklenmedi
