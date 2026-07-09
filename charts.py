"""Interactive Plotly charts for the yield-curve terminal.

Every figure is styled through theme.base_layout so the whole app reads as one
system. Semantic colors: nominal = green, real (TIPS) = blue, breakeven = amber,
forward = purple, model fit = cyan, comparison series = muted dashed.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import theme as T


# ---------------------------------------------------------------------------
# The curve itself
# ---------------------------------------------------------------------------
def curve_chart(curve_df, nss=None, compare_df=None, compare_label=None,
                y_range=None, title="", height=460):
    """Today's curve (green markers), optional NSS smooth fit (cyan), and an
    optional comparison curve (muted dashed)."""
    x = curve_df["Maturity (Years)"].values
    y = curve_df["Yield (%)"].values

    fig = go.Figure()
    if compare_df is not None:
        fig.add_trace(go.Scatter(
            x=compare_df["Maturity (Years)"], y=compare_df["Yield (%)"],
            mode="lines+markers", name=compare_label or "Comparison",
            line=dict(color=T.MUTED, width=1.6, dash="dash"),
            marker=dict(size=6, color=T.MUTED),
            hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>" +
                          (compare_label or "cmp") + "</extra>"))

    if nss is not None:
        grid = np.linspace(x.min(), x.max(), 200)
        fig.add_trace(go.Scatter(
            x=grid, y=nss["eval"](grid), mode="lines", name="NSS fit",
            line=dict(color=T.CYAN, width=1.5),
            hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>NSS</extra>"))

    fig.add_trace(go.Scatter(
        x=x, y=y, mode="lines+markers", name="Yield",
        line=dict(color=T.GREEN, width=2.4),
        marker=dict(size=8, color=T.GREEN, line=dict(color=T.BG, width=1)),
        hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>Spot</extra>"))

    fig = T.base_layout(fig, height=height, title=title)
    fig.update_layout(legend=dict(x=0.01, y=0.02, xanchor="left", yanchor="bottom",
                                  bgcolor="rgba(20,26,36,0.6)"))
    fig.update_xaxes(title="Maturity (Years)")
    fig.update_yaxes(title="Yield (%)", ticksuffix="%",
                     range=y_range)
    return fig


def interpolation_chart(xs, ys, interp, custom_mats=None):
    """Observed dots + interpolated line + optional custom-maturity markers."""
    grid = np.linspace(xs.min(), xs.max(), 250)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=grid, y=interp(grid), mode="lines",
                             name="Interpolated", line=dict(color=T.GREEN, width=2),
                             hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", name="Observed",
                             marker=dict(size=9, color=T.ACCENT,
                                         line=dict(color=T.BG, width=1)),
                             hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>Observed</extra>"))
    if custom_mats:
        cm = np.array(custom_mats, dtype=float)
        fig.add_trace(go.Scatter(
            x=cm, y=interp(cm), mode="markers", name="Custom query",
            marker=dict(size=11, color=T.PURPLE, symbol="diamond",
                        line=dict(color=T.BG, width=1)),
            hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>Query</extra>"))
    fig = T.base_layout(fig, height=440)
    fig.update_layout(legend=dict(x=0.01, y=0.02, yanchor="bottom",
                                  bgcolor="rgba(20,26,36,0.6)"))
    fig.update_xaxes(title="Maturity (Years)")
    fig.update_yaxes(title="Yield (%)", ticksuffix="%")
    return fig


# ---------------------------------------------------------------------------
# The historical surface (aesthetic centerpiece)
# ---------------------------------------------------------------------------
def history_surface(wide, max_dates=140):
    """3D surface of the curve through time. Color encodes yield level."""
    wide = wide.dropna(how="all")
    mats = np.array(sorted(wide.columns), dtype=float)
    grid = np.linspace(mats.min(), mats.max(), 40)

    # Subsample dates evenly to keep the mesh light.
    idx = wide.index
    step = max(1, len(idx) // max_dates)
    rows = wide.iloc[::step]

    Z, dates = [], []
    for d, row in rows.iterrows():
        vals = row.values.astype(float)
        ok = ~np.isnan(vals)
        if ok.sum() >= 2:
            Z.append(np.interp(grid, mats[ok], vals[ok]))
            dates.append(d)
    Z = np.array(Z)

    fig = go.Figure(go.Surface(
        z=Z, x=grid, y=dates, colorscale=T.TIME_SCALE,
        colorbar=dict(title="Yield %", outlinewidth=0,
                      tickfont=dict(color=T.MUTED), len=0.7),
        hovertemplate="%{x:.1f}Y · %{y|%b %Y}<br>%{z:.2f}%<extra></extra>",
        contours=dict(z=dict(show=True, color=T.BORDER, width=1,
                             usecolormap=False))))
    fig = T.base_layout(fig, height=560, legend=False)
    fig.update_layout(scene=dict(
        xaxis=dict(title="Maturity (Y)", backgroundcolor=T.PANEL,
                   gridcolor=T.GRID, color=T.MUTED),
        yaxis=dict(title="Date", backgroundcolor=T.PANEL,
                   gridcolor=T.GRID, color=T.MUTED),
        zaxis=dict(title="Yield %", backgroundcolor=T.PANEL,
                   gridcolor=T.GRID, color=T.MUTED),
        camera=dict(eye=dict(x=1.7, y=-1.5, z=0.7))))
    return fig


# ---------------------------------------------------------------------------
# Spread over time + recessions
# ---------------------------------------------------------------------------
def spread_chart(spread, recessions, label, height=440):
    """A spread (bps) through time with a zero (inversion) line and recession
    bands. `spread` is a pandas Series indexed by date."""
    fig = go.Figure()
    # recession bands
    for s, e in recessions:
        fig.add_vrect(x0=s, x1=e, fillcolor="rgba(179,188,203,0.14)",
                      line_width=0, layer="below")
    cur = spread.iloc[-1]
    color = T.RED if cur < 0 else T.GREEN
    fig.add_trace(go.Scatter(
        x=spread.index, y=spread.values, mode="lines",
        line=dict(color=T.BLUE, width=1.4), name=label,
        hovertemplate="%{x|%d %b %Y}: %{y:+.0f} bps<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=T.RED, width=1, dash="dash"))
    fig.add_trace(go.Scatter(
        x=[spread.index[-1]], y=[cur], mode="markers",
        marker=dict(size=10, color=color, line=dict(color=T.BG, width=1)),
        name=f"Now {cur:+.0f} bps",
        hovertemplate=f"Now: {cur:+.0f} bps<extra></extra>"))
    fig = T.base_layout(fig, height=height)
    fig.update_layout(legend=dict(x=0.01, y=0.02, yanchor="bottom",
                                  bgcolor="rgba(20,26,36,0.6)"))
    fig.update_yaxes(title="Spread (bps)")
    fig.update_xaxes(title="Date")
    return fig


# ---------------------------------------------------------------------------
# Forwards & the implied short-rate path
# ---------------------------------------------------------------------------
def forward_chart(t, spot, fwd, horizon):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=spot, mode="lines", name="Spot curve",
                             line=dict(color=T.GREEN, width=2.2),
                             hovertemplate="t=%{x:.1f}Y: %{y:.2f}%<extra>Spot</extra>"))
    fig.add_trace(go.Scatter(
        x=t, y=fwd, mode="lines", name=f"{horizon:g}Y forward (starts at t)",
        line=dict(color=T.PURPLE, width=2.2, dash="dot"),
        hovertemplate="t=%{x:.1f}Y: %{y:.2f}%<extra>Forward</extra>"))
    fig = T.base_layout(fig, height=460)
    fig.update_layout(legend=dict(x=0.01, y=0.02, yanchor="bottom",
                                  bgcolor="rgba(20,26,36,0.6)"))
    fig.update_xaxes(title="Starting maturity t (Years)")
    fig.update_yaxes(title="Yield (%)", ticksuffix="%")
    return fig


def implied_path_chart(starts, implied, spot0, step):
    """The market-implied path of the short rate: bars for each forward window,
    with the current short rate as a reference line."""
    fig = go.Figure()
    colors = [T.GREEN if v <= spot0 else T.RED for v in implied]
    fig.add_trace(go.Bar(
        x=[f"{int(s)}–{int(s+step)}Y" for s in starts], y=implied,
        marker_color=colors, name=f"Implied {step:g}Y rate",
        hovertemplate="%{x} forward: %{y:.2f}%<extra></extra>"))
    fig.add_hline(y=spot0, line=dict(color=T.ACCENT, width=1.4, dash="dash"),
                  annotation_text=f"Current {step:g}Y {spot0:.2f}%",
                  annotation_font=dict(color=T.ACCENT, family=T.FONT))
    fig = T.base_layout(fig, height=420, legend=False)
    fig.update_xaxes(title="Forward window (years ahead)")
    fig.update_yaxes(title="Implied rate (%)", ticksuffix="%")
    return fig


# ---------------------------------------------------------------------------
# PCA of curve moves
# ---------------------------------------------------------------------------
def pca_loadings_chart(pca):
    """Loadings of each principal factor across the maturity spectrum."""
    fig = go.Figure()
    colors = [T.GREEN, T.BLUE, T.PURPLE, T.AMBER, T.CYAN]
    for i, name in enumerate(pca["names"]):
        ev = pca["explained"][i]
        fig.add_trace(go.Scatter(
            x=pca["maturities"], y=pca["loadings"][i], mode="lines+markers",
            name=f"{name} ({ev:.0%})",
            line=dict(color=colors[i % len(colors)], width=2.2),
            marker=dict(size=6),
            hovertemplate="%{x:.2g}Y: %{y:.3f}<extra>" + name + "</extra>"))
    fig.add_hline(y=0, line=dict(color=T.BORDER, width=1))
    fig = T.base_layout(fig, height=440)
    fig.update_layout(legend=dict(x=0.99, y=0.99, xanchor="right",
                                  bgcolor="rgba(20,26,36,0.6)"))
    fig.update_xaxes(title="Maturity (Years)")
    fig.update_yaxes(title="Factor loading")
    return fig


def pca_variance_chart(pca):
    names = pca["names"]
    ev = pca["explained"]
    fig = go.Figure(go.Bar(
        x=names, y=ev * 100, marker_color=[T.GREEN, T.BLUE, T.PURPLE][:len(names)],
        text=[f"{e:.1%}" for e in ev], textposition="outside",
        textfont=dict(color=T.TEXT, family=T.FONT),
        hovertemplate="%{x}: %{y:.1f}% of variance<extra></extra>"))
    fig = T.base_layout(fig, height=320, legend=False)
    fig.update_yaxes(title="% of curve moves explained", ticksuffix="%",
                     range=[0, 100])
    return fig


def pca_scenario_chart(curve_df, maturities, shock_bps):
    """Base curve vs the PCA-scenario-shocked curve."""
    base_x = curve_df["Maturity (Years)"].values
    base_y = curve_df["Yield (%)"].values
    shocked = np.interp(maturities, base_x, base_y) + shock_bps / 100.0
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=base_x, y=base_y, mode="lines+markers",
                             name="Today", line=dict(color=T.MUTED, width=1.8),
                             marker=dict(size=6, color=T.MUTED),
                             hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>Today</extra>"))
    fig.add_trace(go.Scatter(x=maturities, y=shocked, mode="lines+markers",
                             name="Scenario", line=dict(color=T.ACCENT, width=2.4),
                             marker=dict(size=7, color=T.ACCENT),
                             hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>Scenario</extra>"))
    fig = T.base_layout(fig, height=440)
    fig.update_layout(legend=dict(x=0.01, y=0.02, yanchor="bottom",
                                  bgcolor="rgba(20,26,36,0.6)"))
    fig.update_xaxes(title="Maturity (Years)")
    fig.update_yaxes(title="Yield (%)", ticksuffix="%")
    return fig


# ---------------------------------------------------------------------------
# Mean reversion
# ---------------------------------------------------------------------------
def mean_reversion_chart(spread, mr, label):
    """Spread history with mean and ±1σ / ±2σ bands and the current point."""
    m, sd = mr["mean"], mr["std"]
    fig = go.Figure()
    for k, dash in [(2, "dot"), (1, "dash")]:
        for sign in (+1, -1):
            fig.add_hline(y=m + sign * k * sd,
                          line=dict(color=T.BORDER, width=1, dash=dash))
    fig.add_hline(y=m, line=dict(color=T.AMBER, width=1.2),
                  annotation_text=f"mean {m:+.0f}", annotation_position="right",
                  annotation_font=dict(color=T.AMBER, family=T.FONT))
    fig.add_trace(go.Scatter(x=spread.index, y=spread.values, mode="lines",
                             line=dict(color=T.BLUE, width=1.3), name=label,
                             hovertemplate="%{x|%d %b %Y}: %{y:+.0f} bps<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=[spread.index[-1]], y=[mr["current"]], mode="markers",
        marker=dict(size=11, color=T.ACCENT, line=dict(color=T.BG, width=1)),
        name=f"Now (z={mr['z']:+.2f})",
        hovertemplate=f"Now: {mr['current']:+.0f} bps · z={mr['z']:+.2f}<extra></extra>"))
    fig = T.base_layout(fig, height=440)
    fig.update_layout(legend=dict(x=0.01, y=0.02, yanchor="bottom",
                                  bgcolor="rgba(20,26,36,0.6)"))
    fig.update_yaxes(title="Spread (bps)")
    fig.update_xaxes(title="Date")
    return fig


# ---------------------------------------------------------------------------
# Inflation (US)
# ---------------------------------------------------------------------------
def inflation_chart(curve_df, tips_latest, be_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curve_df["Maturity (Years)"], y=curve_df["Yield (%)"],
        mode="lines+markers", name="Nominal", line=dict(color=T.GREEN, width=2.2),
        hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>Nominal</extra>"))
    fig.add_trace(go.Scatter(
        x=tips_latest["Maturity (Years)"], y=tips_latest["Real Yield (%)"],
        mode="lines+markers", name="Real (TIPS)", line=dict(color=T.BLUE, width=2.2),
        marker=dict(symbol="square", size=7),
        hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>Real</extra>"))
    fig.add_trace(go.Scatter(
        x=be_df["Maturity (Years)"], y=be_df["Breakeven (%)"],
        mode="lines+markers", name="Breakeven inflation",
        line=dict(color=T.AMBER, width=2.2, dash="dash"),
        marker=dict(symbol="triangle-up", size=8),
        hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>Breakeven</extra>"))
    fig.add_hline(y=2.0, line=dict(color=T.MUTED, width=1, dash="dot"),
                  annotation_text="Central-bank 2% target",
                  annotation_font=dict(color=T.MUTED, family=T.FONT))
    fig = T.base_layout(fig, height=460)
    fig.update_layout(legend=dict(x=0.99, y=0.99, xanchor="right",
                                  bgcolor="rgba(20,26,36,0.6)"))
    fig.update_xaxes(title="Maturity (Years)")
    fig.update_yaxes(title="Yield / Rate (%)", ticksuffix="%")
    return fig


def breakeven_history_chart(be_series):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=be_series.index, y=be_series.values, mode="lines",
                             line=dict(color=T.AMBER, width=1.4),
                             name="10Y breakeven",
                             hovertemplate="%{x|%b %Y}: %{y:.2f}%<extra></extra>"))
    fig.add_hline(y=2.0, line=dict(color=T.MUTED, width=1, dash="dot"),
                  annotation_text="2% target",
                  annotation_font=dict(color=T.MUTED, family=T.FONT))
    fig = T.base_layout(fig, height=320, legend=False)
    fig.update_yaxes(title="Breakeven (%)", ticksuffix="%")
    fig.update_xaxes(title="Date")
    return fig


# ---------------------------------------------------------------------------
# Scenario simulator (classic deformations)
# ---------------------------------------------------------------------------
def scenario_chart(curve_df, shocks):
    """Base curve plus each shocked curve."""
    x = curve_df["Maturity (Years)"].values
    y = curve_df["Yield (%)"].values
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="Base",
                             line=dict(color=T.TEXT, width=2.6),
                             marker=dict(size=6, color=T.TEXT),
                             hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>Base</extra>"))
    palette = [T.RED, T.BLUE, T.AMBER, T.PURPLE, T.GREEN, T.CYAN]
    for i, (label, delta) in enumerate(shocks.items()):
        fig.add_trace(go.Scatter(
            x=x, y=y + delta, mode="lines", name=label,
            line=dict(color=palette[i % len(palette)], width=1.8, dash="dash"),
            hovertemplate="%{x:.2g}Y: %{y:.2f}%<extra>" + label + "</extra>"))
    fig = T.base_layout(fig, height=480)
    fig.update_layout(legend=dict(x=0.01, y=0.02, yanchor="bottom",
                                  bgcolor="rgba(20,26,36,0.6)"))
    fig.update_xaxes(title="Maturity (Years)")
    fig.update_yaxes(title="Yield (%)", ticksuffix="%")
    return fig


def shock_profile_chart(maturities, shocks):
    """The shock magnitude (bps) each scenario applies across maturities."""
    fig = go.Figure()
    palette = [T.RED, T.BLUE, T.AMBER, T.PURPLE, T.GREEN, T.CYAN]
    for i, (label, delta) in enumerate(shocks.items()):
        fig.add_trace(go.Scatter(
            x=maturities, y=np.asarray(delta) * 100, mode="lines", name=label,
            line=dict(color=palette[i % len(palette)], width=1.8),
            hovertemplate="%{x:.2g}Y: %{y:+.0f} bps<extra>" + label + "</extra>"))
    fig.add_hline(y=0, line=dict(color=T.BORDER, width=1))
    fig = T.base_layout(fig, height=340)
    fig.update_layout(legend=dict(x=0.01, y=0.99, bgcolor="rgba(20,26,36,0.6)"))
    fig.update_xaxes(title="Maturity (Years)")
    fig.update_yaxes(title="Shock (bps)")
    return fig
