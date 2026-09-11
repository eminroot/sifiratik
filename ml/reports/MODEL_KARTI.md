# GUS-DEDEKTIV - Model Karti

**Model surumu:** `gus-ml-1.0.0` · **Veri surumu:** `1.0.0`
**Egitim tohumu:** 20260902 · **Hedef kapsama:** 0.9

---

## 1. Once sinirliliklar

- Model **SENTETIK** veri uzerinde egitilmistir. Buradaki performans
  **gercek kamu performansi olarak sunulamaz**.
- Cikti **operasyonel inceleme onceligidir**; suc, ihlal veya usulsuzluk
  olasiligi **degildir**. Model tek basina ceza veya olumsuz idari karar
  **uretemez**; nihai karar yetkili insan denetciye aittir.
- Egitim penceresinde yalnizca 246 pozitif ornek vardir.
  Precision@100 gibi metrikler dar orneklemde genis guven araligi tasir; bu
  nedenle **bootstrap guven araliklari** ile birlikte raporlanir.
- `A08_dis_kanit_uyumsuz` mekanizmasi egitimde nadir, testte siktir. Bu
  **kasitli bir kavramsal kayma (concept drift) testidir**; ilgili satira bakiniz.
- **Kimlik ozellikleri risk puanina girmez.** Il (`province`) hicbir yerde
  kullanilmaz; sektor ve olcek bandi ise YALNIZCA beklenti basliklarinda ve
  konformal gruplamada kullanilir. Oradaki isleri karsilastirmayi adil
  yapmaktir - firma kendi sektorunun ve olceginin beklentisiyle olculur. Risk
  puanina dogrudan girselerdi yapacaklari sey "senin gibi firmalar daha cok
  denetleniyor" demek olurdu. Bedeli olculdu ve yoktur: egitim penceresi
  capraz dogrulamasinda PR-AUC 0,2141 -> 0,2169, test Precision@100 0,350 ->
  0,350.
- **Eksik veri dusuk risk sayilmaz.** Calistirilamayan bir sinyal puan
  tasimaz, fakat KATKI tasiyabilir: model, kontrol edilemeyen dosyalarin daha
  sik eksik beyan tasidigini veriden ogrenir. Denetci panelinde bu durum
  kelimelerle yazilir - sessizce "temiz" sayilmaz.
- Model **veri toplamaz**. Kurumun kendi verisini kendi ortaminda degerlendirir.

## 2. Ne yapar

Firma-ceyrek GEKAP beyani icin (a) beklenen beyan araligini kalibre ederek
uretir, (b) sekiz ayri kanit sinyalini degerlendirir, (c) bunlari 0-100
inceleme onceligine cevirir, (d) her sonucu hangi sinyalin ne kadar
urettigini SHAP katkisiyla acikca soyler, (e) **degerlendirilemeyen** sinyali
nedeniyle birlikte bildirir.

Analiz birimi **firma-ceyrek**tir.

## 3. Mimari

| Katman | Bilesen | Yontem |
|---|---|---|
| 3 | Tarihsel baslik | LightGBM quantile (q05/q50/q95), hedef `log1p(beyan)` |
| 3 | Emsal baslik | LightGBM quantile; firmanin **kendi beyan gecmisi girmez** |
| 3 | Harman | log uzayinda agirlikli ortalama, agirlik = **0.95** (valid_a pinball) |
| 3 | Kalibrasyon | Mondrian **CQR**: (sektor, olcek, veri guveni) -> ... -> global |
| 4 | Sekiz sinyal | ham istatistik -> egitim penceresi yuzdelik rampasi -> 0-100 |
| 4 | Birlestirme | LightGBM tohum toplulugu; girdi: sinyallerin **ham** istatistigi + kullanilabilirlik + aralik konumu + veri guveni |
| 4 | Puan | izotonik kalibrasyon -> referans yuzdelik -> 0-100 |
| 5 | Aciklama | TreeSHAP katkisi -> sinyal duzeyi -> **sablonlu** gerekce cumlesi |

Gerekce metni sablonludur; serbest uretimli dil modeli **kullanilmaz**.
Ayni girdi ayni cumleyi uretir ve her cumle arkasindaki sayiyi tasir.

