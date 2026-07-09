# 📉 Yield Curve Terminal

**A Bloomberg-style workbench for reading and forecasting the term structure of interest rates.**

The yield curve is the single most information-dense chart in markets — it prices, all at once, what the market expects for **policy rates, growth, inflation and recession**. This tool pulls those expectations out of live US Treasury and Euro-area curves and layers on the models used to *forecast how the curve moves*.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3d9bff?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-app-ff4d5e?logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/data-FRED%20%C2%B7%20ECB-12e29a" alt="Data">
  <img src="https://img.shields.io/badge/license-MIT-ff9e1b" alt="License">
</p>

> 🔗 **Live demo:** _coming soon_ · 🎓 Educational use only — not investment advice.

---

## Why it's interesting

Most yield-curve charts just *show* the curve. This one *interprets and projects* it, using four complementary engines that each cover the others' blind spots:

| Engine | Answers | Method |
|---|---|---|
| **Forwards** | What is the market *already* pricing? | No-arbitrage forward rates & the implied policy-rate path |
| **PCA** | *How* does the curve move? | Principal components → Level / Slope / Curvature (~99% of moves) |
| **Nelson-Siegel-Svensson** | What's the clean *shape*? | Parametric fit; smooths, extrapolates >30Y, reads off 3 factors |
| **Mean reversion** | Is a spread stretched? | AR(1) z-score & half-life on key spreads (2s10s, 5s30s…) |

Together they turn "I think rates will fall" into a structured, measurable view.

## Features

- **📈 Curve** — live curve + NSS model fit + comparison to N days ago; interpolation and custom-maturity pricing.
- **🌐 History** — a 3D surface of the curve through time, an interactive date explorer, and the **2s10s spread vs NBER recessions**.
- **🔮 Forwards** — spot vs forward curves and the **market-implied path of the short rate** (priced-in cuts/hikes).
- **🧬 Factors (PCA)** — Level / Slope / Curvature decomposition with a **σ-shock scenario builder**.
- **📉 Mean Reversion** — z-score and mean-reversion half-life for the key spreads.
- **💰 Inflation** (US) — Nominal / Real (TIPS) / **Breakeven inflation** vs the 2% target.
- **⚡ Scenarios** — classic curve deformations (parallel, steepener, flattener, butterfly).
- **📖 Guide** — an in-app guide + "how to read this" notes on every chart, so a non-specialist can use it.

## Data

- **US Treasury** (nominal, TIPS) and **NBER recessions** — [FRED](https://fred.stlouisfed.org/).
- **Euro-area AAA government curve** — [ECB Data Portal](https://data.ecb.europa.eu/).
- Free, no API key. Nothing is fabricated: missing values are shown, never invented.

## Tech stack

`Python` · `Streamlit` · `Plotly` · `NumPy` / `pandas` · `SciPy` (least-squares NSS fit, interpolation) · a modular design (`theme` / `analytics` / `charts` / `content` / `app`) that keeps pure math testable and the UI thin.

## Run it locally

```bash
git clone https://github.com/gianlucav03/yield-curve-predictor.git
cd yield-curve-predictor
pip install -r requirements.txt
streamlit run app.py
```

The app opens in your browser and fetches the latest curves on load (a few seconds).

## Project structure

```
theme.py       # single source of visual truth (palette, CSS, Plotly layout)
analytics.py   # pure functions: data fetch, NSS fit, PCA, forwards, mean reversion
charts.py      # Plotly chart builders
content.py     # in-app guide & "how to read this" copy
app.py         # Streamlit wiring: sidebar → cached compute → KPIs → tabs
```

## Disclaimer

For educational and illustrative purposes only. Nothing here is investment advice. Forwards and mean-reversion signals are market expectations and statistical tendencies, not forecasts of realized rates.

## License

[MIT](LICENSE) © gianluca v
