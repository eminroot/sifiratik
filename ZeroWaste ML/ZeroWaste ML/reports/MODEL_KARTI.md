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
- Il (`province`) bilgisi modele **girdi olarak verilmemistir**. Cografi
  profilleme riski nedeniyle yalnizca alt grup adalet olcumunde kullanilir.
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
| 3 | Kalibrasyon | Mondrian **CQR** (sector x size_band -> sector -> size_band -> global) |
| 4 | Sekiz sinyal | ham istatistik -> egitim penceresi yuzdelik rampasi -> 0-100 |
| 4 | Birlestirme | LightGBM (girdi: sinyaller + kullanilabilirlik + aralik konumu + veri guveni) |
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
| PR-AUC | **0.2877** |
| ROC-AUC (ek gosterge) | 0.6782 |
| Precision@50 | 0.44 (Lift 5.443) |
| Precision@100 | **0.32** (bootstrap %95 GA 0.22 - 0.42) |
| Recall@100 | 0.3299 |
| Lift@100 | **3.959** |

### Referans baseline'lar ile ayni tabloda

Metrik tanimlari `gus_generator.quality` icinden ithal edilmistir; iki tablo
ayni fonksiyonlari kullanir.

| model | PR_AUC | ROC_AUC_ek_gosterge | Precision@50 | Precision@100 | Recall@100 | Lift@100 | Precision@100_CI_alt | Precision@100_CI_ust |
|---|---|---|---|---|---|---|---|---|
| GUS-DEDEKTIV (fusion) | 0.2877 | 0.6782 | 0.44 | 0.32 | 0.3299 | 3.959 | 0.22 | 0.42 |
| bl_zscore_hist | 0.1592 | 0.6604 | 0.18 | 0.19 | 0.1959 | 2.351 | 0.12 | 0.27 |
| bl_naive_8signal | 0.1587 | 0.6295 | 0.24 | 0.21 | 0.2165 | 2.598 | 0.13 | 0.3 |
| bl_bom_gap | 0.1438 | 0.6162 | 0.26 | 0.19 | 0.1959 | 2.351 | 0.11 | 0.27 |
| bl_expert_rule | 0.1227 | 0.6158 | 0.08 | 0.18 | 0.1856 | 2.227 | 0.11 | 0.26 |
| politika agirlikli birlestirme | 0.1204 | 0.6203 | 0.1 | 0.14 | 0.1443 | 1.732 | 0.07 | 0.21 |
| bl_random | 0.0804 | 0.4972 | 0.04 | 0.07 | 0.0722 | 0.866 | 0.02 | 0.12 |
| bl_peer | 0.0774 | 0.4858 | 0.1 | 0.07 | 0.0722 | 0.866 | 0.02 | 0.12 |


## 6. Beklenen aralik ve kalibrasyon

Hedef kapsama **0.9**.
Gozlenen kapsama: valid **0.91**, test **0.875**.
Test bolumunde ortanca bagil aralik genisligi **0.853**.

| grup | n | gozlenen_kapsama | ortanca_genislik_ton | ortanca_bagil_genislik |
|---|---|---|---|---|
| tumu | 1200 | 0.875 | 53.023 | 0.853 |
| size_band=buyuk | 100 | 0.89 | 750.771 | 0.717 |
| size_band=kucuk | 488 | 0.8566 | 60.133 | 0.854 |
| size_band=mikro | 384 | 0.901 | 14.579 | 0.944 |
| size_band=orta | 228 | 0.864 | 189.262 | 0.735 |
| sector=elektronik | 118 | 0.8898 | 108.941 | 0.811 |
| sector=ev_temizlik | 90 | 0.9333 | 51.964 | 0.854 |
| sector=gida_icecek | 320 | 0.9 | 31.295 | 0.783 |
| sector=ilac | 108 | 0.8519 | 47.36 | 0.838 |
| sector=kimya_boya | 116 | 0.8879 | 68.363 | 0.816 |
| sector=kozmetik | 124 | 0.8952 | 66.171 | 0.857 |
| sector=otomotiv_yan_sanayi | 138 | 0.8333 | 56.674 | 0.97 |
| sector=tekstil | 186 | 0.8172 | 48.726 | 1.023 |


Olasilik kalibrasyonu (test): Brier **0.06696**,
ECE **0.0204**,
ortalama tahmin 0.06655 vs
gozlenen prevalans 0.08083.

## 7. Sinyaller

Sinyaller **bagimsiz degil, ayridir**; korelasyonlari `06_sinyal_korelasyon.csv`
icindedir. Tek basina ayirt gucleri:

| sinyal | ad | kullanilabilirlik | n | PR_AUC | ROC_AUC | atesleme_orani |
|---|---|---|---|---|---|---|
| S1 | Tarihsel alt sinir ihlali | 0.9992 | 1199 | 0.1483 | 0.6547 | 0.1776 |
| S2 | Emsal alt sinir ihlali | 0.9925 | 1191 | 0.0745 | 0.4658 | 0.2309 |
| S3 | Beklenen-gerceklesen tonaj farki | 0.9942 | 1193 | 0.1309 | 0.5431 | 0.0285 |
| S4 | Faaliyet esnekligi uyumsuzlugu | 0.8858 | 1063 | 0.1175 | 0.5926 | 0.1571 |
| S5 | Dis ticaret ve duzeltme dengesi | 0.82 | 984 | 0.1772 | 0.6641 | 0.1636 |
| S6 | Donemsel davranis kirilmasi | 0.9392 | 1127 | 0.1336 | 0.615 | 0.1837 |
| S7 | Urun agaci / ambalaj matrisi uyumsuzlugu | 0.9933 | 1192 | 0.1153 | 0.5304 | 0.182 |
| S8 | Dis dogrulama kaniti | 0.1983 | 238 | 0.1882 | 0.6495 | 0.2017 |


### Ablation - her sinyal cikarilarak yeniden egitim

| cikarilan | ad | PR_AUC | Precision@100 | delta_PR_AUC | delta_Precision@100 |
|---|---|---|---|---|---|
| - | - | 0.2736 | 0.32 | 0.0 | 0.0 |
| S1 | Tarihsel alt sinir ihlali | 0.2783 | 0.35 | 0.0047 | 0.03 |
| S2 | Emsal alt sinir ihlali | 0.2667 | 0.32 | -0.0069 | 0.0 |
| S3 | Beklenen-gerceklesen tonaj farki | 0.2309 | 0.26 | -0.0427 | -0.06 |
| S4 | Faaliyet esnekligi uyumsuzlugu | 0.2658 | 0.31 | -0.0078 | -0.01 |
| S5 | Dis ticaret ve duzeltme dengesi | 0.2864 | 0.33 | 0.0128 | 0.01 |
| S6 | Donemsel davranis kirilmasi | 0.2782 | 0.32 | 0.0046 | 0.0 |
| S7 | Urun agaci / ambalaj matrisi uyumsuzlugu | 0.2835 | 0.32 | 0.0099 | 0.0 |
| S8 | Dis dogrulama kaniti | 0.2831 | 0.34 | 0.0095 | 0.02 |
| konformal aralik | konformal aralik | 0.2578 | 0.29 | -0.0158 | -0.03 |


## 8. Alt grup davranisi

| boyut | grup | n | prevalans | PR_AUC | Top100_payi |
|---|---|---|---|---|---|
| sector | elektronik | 118 | 0.0932 | 0.5139 | 0.0593 |
| sector | ev_temizlik | 90 | 0.1111 | 0.4318 | 0.0667 |
| sector | gida_icecek | 320 | 0.0563 | 0.1958 | 0.0594 |
| sector | ilac | 108 | 0.1667 | 0.4806 | 0.1481 |
| sector | kimya_boya | 116 | 0.1121 | 0.3753 | 0.0862 |
| sector | kozmetik | 124 | 0.0403 | 0.3187 | 0.0565 |
| sector | otomotiv_yan_sanayi | 138 | 0.1014 | 0.3162 | 0.0652 |
| sector | tekstil | 186 | 0.043 | 0.1309 | 0.1398 |
| size_band | buyuk | 100 | 0.08 | 0.3809 | 0.06 |
| size_band | kucuk | 488 | 0.0799 | 0.2158 | 0.0799 |
| size_band | mikro | 384 | 0.0859 | 0.3642 | 0.0833 |
| size_band | orta | 228 | 0.0746 | 0.4213 | 0.1009 |
| f_data_confidence_level | dusuk | 65 | 0.0769 | 0.5089 | 0.0769 |
| f_data_confidence_level | orta | 630 | 0.081 | 0.2147 | 0.0825 |
| f_data_confidence_level | yuksek | 505 | 0.0812 | 0.3812 | 0.0851 |
| province | Adana | 52 | 0.0577 | 0.4518 | 0.1538 |
| province | Ankara | 122 | 0.0738 | 0.3975 | 0.0738 |
| province | Antalya | 48 | 0.1458 | 0.3446 | 0.1042 |
| province | Balikesir | 26 | 0.1154 | 0.6032 | 0.0769 |
| province | Bursa | 88 | 0.0795 | 0.4467 | 0.0909 |
| province | Eskisehir | 50 | 0.02 | 0.0323 | 0.02 |
| province | Gaziantep | 40 | 0.1 | 0.4221 | 0.075 |
| province | Istanbul | 272 | 0.0956 | 0.2456 | 0.0919 |
| province | Izmir | 104 | 0.0481 | 0.1613 | 0.0865 |
| province | Kayseri | 40 | 0.025 | 0.0476 | 0.1 |
| province | Kocaeli | 82 | 0.0488 | 0.0649 | 0.0732 |
| province | Konya | 52 | 0.0962 | 0.3545 | 0.0769 |
| province | Manisa | 30 | 0.0 |  | 0.0333 |
| province | Mersin | 28 | 0.1429 | 0.622 | 0.0714 |
| province | Sakarya | 34 | 0.1176 | 0.5161 | 0.1176 |
| province | Samsun | 32 | 0.125 | 0.5623 | 0.0938 |
| province | Tekirdag | 44 | 0.0682 | 0.693 | 0.0455 |