## 4. Veri ve bolumleme

| Bolum | Donemler |
|---|---|
| train | 2024Q1, 2024Q2, 2024Q3, 2024Q4, 2025Q1, 2025Q2 |
| valid | 2025Q3, 2025Q4 |
| test | 2026Q1, 2026Q2 |

`valid`, **firma bazinda** ikiye ayrilir: `valid_a` model secimi ve erken
durdurma, `valid_b` kalibrasyon. Ayni satirlari hem secim hem kalibrasyon
icin kullanmak kapsama oranini iyimser gosterirdi.

Konformal artiklar ek olarak egitim bolumunun **capraz uydurulmus
(out-of-fold)** tahminlerinden alinir; boylece artiklar ornekle**m disi**dir.

## 5. Test bolumu sonuclari

> Test bolumu **yalnizca bir kez** okunmustur. Tum model ve esik secimleri
> `valid` uzerinde yapilmistir.

| Metrik | Deger |
|---|---|
| Kayit / pozitif | 1200 / prevalans 0.0808 |
| PR-AUC | **0.3277** |
| ROC-AUC (ek gosterge) | 0.6742 |
| Precision@50 | 0.5 (Lift 6.186) |
| Precision@100 | **0.36** (bootstrap %95 GA 0.26 - 0.45) |
| Recall@100 | 0.3711 |
| Lift@100 | **4.454** |

### Referans baseline'lar ile ayni tabloda

Metrik tanimlari `gus_generator.quality` icinden ithal edilmistir; iki tablo
ayni fonksiyonlari kullanir.

| model | PR_AUC | ROC_AUC_ek_gosterge | Precision@50 | Precision@100 | Recall@100 | Lift@100 | Precision@100_CI_alt | Precision@100_CI_ust |
|---|---|---|---|---|---|---|---|---|
| GUS-DEDEKTIV (fusion) | 0.3277 | 0.6742 | 0.5 | 0.36 | 0.3711 | 4.454 | 0.26 | 0.45 |
| politika agirlikli birlestirme | 0.1704 | 0.6504 | 0.22 | 0.29 | 0.299 | 3.588 | 0.2 | 0.37 |
| bl_zscore_hist | 0.1592 | 0.6604 | 0.18 | 0.19 | 0.1959 | 2.351 | 0.12 | 0.27 |
| bl_naive_8signal | 0.1587 | 0.6295 | 0.24 | 0.21 | 0.2165 | 2.598 | 0.13 | 0.3 |
| bl_bom_gap | 0.1438 | 0.6162 | 0.26 | 0.19 | 0.1959 | 2.351 | 0.11 | 0.27 |
| bl_expert_rule | 0.1227 | 0.6158 | 0.08 | 0.18 | 0.1856 | 2.227 | 0.11 | 0.26 |
| bl_random | 0.0804 | 0.4972 | 0.04 | 0.07 | 0.0722 | 0.866 | 0.02 | 0.12 |
| bl_peer | 0.0774 | 0.4858 | 0.1 | 0.07 | 0.0722 | 0.866 | 0.02 | 0.12 |


## 6. Beklenen aralik ve kalibrasyon

Hedef kapsama **0.9**.
Gozlenen kapsama: valid **0.9167**, test **0.8825**.
Test bolumunde ortanca bagil aralik genisligi **0.873**.

| grup | n | gozlenen_kapsama | ortanca_genislik_ton | ortanca_bagil_genislik |
|---|---|---|---|---|
| tumu | 1200 | 0.8825 | 53.435 | 0.873 |
| size_band=buyuk | 100 | 0.89 | 785.417 | 0.741 |
| size_band=kucuk | 488 | 0.873 | 62.339 | 0.89 |
| size_band=mikro | 384 | 0.901 | 14.075 | 0.967 |
| size_band=orta | 228 | 0.8684 | 180.341 | 0.741 |
| sector=elektronik | 118 | 0.9153 | 111.716 | 0.828 |
| sector=ev_temizlik | 90 | 0.9444 | 54.109 | 0.841 |
| sector=gida_icecek | 320 | 0.9125 | 32.186 | 0.809 |
| sector=ilac | 108 | 0.8611 | 49.652 | 0.859 |
| sector=kimya_boya | 116 | 0.8793 | 68.195 | 0.835 |
| sector=kozmetik | 124 | 0.8952 | 69.512 | 0.896 |
| sector=otomotiv_yan_sanayi | 138 | 0.8333 | 60.991 | 0.985 |
| sector=tekstil | 186 | 0.8226 | 48.766 | 1.039 |


