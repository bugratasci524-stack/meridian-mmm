# %%
# ============================================================
# 1. IMPORTLAR VE AYARLAR
# ============================================================
import os
os.chdir(r"C:\dev\meridian-mmm")           # calisma klasorunu proje klasorune sabitle
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"   # TensorFlow bilgi mesajlarini gizler, importlardan once olmali

import numpy as np
import pandas as pd

from meridian import backend
from meridian import constants
from meridian.data import data_frame_input_data_builder
from meridian.model import model, prior_distribution, spec
from meridian.analysis import visualizer, summarizer, optimizer
from meridian.analysis.review import reviewer
from meridian.schema.serde import meridian_serde

DATA_PATH = "data/geo_all_channels.csv"
OUT = "outputs"
MODEL_PATH = f"{OUT}/mmm_model.binpb"
os.makedirs(OUT, exist_ok=True)

# True yaparsan model yeniden egitilmez, kaydedilmis model yuklenir
USE_SAVED_MODEL = False


# %%
# ============================================================
# 2. VERIYI OKU VE KONTROL ET
# ============================================================
df = pd.read_csv(DATA_PATH)

# CSV'deki isimsiz index kolonunu at
df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

# Meridian tarihleri yyyy-mm-dd metin olarak bekler
df["time"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d")

print(df.shape)                                  # (6240, 18) beklenir
print(df["geo"].nunique(), "bolge")              # 40
print(df["time"].min(), "->", df["time"].max())  # 2021-01-25 -> 2024-01-15
print("Eksik deger:", df.isna().sum().sum())     # 0
print(df.dtypes)                                 # geo ve time disindakiler sayisal olmali


# %%
# ============================================================
# 3. VERIYI MERIDIAN FORMATINA CEVIR
# ============================================================
# KPI donusum adedi oldugu icin non_revenue. revenue_per_conversion
# verildigi icin ROI gelir cinsinden hesaplanir.
builder = data_frame_input_data_builder.DataFrameInputDataBuilder(
    kpi_type="non_revenue",
    default_kpi_column="conversions",
    default_revenue_per_kpi_column="revenue_per_conversion",
)

channels = ["Channel0", "Channel1", "Channel2", "Channel3", "Channel4"]

builder = (
    builder.with_kpi(df)
    .with_revenue_per_kpi(df)
    .with_population(df)
    .with_controls(df, control_cols=["sentiment_score_control", "competitor_sales_control"])
    .with_media(
        df,
        media_cols=[f"{c}_impression" for c in channels],      # etki gosterimden ogrenilir
        media_spend_cols=[f"{c}_spend" for c in channels],     # ROI harcamaya bolunerek hesaplanir
        media_channels=channels,
    )
    .with_non_media_treatments(df, non_media_treatment_cols=["Promo"])
    .with_organic_media(
        df,
        organic_media_cols=["Organic_channel0_impression"],
        organic_media_channels=["Organic_channel0"],
    )
)

data = builder.build()
print(data)


# %%
# ============================================================
# 4. PRIOR VE MODEL TANIMI
# ============================================================
# ROI prior: LogNormal(0.2, 0.9) -> ROI negatif olamaz, medyani ~1.2,
# genis belirsizlik. "Fikrim var ama zayif, veri konussun" demek.
# backend.np_float_dtype sayilari Meridian'in calistigi hassasiyete
# (float32 ya da float64) otomatik cevirir.
roi_mu = 0.2
roi_sigma = 0.9

prior = prior_distribution.PriorDistribution(
    roi_m=backend.tfd.LogNormal(
        backend.np_float_dtype(roi_mu),
        backend.np_float_dtype(roi_sigma),
        name=constants.ROI_M,
    )
)

model_spec = spec.ModelSpec(
    prior=prior,
    enable_aks=True,  # trend ve sezonsallik icin otomatik knot secimi
)


# %%
# ============================================================
# 5. MODELI EGIT (MCMC) YA DA KAYITLI MODELI YUKLE
# ============================================================
if USE_SAVED_MODEL and os.path.exists(MODEL_PATH):
    mmm = meridian_serde.load_meridian(MODEL_PATH)
    print("Kayitli model yuklendi.")
else:
    mmm = model.Meridian(input_data=data, model_spec=model_spec)

    # Veriyi gormeden modelin inanci (prior ile posterior'u kiyaslamak icin)
    mmm.sample_prior(500, seed=1)

    # Deneme ayarlari. Tam calistirma icin:
    # n_chains=10, n_adapt=1000, n_burnin=500, n_keep=1000
    mmm.sample_posterior(
        n_chains=4,
        n_adapt=500,
        n_burnin=500,
        n_keep=500,
        seed=1,
    )

    meridian_serde.save_meridian(mmm, MODEL_PATH)
    print("Model egitildi ve kaydedildi:", MODEL_PATH)


# %%
# ============================================================
# 6. MODEL SAGLIGI
# ============================================================
# R-hat 1.0'a yakin olmali, 1.2 ustu yakinsama sorunu demek.
# Posterior prior'dan ayrisiyorsa veri o parametre hakkinda bilgi vermis demek.
health = reviewer.ModelReviewer(mmm).run()
health.output_model_health_card(filename="health_card.html", filepath=OUT)

diag = visualizer.ModelDiagnostics(mmm)
diag.plot_rhat_boxplot().save(f"{OUT}/rhat.html")
diag.plot_prior_and_posterior_distribution().save(f"{OUT}/prior_vs_posterior.html")

fit = visualizer.ModelFit(mmm)
fit.plot_model_fit().save(f"{OUT}/model_fit.html")

print("Saglik ciktilari outputs/ klasorune kaydedildi.")


# %%
# ============================================================
# 7. SONUCLAR
# ============================================================
summ = summarizer.Summarizer(mmm)
summ.output_model_results_summary(
    "summary_output.html", OUT, "2021-01-25", "2024-01-15"
)

media_summary = visualizer.MediaSummary(mmm)
summary_table = media_summary.summary_table()
print(summary_table)
summary_table.to_csv(f"{OUT}/media_summary.csv", index=False)

media_summary.plot_roi_bar_chart().save(f"{OUT}/roi.html")
media_summary.plot_contribution_waterfall_chart().save(f"{OUT}/contribution.html")

media_effects = visualizer.MediaEffects(mmm)
media_effects.plot_response_curves().save(f"{OUT}/response_curves.html")
media_effects.plot_adstock_decay().save(f"{OUT}/adstock.html")

print("Sonuc ciktilari outputs/ klasorune kaydedildi.")


# %%
# ============================================================
# 8. BUTCE OPTIMIZASYONU
# ============================================================
# Varsayilan: toplam butce gecmis harcamaya esit, her kanal +-%30 bandinda.
opt = optimizer.BudgetOptimizer(mmm)
results = opt.optimize()
results.output_optimization_summary("optimization_output.html", OUT)

print("Optimizasyon ciktisi outputs/ klasorune kaydedildi.")