## 9. Mekanizma bazli yakalama ve kavramsal kayma

| mekanizma | n | truth | Top50_icinde | Top50_orani | Top100_icinde | Top100_orani | Top200_icinde | Top200_orani |
|---|---|---|---|---|---|---|---|---|
| A01_tarihsel_dusus | 9 | 9 | 5 | 0.5556 | 6 | 0.6667 | 8 | 0.8889 |
| A02_emsal_alti | 5 | 5 | 2 | 0.4 | 2 | 0.4 | 2 | 0.4 |
| A03_beklenen_fark | 10 | 8 | 4 | 0.4 | 7 | 0.7 | 8 | 0.8 |
| A04_faaliyet_uyumsuz | 9 | 9 | 4 | 0.4444 | 4 | 0.4444 | 5 | 0.5556 |
| A06_mevsimsel_kirilma | 3 | 3 | 2 | 0.6667 | 2 | 0.6667 | 2 | 0.6667 |
| A07_urun_agaci_uyumsuz | 5 | 5 | 1 | 0.2 | 2 | 0.4 | 4 | 0.8 |
| A08_dis_kanit_uyumsuz | 18 | 17 | 4 | 0.2222 | 10 | 0.5556 | 13 | 0.7222 |
| N00_normal | 895 | 37 | 12 | 0.0134 | 24 | 0.0268 | 79 | 0.0883 |
| N09_veri_eksikligi | 33 | 0 | 1 | 0.0303 | 1 | 0.0303 | 3 | 0.0909 |
| N10_mesru_gorunum | 213 | 4 | 15 | 0.0704 | 42 | 0.1972 | 76 | 0.3568 |


## 10. Denetim faydasi

| K | dogrulanan_vaka | vaka_100_denetim_basina | duzeltilen_tonaj | toplam_tonajin_payi | denetim_maliyeti_try | ton_basina_maliyet_try | toplam_inceleme_gunu |
|---|---|---|---|---|---|---|---|
| 25 | 13 | 52.0 | 1290.17 | 0.4394 | 1113754.54 | 863.26 | 336 |
| 50 | 22 | 44.0 | 1883.94 | 0.6417 | 2078016.76 | 1103.01 | 664 |
| 100 | 32 | 32.0 | 2304.97 | 0.7851 | 3890592.65 | 1687.92 | 1241 |
| 200 | 44 | 22.0 | 2689.81 | 0.9161 | 7956164.64 | 2957.89 | 2425 |
| 400 | 58 | 14.5 | 2784.49 | 0.9484 | 15878358.34 | 5702.43 | 4751 |


### Top-100 icindeki negatiflerin profili

`N10_mesru_gorunum`, mesru nedenle riskli **gorunen** kayitlardir; denetciye
gerekce panelinde nedeniyle birlikte gosterilir. `N09_veri_eksikligi` dusuk
risk **sayilmaz**, ayri veri incelemesi kuyruguna gider.

| kategori | sayi | pay | aciklama |
|---|---|---|---|
| Top-100 toplam | 100 | 1.0 |  |
| dogrulanan eksik beyan | 32 | 0.32 | gercek pozitif |
| A08_dis_kanit_uyumsuz | 1 | 0.01 | yanlis pozitif |
| N00_normal | 24 | 0.24 | yanlis pozitif |
| N09_veri_eksikligi | 1 | 0.01 | veri incelemesi kuyrugu |
| N10_mesru_gorunum | 42 | 0.42 | yanlis pozitif |
|   mesru neden: eskimis_ambalaj_agirlik_matrisi | 1 | 0.01 | denetci gerekce panelinde gorunur |
|   mesru neden: gec_duzeltme_beyannamesi | 8 | 0.08 | denetci gerekce panelinde gorunur |
|   mesru neden: ihracat_agirlikli_donem | 16 | 0.16 | denetci gerekce panelinde gorunur |
|   mesru neden: mevsimsel_uretim_duraklamasi | 11 | 0.11 | denetci gerekce panelinde gorunur |
|   mesru neden: urun_gami_degisikligi | 1 | 0.01 | denetci gerekce panelinde gorunur |
|   mesru neden: yasal_muafiyet_istisna | 4 | 0.04 | denetci gerekce panelinde gorunur |
|   mesru neden: yeni_firma_kisa_tarihce | 1 | 0.01 | denetci gerekce panelinde gorunur |


## 11. Kullanim sinirlari

- Puan siralamadir; esik gecmek **ihlal kaniti degildir**.
- Kullanilamayan sinyal **temiz sonuc degildir**; veri guveni dusurulur.
- Model kararlari `decision_id` ile model ve veri surumune baglanir.
- Gercek veriye gecişte sinyal mantigi degismez; sentetik alanlar karsilik
  gelen resmi kaynakla degistirilir.