Olasilik kalibrasyonu (test): Brier **0.06596**,
ECE **0.02186**,
ortalama tahmin 0.06422 vs
gozlenen prevalans 0.08083.

## 7. Sinyaller

Sinyaller **bagimsiz degil, ayridir**; korelasyonlari `06_sinyal_korelasyon.csv`
icindedir. Tek basina ayirt gucleri:

| sinyal | ad | kullanilabilirlik | n | PR_AUC | ROC_AUC | atesleme_orani |
|---|---|---|---|---|---|---|
| S1 | Tarihsel alt sinir ihlali | 0.9992 | 1199 | 0.1487 | 0.6547 | 0.2477 |
| S2 | Emsal alt sinir ihlali | 0.9925 | 1191 | 0.0745 | 0.4658 | 0.2065 |
| S3 | Beklenen-gerceklesen tonaj farki | 0.9942 | 1193 | 0.2335 | 0.6621 | 0.2372 |
| S4 | Faaliyet esnekligi uyumsuzlugu | 0.8858 | 1063 | 0.1175 | 0.5926 | 0.2333 |
| S5 | Dis ticaret ve duzeltme dengesi | 0.82 | 984 | 0.1651 | 0.664 | 0.2449 |
| S6 | Donemsel davranis kirilmasi | 0.9392 | 1127 | 0.1302 | 0.6149 | 0.2458 |
| S7 | Urun agaci / ambalaj matrisi uyumsuzlugu | 0.9933 | 1192 | 0.1074 | 0.5304 | 0.2844 |
| S8 | Dis dogrulama kaniti | 0.1983 | 238 | 0.1882 | 0.6495 | 0.2395 |


### Ablation - her sinyal cikarilarak yeniden egitim

| cikarilan | ad | PR_AUC | Precision@100 | delta_PR_AUC | delta_Precision@100 |
|---|---|---|---|---|---|
| - | - | 0.2995 | 0.35 | 0.0 | 0.0 |
| S1 | Tarihsel alt sinir ihlali | 0.2983 | 0.33 | -0.0012 | -0.02 |
| S2 | Emsal alt sinir ihlali | 0.2978 | 0.34 | -0.0017 | -0.01 |
| S3 | Beklenen-gerceklesen tonaj farki | 0.2294 | 0.26 | -0.07 | -0.09 |
| S4 | Faaliyet esnekligi uyumsuzlugu | 0.2975 | 0.34 | -0.002 | -0.01 |
| S5 | Dis ticaret ve duzeltme dengesi | 0.2945 | 0.33 | -0.005 | -0.02 |
| S6 | Donemsel davranis kirilmasi | 0.2956 | 0.36 | -0.0039 | 0.01 |
| S7 | Urun agaci / ambalaj matrisi uyumsuzlugu | 0.3128 | 0.36 | 0.0133 | 0.01 |
| S8 | Dis dogrulama kaniti | 0.297 | 0.35 | -0.0025 | 0.0 |
| konformal aralik | konformal aralik | 0.2775 | 0.34 | -0.022 | -0.01 |


## 8. Alt grup davranisi

