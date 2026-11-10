# Meridian MMM

Google Meridian ile geo bazlı Marketing Mix Model (MMM) çalışması. Model; ücretli medya kanallarının satışa katkısını, ROI'lerini, etkilerinin ne kadar sürdüğünü ve aynı bütçeyle daha verimli bir dağılımı hesaplıyor.

## Veri

Meridian reposundaki simüle `geo_all_channels.csv` veri seti kullanılıyor:
https://github.com/google/meridian/blob/main/meridian/data/simulated_data/csv/geo_all_channels.csv

- 40 bölge, 156 hafta (Ocak 2021 ile Ocak 2024 arası)
- KPI: `conversions`, dönüşüm başı gelir: `revenue_per_conversion`
- 5 ücretli kanal (gösterim + harcama), 1 organik kanal, Promo, 2 kontrol değişkeni

Veri gerçek bir markaya ait değildir; sonuçlar öğrenme ve kod akışını test etme amaçlıdır.

## Klasör yapısı

```
meridian-mmm/
├── data/                 # geo_all_channels.csv (git'e girmez)
├── outputs_v1/           # İlk model çıktıları (git'e girmez)
├── outputs_v2/           # Güncel model çıktıları (git'e girmez)
├── run_model.py          # Modelin tamamı, # %% hücreleriyle
├── requirements.txt
└── README.md
```

## Kurulum (Windows)

Proje OneDrive dışında bir klasörde olmalı (örneğin `C:\dev\meridian-mmm`), aksi halde sanal ortam kurulumunda dosya kilitlenme sorunları çıkıyor.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Veriyi ham haliyle indir:

```powershell
mkdir data
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/google/meridian/main/meridian/data/simulated_data/csv/geo_all_channels.csv" -OutFile "data\geo_all_channels.csv"
```

CSV dosyasını Excel'de açıp kaydetme. Türkçe ayarlı Excel ayırıcıyı ve ondalıkları değiştirdiği için dosya Python tarafından okunamaz hale gelir.

## Çalıştırma

VS Code'da Jupyter eklentisi kurulu olmalı. `run_model.py` dosyasındaki hücreleri **Run Cell** ile sırayla çalıştır:

| Hücre | İşi |
|---|---|
| 1 | Importlar ve ayarlar (`OUT`, `USE_SAVED_MODEL`) |
| 2 | Veri okuma ve kontrol |
| 3 | Veriyi Meridian formatına çevirme |
| 4 | Prior ve model tanımı |
| 5 | Model eğitimi (MCMC) ya da kayıtlı modeli yükleme |
| 6 | Model sağlığı (health card, R-hat, model fit, prior vs posterior) |
| 7 | Sonuçlar (ROI, katkı, tepki eğrileri, adstock) |
| 8 | Bütçe optimizasyonu |

Eğitim CPU'da uzun sürer. Model bir kez eğitildikten sonra `USE_SAVED_MODEL = True` yapılırsa 5. hücre modeli kayıttan yükler.

Script dosyasına `mmm.py` adı verilmemeli; Meridian'ın arka planda kullandığı `mmm` paketiyle çakışıyor.

## Model ayarları

- ROI prior: `LogNormal(0.2, 0.9)`, bütün kanallar için aynı
- Zaman etkisi: otomatik knot seçimi (`enable_aks=True`)
- Adstock penceresi: varsayılan `max_lag=8` hafta
- MCMC: 4 zincir, `n_adapt=1000`, `n_burnin=1000`, `n_keep=1000`

## Sürümler

| Etiket | Açıklama |
|---|---|
| `v1-ilk-model` | 500 adımlık eğitim. Zaman etkisinde (`mu_t`) R-hat 1,43, tam yakınsamadı |
| `v2-yakinsamis-model` | 1000 adımlık eğitim. Bütün R-hat değerleri 1,1 civarı ve altında, health card: Passed |

## Güncel modelden ana bulgular (v2)

- Gelirin yaklaşık %77'si baseline'dan, %20'si ücretli medyadan geliyor. Toplam medya ROI'si yaklaşık 1,2.
- Channel0 ve Channel4 en yüksek ROI'li (~1,6) ve etkisi en uzun süren (yarı ömür 3,5 ile 4 hafta) kanallar.
- Channel3 bütçenin %40'ını alıyor ama ROI'si en düşük (~0,8) ve en doymuş kanal. Model bu bulgudan en emin olduğu kanal.
- Bütün ROI aralıkları 1'i kesiyor; yön güvenilir, büyüklükler belirsiz.
- Optimizasyon (sabit bütçe, ±%30 sınır): Channel3'ten %30 azaltma, Channel0, Channel4 ve Channel2'de %30 artırma, Channel1'de hafif azaltma. Aynı 220M bütçeyle medya katkısı 261M'den 267M'ye çıkıyor (+%2,5). Beş kanaldan dördü sınıra dayandığı için öneri yönü kuvvetli.

## Olası sonraki adımlar

- Toplam bütçe senaryosu: `opt.optimize(fixed_budget=False, target_mroi=...)`
- Farklı optimizasyon sınırları: `spend_constraint_lower` / `spend_constraint_upper`
- Uzun etkili kanallar için daha uzun adstock penceresi: `ModelSpec(max_lag=13)`
- Gerçek projede: lift testi ya da geo deney sonuçlarıyla prior kalibrasyonu