"""
Yield Curve Terminal
====================
An interactive Streamlit workbench over the US Treasury and Euro Area AAA
government curves. It reads what the bond market is pricing about future rates,
inflation, and recession risk — and adds the modelling layer used to *predict*
how the term structure moves: Nelson-Siegel-Svensson fitting, PCA of historical
curve moves, forward-implied rate paths, and spread mean-reversion.

Run with:  streamlit run app.py --server.headless true --server.port 8544
"""

import datetime as dt

import numpy as np
import pandas as pd
import streamlit as st

import theme as T
import charts
import analytics as A
import content as C

st.set_page_config(page_title="Yield Curve Terminal", page_icon="📉",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(T.inject_css(), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached data + analytics layer — keyed on config so re-runs are instant and
# the network only fires when country / window changes.
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data(country, start, end):
    latest, wide = A.build_curve(country, start, end)
    tips_latest, tips_wide = A.build_tips_curve(country, start, end)
    recessions = A.fetch_recessions(country, start, end)
    return dict(latest=latest, wide=wide, tips_latest=tips_latest,
                tips_wide=tips_wide, recessions=recessions)


@st.cache_data(show_spinner=False)
def compute_pca(wide, n):
    return A.pca_factors(wide, n)


# ---------------------------------------------------------------------------
# Sidebar — configuration form
# ---------------------------------------------------------------------------
COUNTRY_LABELS = {A.COUNTRIES[c]["label"]: c for c in A.COUNTRIES}

with st.sidebar:
    st.markdown("### ⚙︎ Configuration")
    with st.form("config"):
        country_label = st.selectbox("Market", list(COUNTRY_LABELS.keys()))
        st.caption("Which sovereign curve to analyze. **US** (FRED) adds TIPS "
                   "breakevens and NBER recession bands; **Euro Area AAA** (ECB) "
                   "and **Japan** (JGB, MOF) are nominal-only. Changing this "
                   "refetches everything.")
        country = COUNTRY_LABELS[country_label]

        hist_years = st.slider("History (years)", 2, 25, 8, 1)
        st.caption("Look-back window for the *History* surface, the spread charts, "
                   "**PCA factors** and **mean reversion**. Longer = steadier "
                   "statistics; shorter = regime-specific.")

        compare_days = st.slider("Compare vs N days ago", 5, 365, 30, 5)
        st.caption("The dashed reference curve on *Curve* — how the shape has "
                   "shifted over this many calendar days.")

        fwd_horizon = st.select_slider("Forward horizon (years)",
                                       [0.5, 1.0, 2.0, 3.0, 5.0], 1.0)
        st.caption("Window of the no-arbitrage **forward curve** on *Forwards* "
                   "(e.g. 5Y = the 5-year rate starting at each point). Capped at "
                   "5Y: these are the standard quoted tenors, and start + horizon "
                   "must stay within the 30Y end of the curve.")

        interp_kind = st.selectbox("Interpolation", ["linear", "cubic"], 0)
        st.caption("How yields between quoted maturities are filled. **Linear** "
                   "never overshoots between points — use it for numbers. "
                   "**Cubic** is smoother but can invent small humps — use it for "
                   "looks.")

        custom_mats_raw = st.text_input("Custom maturities (Y)", "4.5, 8, 12, 15, 25")
        st.caption("Extra maturities to price by interpolation on *Curve*.")

        with st.expander("Scenario shocks"):
            shock_bp = st.slider("Shock magnitude (bps)", 10, 200, 50, 5)
            pivot = st.slider("Steepener/flattener pivot (Y)", 2, 15, 5, 1)
            fly_center = st.slider("Butterfly center (Y)", 2, 20, 7, 1)
            st.caption("Drives the classic deformations on *Scenarios* — and the "
                       "P&L scenarios on *Rates Risk* "
                       "(parallel, steepener, flattener, butterfly).")

        with st.expander("Bond (Rates Risk)"):
            coupon = st.slider("Coupon (%)", 0.0, 10.0, 4.0, 0.25)
            bond_mat = st.slider("Maturity (Y)", 0.5, 30.0, 10.0, 0.5)
            notional = st.select_slider(
                "Notional", [100_000, 250_000, 500_000, 1_000_000, 5_000_000,
                             10_000_000], 1_000_000)
            st.caption("The bond priced off the curve on *Rates Risk*, where its "
                       "**duration, DV01, convexity, key-rate DV01** and "
                       "**scenario P&L** are computed. Semiannual coupons.")

        submitted = st.form_submit_button("▶  Run analysis", use_container_width=True)

    st.caption("Data: FRED (US Treasury/TIPS) · ECB Data Portal (Euro Area AAA). "
               "Educational use only — not investment advice.")

meta = A.country_meta(country)
custom_mats = [float(x) for x in custom_mats_raw.replace(" ", "").split(",")
               if x.strip()]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="app-title">YIELD CURVE <span class="accent">TERMINAL</span></div>'
    '<div class="app-sub">Term-structure analytics · NSS fit · PCA factors · '
    'forwards · mean reversion · scenario shocks</div>',
    unsafe_allow_html=True)
st.write("")

# ---------------------------------------------------------------------------
# Fetch + core analytics
# ---------------------------------------------------------------------------
today = dt.date.today()
start = (today - dt.timedelta(days=int(365.25 * hist_years))).strftime("%Y-%m-%d")
end = today.strftime("%Y-%m-%d")

try:
    with st.spinner(f"Fetching {meta['curve_name']} curve…"):
        D = load_data(country, start, end)
except A.DataUnavailable:
    st.markdown(
        '<div class="ticker-alert">⚠ The data provider returned no data (usually '
        "a temporary rate-limit or outage). Wait a minute and press Run again.</div>",
        unsafe_allow_html=True)
    st.stop()
except Exception as e:
    st.error(f"Could not load data: {e}")
    st.stop()

latest, wide = D["latest"], D["wide"]
interp, xs, ys = A.make_interpolator(latest, kind=interp_kind)
nss = A.fit_nss(latest)

s2, s10, s30, s5, s3 = (float(interp(m)) for m in (2, 10, 30, 5, 3))
spread_2s10s = (s10 - s2) * 100
spread_5s30s = (s30 - s5) * 100
short_rate = float(interp(xs.min()))
regime = "Inverted" if spread_2s10s < 0 else ("Flat" if abs(spread_2s10s) < 15 else "Normal")
regime_color = T.RED if regime == "Inverted" else (T.AMBER if regime == "Flat" else T.GREEN)

# ---- KPI cards -------------------------------------------------------------
cards = [
    T.kpi_card("Short rate", f"{short_rate:.2f}%", f"{xs.min()*12:.0f}M point", T.BLUE),
    T.kpi_card("10Y yield", f"{s10:.2f}%", "benchmark", T.GREEN),
    T.kpi_card("2s10s", f"{spread_2s10s:+.0f} bps",
               "recession bellwether", T.RED if spread_2s10s < 0 else T.GREEN),
    T.kpi_card("5s30s", f"{spread_5s30s:+.0f} bps", "long-end slope", T.PURPLE),
    T.kpi_card("Curvature", f"{nss['curvature']:+.2f}", "NSS 2-5-10 fly", T.CYAN),
    T.kpi_card("Regime", regime, f"NSS fit ±{nss['rmse_bps']:.1f} bps", regime_color),
]
st.markdown('<div class="kpi-row">' + "".join(cards) + "</div>", unsafe_allow_html=True)
st.caption(f"{meta['curve_name']} · {len(wide):,} daily curves · "
           f"{wide.index[0].date()} → {wide.index[-1].date()} · currency {meta['currency']}")

# ---- Maturity strip --------------------------------------------------------
chips = []
for i, (_, r) in enumerate(latest.iterrows()):
    m = r["Maturity (Years)"]
    lbl = f"{m*12:.0f}M" if m < 1 else f"{m:.0f}Y"
    color = T.ASSET_COLORS[i % len(T.ASSET_COLORS)]
    chips.append(
        f'<div class="chip"><span class="dot" style="background:{color}"></span>'
        f'<span class="tkr">{lbl}</span><span class="desc">{r["Yield (%)"]:.2f}%</span></div>')
st.markdown('<div class="asset-strip">' + "".join(chips) + "</div>", unsafe_allow_html=True)
st.write("")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
def how_to_read(key):
    """Render a collapsible 'how to read this' note under a chart."""
    with st.expander("ℹ️  How to read this"):
        st.markdown(C.HOW_TO_READ[key])


(tab_guide, tab_curve, tab_hist, tab_fwd, tab_pca, tab_mr, tab_infl, tab_scen,
 tab_rates) = st.tabs(
    ["📖 Guide", "📈 Curve", "🌐 History", "🔮 Forwards", "🧬 Factors (PCA)",
     "📉 Mean Reversion", "💰 Inflation", "⚡ Scenarios", "⚖️ Rates Risk"])

# ---- Guide -----------------------------------------------------------------
with tab_guide:
    st.markdown(C.GUIDE)

# ---- Curve -----------------------------------------------------------------
with tab_curve:
    ref_date = today - dt.timedelta(days=int(compare_days))
    past_mask = wide.index <= pd.Timestamp(ref_date)
    compare_df, compare_label = None, None
    if past_mask.any():
        compare_df = A.curve_from_row(wide[past_mask].iloc[-1])
        compare_label = f"{wide[past_mask].index[-1].date()}"

    st.markdown('<div class="section-tag">Current curve · NSS model fit</div>',
                unsafe_allow_html=True)
    st.plotly_chart(charts.curve_chart(
        latest, nss=nss, compare_df=compare_df,
        compare_label=f"{compare_days}d ago ({compare_label})" if compare_label else None,
        title=""), use_container_width=True)

    st.markdown(T.signal_box(
        f"{regime} curve",
        f"Front end near <b>{short_rate:.2f}%</b>, 10Y at <b>{s10:.2f}%</b>, "
        f"2s10s <b>{spread_2s10s:+.0f} bps</b>. The Nelson-Siegel-Svensson fit "
        f"(RMSE {nss['rmse_bps']:.1f} bps) reads level <b>{nss['level']:.2f}%</b>, "
        f"slope <b>{nss['slope']:+.2f}%</b>, curvature <b>{nss['curvature']:+.2f}</b>. "
        + ("An inverted curve has preceded every US recession in the last 60 years."
           if spread_2s10s < 0 else
           "A positively-sloped curve is the market's base case for steady growth."),
        accent=regime_color), unsafe_allow_html=True)
    how_to_read("curve")

    st.markdown('<div class="section-tag">Interpolation & custom pricing</div>',
                unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.plotly_chart(charts.interpolation_chart(xs, ys, interp, custom_mats),
                        use_container_width=True)
    with c2:
        rows = [(f"{m:g}Y", f"{float(interp(m)):.2f}%") for m in custom_mats]
        st.dataframe(pd.DataFrame(rows, columns=["Maturity", "Interp. yield"]),
                     use_container_width=True, hide_index=True)
        spr = A.custom_spreads(interp, [(2, 10), (5, 30), (3, 10), (2, 5)])
        st.dataframe(pd.DataFrame([(l, f"{b:+.0f} bps") for l, b in spr],
                                  columns=["Spread", "bps"]),
                     use_container_width=True, hide_index=True)
    how_to_read("interpolation")

# ---- History ---------------------------------------------------------------
with tab_hist:
    st.markdown('<div class="section-tag">Curve through time (3D surface)</div>',
                unsafe_allow_html=True)
    st.plotly_chart(charts.history_surface(wide), use_container_width=True)
    how_to_read("surface")

    st.markdown('<div class="section-tag">Interactive explorer</div>',
                unsafe_allow_html=True)
    curves = A.daily_curves(wide)
    dates = sorted(curves.keys())
    y_lo, y_hi = float(wide.min().min()) - 0.3, float(wide.max().max()) + 0.3
    e1, e2, e3 = st.columns([2, 2, 1])
    primary = e1.select_slider("Date", dates, value=dates[-1])
    compare = e2.select_slider("Compare", dates, value=dates[0])
    show_cmp = e3.checkbox("Show comparison", True)
    st.plotly_chart(charts.curve_chart(
        curves[primary], compare_df=curves[compare] if show_cmp else None,
        compare_label=compare if show_cmp else None,
        y_range=[y_lo, y_hi], title=f"{primary}"), use_container_width=True)
    how_to_read("explorer")

    st.markdown('<div class="section-tag">2s/10s spread & recession signal</div>',
                unsafe_allow_html=True)
    spread = A.spread_series(wide, 2, 10)
    st.plotly_chart(charts.spread_chart(spread, D["recessions"], "2s/10s"),
                    use_container_width=True)
    if not D["recessions"]:
        st.caption("Recession bands available for the US only.")
    how_to_read("spread")

# ---- Forwards --------------------------------------------------------------
with tab_fwd:
    st.markdown('<div class="section-tag">Spot vs forward curve</div>',
                unsafe_allow_html=True)
    t, spot, fwd = A.forward_curve(interp, float(fwd_horizon), xs.min(), 30.0)
    st.plotly_chart(charts.forward_chart(t, spot, fwd, float(fwd_horizon)),
                    use_container_width=True)
    how_to_read("forward")

    st.markdown('<div class="section-tag">Market-implied short-rate path</div>',
                unsafe_allow_html=True)
    step = 1.0
    starts, implied, spot0 = A.implied_short_rate_path(interp, max_year=10, step=step)
    st.plotly_chart(charts.implied_path_chart(starts, implied, spot0, step),
                    use_container_width=True)
    peak_i = int(np.argmax(implied))
    trough_i = int(np.argmin(implied))
    direction = ("cuts" if implied[trough_i] < spot0 - 0.1 else
                 "hikes" if implied[peak_i] > spot0 + 0.1 else "little change")
    st.markdown(T.signal_box(
        "What the curve predicts",
        f"Today's 1Y rate is <b>{spot0:.2f}%</b>. The no-arbitrage curve implies "
        f"the 1Y rate reaching <b>{implied.min():.2f}%</b> at its low and "
        f"<b>{implied.max():.2f}%</b> at its high over the next decade — the "
        f"market is pricing <b>{direction}</b>. These forwards are the market's "
        "own forecast, not a guarantee: realized rates routinely differ.",
        accent=T.PURPLE), unsafe_allow_html=True)
    how_to_read("implied_path")

# ---- PCA -------------------------------------------------------------------
with tab_pca:
    try:
        pca = compute_pca(wide, 3)
    except A.CurveDataError as e:
        st.warning(str(e))
        pca = None

    if pca is not None:
        st.markdown('<div class="section-tag">How the curve moves — principal factors</div>',
                    unsafe_allow_html=True)
        p1, p2 = st.columns([1, 2])
        with p1:
            st.plotly_chart(charts.pca_variance_chart(pca), use_container_width=True)
        with p2:
            st.plotly_chart(charts.pca_loadings_chart(pca), use_container_width=True)
        st.markdown(T.signal_box(
            "Reading the factors",
            f"Over the last {hist_years}y, <b>{pca['explained'][0]:.0%}</b> of daily "
            f"curve moves are a parallel <b>Level</b> shift, "
            f"<b>{pca['explained'][1]:.0%}</b> a <b>Slope</b> (steepen/flatten) move, "
            f"and <b>{pca['explained'][2]:.0%}</b> a <b>Curvature</b> (belly) move. "
            "Together these three shapes explain almost every realistic move — so a "
            "forecast of the whole curve reduces to a view on just these three numbers.",
            accent=T.GREEN), unsafe_allow_html=True)
        how_to_read("pca")

        st.markdown('<div class="section-tag">Scenario builder — shock the factors</div>',
                    unsafe_allow_html=True)
        st.caption("Move each factor in units of its historical daily σ; the curve "
                   "reshapes the way that factor empirically moves it.")
        sc = st.columns(len(pca["names"]))
        sigma_moves = []
        for i, name in enumerate(pca["names"]):
            sigma_moves.append(sc[i].slider(
                f"{name} (σ)", -5.0, 5.0, 0.0, 0.5, key=f"pca_{name}"))
        mats_p, shock = A.pca_scenario_shock(pca, sigma_moves)
        st.plotly_chart(charts.pca_scenario_chart(latest, mats_p, shock),
                        use_container_width=True)
        how_to_read("pca_scenario")

# ---- Mean reversion --------------------------------------------------------
with tab_mr:
    st.markdown('<div class="section-tag">Spread mean reversion</div>',
                unsafe_allow_html=True)
    SPREAD_CHOICES = {"2s/10s": (2, 10), "5s/30s": (5, 30), "3s/10s": (3, 10),
                      "2s/5s": (2, 5)}
    which = st.radio("Spread", list(SPREAD_CHOICES.keys()), horizontal=True)
    a, b = SPREAD_CHOICES[which]
    sp = A.spread_series(wide, a, b)
    try:
        mr = A.mean_reversion(sp)
        st.plotly_chart(charts.mean_reversion_chart(sp, mr, which),
                        use_container_width=True)
        hl = (f"{mr['half_life_days']:.0f} trading days"
              if np.isfinite(mr["half_life_days"]) else "no reversion detected")
        if mr["z"] > 1:
            lean = (f"rich vs history (z={mr['z']:+.2f}) — statistically it tends "
                    f"to fall back toward its {mr['mean']:+.0f} bps mean")
            acc = T.RED
        elif mr["z"] < -1:
            lean = (f"cheap vs history (z={mr['z']:+.2f}) — statistically it tends "
                    f"to rise back toward its {mr['mean']:+.0f} bps mean")
            acc = T.GREEN
        else:
            lean = f"near its historical mean (z={mr['z']:+.2f}) — no strong pull"
            acc = T.AMBER
        st.markdown(T.signal_box(
            f"{which}: {mr['current']:+.0f} bps",
            f"The spread is <b>{lean}</b>. AR(1) persistence ρ={mr['rho']:.3f} "
            f"implies a mean-reversion half-life of <b>{hl}</b>. "
            "Mean reversion is a statistical tendency over the estimation window, "
            "not a timing signal.",
            accent=acc), unsafe_allow_html=True)
        how_to_read("mean_reversion")
    except A.CurveDataError as e:
        st.warning(str(e))

# ---- Inflation -------------------------------------------------------------
with tab_infl:
    if D["tips_latest"] is None:
        st.markdown('<div class="section-tag">Inflation decomposition</div>',
                    unsafe_allow_html=True)
        st.info(f"Real (inflation-protected) yields are not published as a free "
                f"curve for {meta['label']}. Breakeven inflation is available for "
                "the US market only — switch Market to United States in the sidebar.")
    else:
        tips_latest, tips_wide = D["tips_latest"], D["tips_wide"]
        be = A.breakevens(interp, tips_latest)
        st.markdown('<div class="section-tag">Nominal · Real · Breakeven inflation</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(charts.inflation_chart(latest, tips_latest, be),
                        use_container_width=True)
        be10 = float(be.loc[be["Maturity (Years)"] == 10, "Breakeven (%)"].iloc[0]) \
            if (be["Maturity (Years)"] == 10).any() else float(be["Breakeven (%)"].iloc[-1])
        st.markdown(T.signal_box(
            "Inflation the market is pricing",
            f"The 10Y breakeven sits at <b>{be10:.2f}%</b> — the average annual CPI "
            "the bond market expects over ten years. Above 2% means the market sees "
            "the Fed overshooting its target; below, undershooting.",
            accent=T.AMBER), unsafe_allow_html=True)
        how_to_read("inflation")

        if 10 in tips_wide.columns and 10 in wide.columns:
            be_series = (wide[10] - tips_wide[10]).dropna()
            st.markdown('<div class="section-tag">10Y breakeven over time</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(charts.breakeven_history_chart(be_series),
                            use_container_width=True)
            how_to_read("breakeven_history")

# ---- Scenarios -------------------------------------------------------------
with tab_scen:
    st.markdown('<div class="section-tag">Curve deformation simulator</div>',
                unsafe_allow_html=True)
    mats = latest["Maturity (Years)"].values
    shocks = A.shock_profiles(mats, shock_bp / 100.0, pivot=float(pivot),
                              butterfly_center=float(fly_center))
    st.plotly_chart(charts.scenario_chart(latest, shocks), use_container_width=True)
    st.markdown('<div class="section-tag">Shock profiles (bps by maturity)</div>',
                unsafe_allow_html=True)
    st.plotly_chart(charts.shock_profile_chart(mats, shocks), use_container_width=True)
    how_to_read("scenarios")

# ---- Rates Risk ------------------------------------------------------------
with tab_rates:
    ccy = {"USD": "$", "EUR": "€", "JPY": "¥"}.get(meta["currency"], "")
    risk = A.bond_risk(latest, coupon, bond_mat, notional, freq=2, kind=interp_kind)
    st.markdown('<div class="section-tag">Bond risk · duration · DV01 · convexity</div>',
                unsafe_allow_html=True)
    st.caption(f"A **{coupon:.2f}%** semiannual bond maturing in **{bond_mat:g}Y**, "
               f"**{ccy}{notional:,.0f}** notional, priced off the current curve "
               "(treated as a continuously-compounded zero curve). All measures are "
               "computed by bump-and-reprice.")
    cards = [
        T.kpi_card("Price", f"{risk['per100']:.2f}",
                   f"per 100 · {ccy}{risk['price']:,.0f}", T.GREEN),
        T.kpi_card("Mod. duration", f"{risk['mod_duration']:.2f}", "years", T.BLUE),
        T.kpi_card("DV01", f"{ccy}{risk['dv01']:,.0f}", "per 1bp move", T.ACCENT),
        T.kpi_card("Convexity", f"{risk['convexity']:.1f}", "2nd-order", T.PURPLE),
    ]
    st.markdown('<div class="kpi-row">' + "".join(cards) + "</div>",
                unsafe_allow_html=True)

    st.markdown('<div class="section-tag">Price vs yield — convexity</div>',
                unsafe_allow_html=True)
    shifts, prices, dur_line, _ = A.price_yield_profile(
        latest, coupon, bond_mat, notional, kind=interp_kind)
    st.plotly_chart(charts.price_yield_chart(shifts, prices, dur_line, risk, notional),
                    use_container_width=True)
    how_to_read("price_yield")

    st.markdown('<div class="section-tag">Key-rate DV01 — where the risk sits</div>',
                unsafe_allow_html=True)
    krd = A.key_rate_dv01(latest, coupon, bond_mat, notional, kind=interp_kind)
    st.plotly_chart(charts.key_rate_chart(krd), use_container_width=True)
    how_to_read("key_rate")

    st.markdown('<div class="section-tag">Scenario P&L</div>', unsafe_allow_html=True)
    shocks_r = A.shock_profiles(latest["Maturity (Years)"].values, shock_bp / 100.0,
                                pivot=float(pivot), butterfly_center=float(fly_center))
    _, pnl_rows = A.scenario_bond_pnl(latest, shocks_r, coupon, bond_mat, notional,
                                      kind=interp_kind, risk=risk)
    st.plotly_chart(charts.scenario_pnl_chart(pnl_rows), use_container_width=True)
    par = next((r for r in pnl_rows if r["approx"]), None)
    if par:
        a = par["approx"]
        st.markdown(T.signal_box(
            "Why convexity matters",
            f"Under <b>{par['scenario']}</b> the bond's exact P&L is "
            f"<b>{ccy}{par['pnl']:+,.0f}</b>. Duration alone predicts "
            f"<b>{ccy}{a['dur_only']:+,.0f}</b>; adding convexity gives "
            f"<b>{ccy}{a['dur_cvx']:+,.0f}</b> — almost exact. Convexity is the "
            "curvature duration misses, and it always works in the holder's "
            "favour: gains a little bigger, losses a little smaller.",
            accent=T.PURPLE), unsafe_allow_html=True)
    how_to_read("scenario_pnl")