| boyut | grup | n | prevalans | PR_AUC | Top100_payi |
|---|---|---|---|---|---|
| sector | elektronik | 118 | 0.0932 | 0.4558 | 0.0847 |
| sector | ev_temizlik | 90 | 0.1111 | 0.4542 | 0.1111 |
| sector | gida_icecek | 320 | 0.0563 | 0.305 | 0.0625 |
| sector | ilac | 108 | 0.1667 | 0.5312 | 0.1296 |
| sector | kimya_boya | 116 | 0.1121 | 0.3937 | 0.1034 |
| sector | kozmetik | 124 | 0.0403 | 0.1514 | 0.0403 |
| sector | otomotiv_yan_sanayi | 138 | 0.1014 | 0.2922 | 0.0797 |
| sector | tekstil | 186 | 0.043 | 0.1194 | 0.0968 |
| size_band | buyuk | 100 | 0.08 | 0.4855 | 0.06 |
| size_band | kucuk | 488 | 0.0799 | 0.2868 | 0.0635 |
| size_band | mikro | 384 | 0.0859 | 0.2938 | 0.1198 |
| size_band | orta | 228 | 0.0746 | 0.4374 | 0.0746 |
| f_data_confidence_level | dusuk | 65 | 0.0769 | 0.4257 | 0.0769 |
| f_data_confidence_level | orta | 630 | 0.081 | 0.245 | 0.0762 |
| f_data_confidence_level | yuksek | 505 | 0.0812 | 0.4448 | 0.0931 |
| province | Adana | 52 | 0.0577 | 0.5213 | 0.0577 |
| province | Ankara | 122 | 0.0738 | 0.2937 | 0.0492 |
| province | Antalya | 48 | 0.1458 | 0.4518 | 0.0417 |
| province | Balikesir | 26 | 0.1154 | 0.5436 | 0.0769 |
| province | Bursa | 88 | 0.0795 | 0.263 | 0.0795 |
| province | Eskisehir | 50 | 0.02 | 0.037 | 0.04 |
| province | Gaziantep | 40 | 0.1 | 0.3871 | 0.075 |
| province | Istanbul | 272 | 0.0956 | 0.2394 | 0.0993 |
| province | Izmir | 104 | 0.0481 | 0.188 | 0.0673 |
| province | Kayseri | 40 | 0.025 | 0.0333 | 0.125 |
| province | Kocaeli | 82 | 0.0488 | 0.05 | 0.122 |
| province | Konya | 52 | 0.0962 | 0.3937 | 0.1154 |
| province | Manisa | 30 | 0.0 |  | 0.0667 |
| province | Mersin | 28 | 0.1429 | 0.75 | 0.1786 |
| province | Sakarya | 34 | 0.1176 | 0.7208 | 0.1176 |
| province | Samsun | 32 | 0.125 | 0.7857 | 0.0938 |
| province | Tekirdag | 44 | 0.0682 | 0.7255 | 0.0455 |


## 9. Mekanizma bazli yakalama ve kavramsal kayma

| mekanizma | n | truth | Top50_icinde | Top50_orani | Top100_icinde | Top100_orani | Top200_icinde | Top200_orani |
|---|---|---|---|---|---|---|---|---|
| A01_tarihsel_dusus | 9 | 9 | 5 | 0.5556 | 6 | 0.6667 | 7 | 0.7778 |
| A02_emsal_alti | 5 | 5 | 2 | 0.4 | 2 | 0.4 | 2 | 0.4 |
| A03_beklenen_fark | 10 | 8 | 4 | 0.4 | 7 | 0.7 | 9 | 0.9 |
| A04_faaliyet_uyumsuz | 9 | 9 | 3 | 0.3333 | 4 | 0.4444 | 5 | 0.5556 |
| A06_mevsimsel_kirilma | 3 | 3 | 1 | 0.3333 | 2 | 0.6667 | 2 | 0.6667 |
| A07_urun_agaci_uyumsuz | 5 | 5 | 1 | 0.2 | 3 | 0.6 | 4 | 0.8 |
| A08_dis_kanit_uyumsuz | 18 | 17 | 10 | 0.5556 | 12 | 0.6667 | 13 | 0.7222 |
| N00_normal | 895 | 37 | 10 | 0.0112 | 30 | 0.0335 | 91 | 0.1017 |
| N09_veri_eksikligi | 33 | 0 | 0 | 0.0 | 1 | 0.0303 | 5 | 0.1515 |
| N10_mesru_gorunum | 213 | 4 | 14 | 0.0657 | 33 | 0.1549 | 62 | 0.2911 |


## 10. Denetim faydasi

| K | dogrulanan_vaka | vaka_100_denetim_basina | duzeltilen_tonaj | toplam_tonajin_payi | denetim_maliyeti_try | ton_basina_maliyet_try | toplam_inceleme_gunu |
|---|---|---|---|---|---|---|---|
| 25 | 17 | 68.0 | 2082.96 | 0.7094 | 1230884.7 | 590.93 | 367 |
| 50 | 25 | 50.0 | 2177.87 | 0.7418 | 1904898.31 | 874.66 | 605 |
| 100 | 36 | 36.0 | 2611.19 | 0.8894 | 3651705.42 | 1398.48 | 1126 |
| 200 | 41 | 20.5 | 2739.15 | 0.9329 | 7518798.89 | 2744.94 | 2311 |
| 400 | 50 | 12.5 | 2888.26 | 0.9837 | 15645762.2 | 5417.03 | 4782 |


### Top-100 icindeki negatiflerin profili

`N10_mesru_gorunum`, mesru nedenle riskli **gorunen** kayitlardir; denetciye
gerekce panelinde nedeniyle birlikte gosterilir. `N09_veri_eksikligi` dusuk
risk **sayilmaz**, ayri veri incelemesi kuyruguna gider.

| kategori | sayi | pay | aciklama |
|---|---|---|---|
| Top-100 toplam | 100 | 1.0 |  |
| dogrulanan eksik beyan | 36 | 0.36 | gercek pozitif |
| A08_dis_kanit_uyumsuz | 1 | 0.01 | yanlis pozitif |
| N00_normal | 29 | 0.29 | yanlis pozitif |
| N09_veri_eksikligi | 1 | 0.01 | veri incelemesi kuyrugu |
| N10_mesru_gorunum | 33 | 0.33 | yanlis pozitif |
|   mesru neden: eskimis_ambalaj_agirlik_matrisi | 4 | 0.04 | denetci gerekce panelinde gorunur |
|   mesru neden: gec_duzeltme_beyannamesi | 9 | 0.09 | denetci gerekce panelinde gorunur |
|   mesru neden: ihracat_agirlikli_donem | 7 | 0.07 | denetci gerekce panelinde gorunur |
|   mesru neden: mevsimsel_uretim_duraklamasi | 7 | 0.07 | denetci gerekce panelinde gorunur |
|   mesru neden: urun_gami_degisikligi | 4 | 0.04 | denetci gerekce panelinde gorunur |
|   mesru neden: yasal_muafiyet_istisna | 1 | 0.01 | denetci gerekce panelinde gorunur |
|   mesru neden: yeni_firma_kisa_tarihce | 1 | 0.01 | denetci gerekce panelinde gorunur |


## 11. Gercek veriye gecerken

Sinyal mantigi degismez; sentetik alanlar karsilik gelen resmi kaynakla
degistirilir (`Government_Integration_Map`). Uc nokta pilotta yeniden
olculmelidir:

1. **Konformal kapsama her donem yeniden kalibre edilmelidir.** Hedef 0,90
   iken `valid` uzerinde 0,92, bir sonraki pencerede (test) 0,88 gozlendi.
   Konformal garanti degisim-degismezlik varsayar; zaman icinde ilerledikce
   bu varsayim zayiflar. Egitim penceresi icinde olculen kayma payi bu
   surumde 0,00 cikti, yani kayip egitim->valid gecisinde degil valid->test
   gecisinde olustu.
2. **Sinyal olcekleri populasyona baglidir.** Rampa capalari egitim
   penceresinin dagilimindan ogrenilir. Farkli bir populasyonda bir sinyal
   hic ateslemeyebilir; `signals.json` yeniden uretilmelidir.
3. **S3 kapsam duzeltmesi kurumun kapsam alaninin anlamina baglidir.**
   Beklenti, urun agacinin kapsanan kismindan gelir ve kapsam oranina
   bolunerek genisletilir. Kurumun kapsam alani farkli tanimliysa bu bolme
   yeniden dogrulanmalidir.

## 12. Kullanim sinirlari

- Puan siralamadir; esik gecmek **ihlal kaniti degildir**.
- Kullanilamayan sinyal **temiz sonuc degildir**; veri guveni dusurulur.
- Model kararlari `decision_id` ile model ve veri surumune baglanir.
- Gercek veriye gecişte sinyal mantigi degismez; sentetik alanlar karsilik
  gelen resmi kaynakla degistirilir.
