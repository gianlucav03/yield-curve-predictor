"""
Pure analytics for the yield-curve terminal — no Streamlit, no plotting.

Everything here is cacheable and testable in isolation: data fetching from the
official free providers (FRED for the US, the ECB Data Portal for the euro
area), curve construction and interpolation, no-arbitrage forward rates,
Nelson-Siegel-Svensson curve fitting, PCA of historical curve moves, spread
mean-reversion statistics, breakeven inflation, and scenario shocks.

Data integrity is non-negotiable: we never fabricate a value. Official curve
series occasionally return empty for a valid maturity (holiday buffers, provider
hiccups); we retry each empty series individually and, only if *everything*
comes back empty, raise a transient `DataUnavailable` telling the user to retry
— never a "bad input" error, because the maturities are fixed, not user-typed.
"""

import time
from io import StringIO

import numpy as np
import pandas as pd
import requests
from scipy.interpolate import interp1d
from scipy.optimize import least_squares



# ===========================================================================
# Errors
# ===========================================================================
class DataUnavailable(Exception):
    """Every series came back empty — a transient provider issue, retry later."""


class CurveDataError(Exception):
    """A specific, named data problem (message is safe to show the user)."""


# ===========================================================================
# Country / provider configuration
# ===========================================================================
# Each country declares its data provider and the maturity grid we query.
# `nominal` maps a label -> (provider code, maturity in years). US extras
# (`tips`, `recession`) power inflation and recession features; euro area has
# no free equivalent, so those features degrade gracefully to "not available".
COUNTRIES = {
    "US": {
        "label": "United States",
        "curve_name": "US Treasury",
        "provider": "fred",
        "currency": "USD",
        "nominal": {
            "1M": ("DGS1MO", 1 / 12), "3M": ("DGS3MO", 3 / 12),
            "6M": ("DGS6MO", 6 / 12), "1Y": ("DGS1", 1.0),
            "2Y": ("DGS2", 2.0), "3Y": ("DGS3", 3.0), "5Y": ("DGS5", 5.0),
            "7Y": ("DGS7", 7.0), "10Y": ("DGS10", 10.0),
            "20Y": ("DGS20", 20.0), "30Y": ("DGS30", 30.0),
        },
        "tips": {
            "5Y": ("DFII5", 5.0), "7Y": ("DFII7", 7.0), "10Y": ("DFII10", 10.0),
            "20Y": ("DFII20", 20.0), "30Y": ("DFII30", 30.0),
        },
        "recession": "USREC",
    },
    "EA": {
        "label": "Euro Area (AAA)",
        "curve_name": "Euro Area AAA Govt",
        "provider": "ecb",
        "currency": "EUR",
        "nominal": {
            "3M": ("SR_3M", 3 / 12), "6M": ("SR_6M", 6 / 12),
            "1Y": ("SR_1Y", 1.0), "2Y": ("SR_2Y", 2.0), "3Y": ("SR_3Y", 3.0),
            "5Y": ("SR_5Y", 5.0), "7Y": ("SR_7Y", 7.0), "10Y": ("SR_10Y", 10.0),
            "15Y": ("SR_15Y", 15.0), "20Y": ("SR_20Y", 20.0),
            "30Y": ("SR_30Y", 30.0),
        },
        "tips": None,
        "recession": None,
    },
}


def country_meta(country):
    if country not in COUNTRIES:
        raise CurveDataError(f"Unknown country '{country}'.")
    return COUNTRIES[country]


# ===========================================================================
# Low-level fetchers (one series each) — with individual retry
# ===========================================================================
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
ECB_URL = "https://data-api.ecb.europa.eu/service/data/YC"
# ECB AAA spot-rate series key template (flowRef=YC is in the base URL):
#   B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y  -> Euro area AAA, 10-year spot rate.
ECB_KEY = "B.U2.EUR.4F.G_N_A.SV_C_YM.{code}"

# NB: do NOT set a custom/browser-like User-Agent. FRED's WAF (fredgraph.csv)
# tarpits requests whose UA is a custom string or a browser string ("Mozilla…")
# — they hang until read-timeout — while it answers the default requests UA
# ("python-requests/x.y") instantly. Verified empirically. So we send no UA
# override and let requests use its default, which FRED accepts.
def _get(url, timeout=10):
    return requests.get(url, timeout=timeout)


def _fetch_fred(code, start, end, retries=2):
    """Download one FRED series as a clean date-indexed Series of yields (%)."""
    url = f"{FRED_URL}?id={code}&cosd={start}&coed={end}"
    last_exc = None
    for attempt in range(retries):
        try:
            raw = pd.read_csv(StringIO(_get(url).text))
            raw["observation_date"] = pd.to_datetime(raw["observation_date"])
            # FRED marks missing observations with "." (text) — coerce to NaN.
            raw[code] = pd.to_numeric(raw[code], errors="coerce")
            s = raw.dropna().set_index("observation_date")[code]
            if not s.empty:
                return s
        except Exception as e:  # network / parse hiccup — retry
            last_exc = e
        time.sleep(1.0)
    if last_exc is not None and retries:
        # Exhausted retries with real errors; surface as transient.
        return pd.Series(dtype=float)
    return pd.Series(dtype=float)


def _fetch_ecb(code, start, end, retries=2):
    """Download one ECB yield-curve spot rate as a date-indexed Series (%)."""
    key = ECB_KEY.format(code=code)
    url = f"{ECB_URL}/{key}?startPeriod={start}&endPeriod={end}&format=csvdata"
    for attempt in range(retries):
        try:
            r = _get(url)
            if r.status_code == 200 and r.text.lstrip().startswith("KEY"):
                df = pd.read_csv(StringIO(r.text))
                s = pd.Series(
                    pd.to_numeric(df["OBS_VALUE"], errors="coerce").values,
                    index=pd.to_datetime(df["TIME_PERIOD"]),
                ).dropna().sort_index()
                if not s.empty:
                    return s
        except Exception:
            pass
        time.sleep(1.0)
    return pd.Series(dtype=float)


def _fetch_one(provider, code, start, end):
    return _fetch_fred(code, start, end) if provider == "fred" \
        else _fetch_ecb(code, start, end)


# ===========================================================================
# Curve construction
# ===========================================================================
def _build_from_map(provider, series_map, start, end):
    """Fetch every maturity in `series_map`. Return a wide DataFrame
    (index=date, columns=maturity-in-years). Retries empty series once more
    individually, then classifies total failure as transient."""
    by_maturity = {}
    missing = []
    consecutive_empty = 0
    for i, (label, (code, maturity)) in enumerate(series_map.items()):
        s = _fetch_one(provider, code, start, end)
        if s.empty:  # one extra individual retry before giving up on it
            time.sleep(0.5)
            s = _fetch_one(provider, code, start, end)
        if s.empty:
            missing.append(label)
            consecutive_empty += 1
            # Fail fast: if the first several requests all come back empty, the
            # provider is down or throttling us. Bail immediately instead of
            # grinding through every remaining maturity (which, with timeouts,
            # can take many minutes) before giving the same verdict.
            if by_maturity == {} and consecutive_empty >= 3:
                raise DataUnavailable(
                    "The data provider isn't responding (temporary rate-limit or "
                    "outage). Wait a minute and press Run again."
                )
        else:
            by_maturity[maturity] = s
            consecutive_empty = 0
        # Small courtesy gap between requests to avoid burst rate-limiting.
        time.sleep(0.1)

    if not by_maturity:
        # Nothing at all came back — treat as a transient provider outage.
        raise DataUnavailable(
            "The data provider returned no data for any maturity (usually a "
            "temporary rate-limit or outage). Wait a minute and press Run again."
        )
    wide = pd.DataFrame(by_maturity).sort_index(axis=1)
    return wide, missing


def build_curve(country, start, end):
    """Fetch the full nominal curve history for a country.

    Returns (latest_curve_df, wide_history_df). `latest` has columns
    ['Maturity (Years)', 'Yield (%)']; `wide` is indexed by date with maturity
    (years) columns.
    """
    meta = country_meta(country)
    wide, _ = _build_from_map(meta["provider"], meta["nominal"], start, end)
    wide = wide.dropna(how="all")
    if wide.empty:
        raise DataUnavailable("No curve observations in the requested window.")
    latest = curve_from_row(wide.dropna(how="all").iloc[-1])
    return latest, wide


def build_tips_curve(country, start, end):
    """Fetch the real (inflation-protected) curve history. US only.
    Returns (latest_real_df, wide_history_df) or (None, None) if unsupported."""
    meta = country_meta(country)
    if not meta.get("tips"):
        return None, None
    wide, _ = _build_from_map(meta["provider"], meta["tips"], start, end)
    wide = wide.dropna(how="all")
    if wide.empty:
        return None, None
    latest = wide.iloc[-1].dropna().rename_axis("Maturity (Years)") \
        .reset_index(name="Real Yield (%)")
    return latest, wide


def fetch_recessions(country, start, end):
    """Return recession (start, end) date pairs, or [] if unsupported."""
    meta = country_meta(country)
    code = meta.get("recession")
    if not code:
        return []
    rec = _fetch_fred(code, start, end)
    if rec.empty:
        return []
    changes = (rec == 1).astype(int).diff().fillna(0)
    starts = list(rec.index[changes == 1])
    ends = list(rec.index[changes == -1])
    if len(starts) > len(ends):
        ends.append(rec.index[-1])
    return list(zip(starts, ends))


def curve_from_row(row):
    """One wide-history row -> tidy ['Maturity (Years)', 'Yield (%)'] frame."""
    return (row.dropna().rename_axis("Maturity (Years)")
            .reset_index(name="Yield (%)"))


def daily_curves(wide):
    """Dict {date-string: tidy curve df} for the interactive explorer."""
    wide = wide.dropna(how="all")
    return {d.strftime("%Y-%m-%d"): curve_from_row(row)
            for d, row in wide.iterrows()}


# ===========================================================================
# Interpolation & spreads
# ===========================================================================
def make_interpolator(curve_df, kind="linear"):
    """Callable yield(maturity) from an observed curve, extrapolating flat-ish
    past the ends via linear extrapolation."""
    x = curve_df["Maturity (Years)"].values.astype(float)
    y = curve_df["Yield (%)"].values.astype(float)
    order = np.argsort(x)
    return interp1d(x[order], y[order], kind=kind, fill_value="extrapolate"), \
        x[order], y[order]


def custom_spreads(interp, pairs):
    """[(short, long)] -> [(label, spread_bps)] using the interpolator."""
    out = []
    for short, long in pairs:
        bps = (float(interp(long)) - float(interp(short))) * 100
        out.append((f"{short:g}s/{long:g}s", bps))
    return out


def spread_series(wide, short, long):
    """Historical (long - short) spread in bps from wide history, interpolating
    per-maturity when an exact column is absent."""
    def col(m):
        if m in wide.columns:
            return wide[m]
        # linear interpolate across available columns for each date
        cols = np.array(sorted(wide.columns))
        vals = wide[cols].values
        out = np.full(len(wide), np.nan)
        for i, rowvals in enumerate(vals):
            ok = ~np.isnan(rowvals)
            if ok.sum() >= 2:
                out[i] = np.interp(m, cols[ok], rowvals[ok])
        return pd.Series(out, index=wide.index)

    return ((col(long) - col(short)) * 100).dropna()


# ===========================================================================
# Forward rates & the market-implied short-rate path
# ===========================================================================
def forward_curve(interp, horizon, x_min, x_max=30.0, n=300):
    """No-arbitrage forward curve: the `horizon`-year rate starting at each t.
        f(t) = ((t+h)*y(t+h) - t*y(t)) / h
    Returns (t, spot(t), forward(t))."""
    t = np.linspace(x_min, max(x_min, x_max - horizon), n)
    spot = interp(t)
    fwd = ((t + horizon) * interp(t + horizon) - t * spot) / horizon
    return t, spot, fwd


def implied_short_rate_path(interp, max_year=10, step=1.0):
    """Market-implied path of the future short rate: the `step`-year rate the
    curve implies starting each year forward (what the market 'predicts').
    Returns (start_years, implied_rate, spot_today_for_reference)."""
    starts = np.arange(0, max_year, step)
    implied = np.array([
        ((t + step) * float(interp(t + step)) - t * float(interp(t))) / step
        for t in starts
    ])
    spot0 = float(interp(step))  # today's short rate reference
    return starts, implied, spot0


# ===========================================================================
# Nelson-Siegel-Svensson parametric fit
# ===========================================================================
def _nss(tau, b0, b1, b2, b3, l1, l2):
    """Nelson-Siegel-Svensson yield function."""
    tau = np.asarray(tau, dtype=float)
    tau = np.where(tau <= 0, 1e-6, tau)
    x1, x2 = tau / l1, tau / l2
    term1 = (1 - np.exp(-x1)) / x1
    term2 = term1 - np.exp(-x1)
    term3 = (1 - np.exp(-x2)) / x2 - np.exp(-x2)
    return b0 + b1 * term1 + b2 * term2 + b3 * term3


def _nss_basis(tau, l1, l2):
    """The four NSS loadings evaluated at maturities `tau` for given decays.
    Given the decays, the model is *linear* in the betas — this is the design
    matrix column set used by the stable two-stage fit."""
    tau = np.asarray(tau, dtype=float)
    tau = np.where(tau <= 0, 1e-6, tau)
    x1, x2 = tau / l1, tau / l2
    t1 = (1 - np.exp(-x1)) / x1
    t2 = t1 - np.exp(-x1)
    t3 = (1 - np.exp(-x2)) / x2 - np.exp(-x2)
    return np.column_stack([np.ones_like(tau), t1, t2, t3])


def fit_nss(curve_df):
    """Fit NSS to an observed curve. Returns a dict with parameters, the
    interpretable factors (level/slope/curvature), an evaluator, and fit RMSE.

    Uses the standard, robust two-stage estimation: grid-search the two decay
    parameters (λ1, λ2) — the only source of nonlinearity — and solve ordinary
    least squares for the betas at each grid point. This avoids the parameter
    degeneracy that makes a joint nonlinear fit run the curvature β to a bound.
    """
    x = curve_df["Maturity (Years)"].values.astype(float)
    y = curve_df["Yield (%)"].values.astype(float)
    order = np.argsort(x)
    x, y = x[order], y[order]

    l1_grid = np.linspace(0.2, 8.0, 32)
    l2_grid = np.linspace(1.0, 30.0, 32)
    best = None  # (ssr, betas, l1, l2)
    for l1 in l1_grid:
        for l2 in l2_grid:
            if l2 <= l1:
                continue  # keep the two humps distinct (λ1 short, λ2 long)
            A = _nss_basis(x, l1, l2)
            betas, *_ = np.linalg.lstsq(A, y, rcond=None)
            ssr = float(np.sum((A @ betas - y) ** 2))
            if best is None or ssr < best[0]:
                best = (ssr, betas, l1, l2)

    _, betas, l1, l2 = best
    b0, b1, b2, b3 = betas
    p = [b0, b1, b2, b3, l1, l2]
    fitted = _nss(x, *p)
    rmse = float(np.sqrt(np.mean((fitted - y) ** 2)))

    # Interpretable factors are read off the *fitted smooth curve*, not the raw
    # betas: the NSS betas are near-collinear and individually unstable, but the
    # fitted yields are well determined (tiny RMSE). These are the standard
    # market definitions of level / slope / curvature.
    ev = lambda tau: float(_nss(tau, *p))
    lo = float(x.min())
    long_level = ev(30) if x.max() >= 25 else ev(x.max())
    short_rate = ev(max(lo, 0.25))
    slope = ev(10) - ev(2)                      # 2s10s slope
    curvature = 2 * ev(5) - ev(2) - ev(10)      # 2-5-10 butterfly

    return {
        "params": dict(beta0=b0, beta1=b1, beta2=b2, beta3=b3, lam1=l1, lam2=l2),
        "level": long_level,       # long-end level (30Y fit)
        "short_rate": short_rate,  # front-end level (fit)
        "slope": slope,            # 10Y − 2Y (positive => upward sloping)
        "curvature": curvature,    # 2·5Y − 2Y − 10Y (positive => humped)
        "rmse_bps": rmse * 100,
        "eval": lambda tau: _nss(tau, *p),
    }


# ===========================================================================
# PCA of historical curve moves (empirical level / slope / curvature)
# ===========================================================================
_PC_NAMES = ["Level", "Slope", "Curvature", "PC4", "PC5"]


def pca_factors(wide, n_components=3):
    """PCA on daily curve *changes* (in bps). Returns the empirical factors that
    drive curve moves, oriented and signed for consistent interpretation.

    Returns dict: maturities, loadings (n x m), explained (n,), factor_std (bps),
    scores (DataFrame date x factor), names.
    """
    # Common maturities with continuous data.
    df = wide.dropna(axis=1, how="any")
    if df.shape[1] < 3:
        df = wide.ffill().dropna(axis=1, how="any")
    if df.shape[1] < 3 or df.shape[0] < 30:
        raise CurveDataError("Not enough overlapping history for PCA — widen the "
                             "history window.")
    maturities = np.array(sorted(df.columns))
    df = df[maturities]

    changes = df.diff().dropna() * 100.0  # daily changes in bps
    X = changes.values
    Xc = X - X.mean(axis=0)

    # SVD-based PCA
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    n = min(n_components, Vt.shape[0])
    loadings = Vt[:n].copy()
    var = (S ** 2) / (len(Xc) - 1)
    explained = var[:n] / var.sum()
    scores = U[:, :n] * S[:n]  # projection of each day's move onto each factor

    # Orient signs so the factors read conventionally:
    #  PC1 (Level): all-positive loadings (whole curve up)
    #  PC2 (Slope): long end positive (steepener)
    #  PC3 (Curvature): belly positive (hump up)
    for i in range(n):
        w = loadings[i]
        if i == 0:
            ref = np.sign(w.sum())
        elif i == 1:
            ref = np.sign(w[-1] - w[0])
        else:
            mid = len(w) // 2
            ref = np.sign(w[mid] - 0.5 * (w[0] + w[-1]))
        if ref < 0:
            loadings[i] *= -1
            scores[:, i] *= -1

    factor_std = scores.std(axis=0)
    scores_df = pd.DataFrame(
        scores, index=changes.index,
        columns=[_PC_NAMES[i] for i in range(n)])

    return {
        "maturities": maturities,
        "loadings": loadings,
        "explained": explained,
        "factor_std": factor_std,
        "scores": scores_df,
        "names": [_PC_NAMES[i] for i in range(n)],
    }


def pca_scenario_shock(pca, sigma_moves):
    """Translate factor moves (in σ) into a per-maturity yield shock (bps).
    `sigma_moves` is a list aligned with pca['names']. Returns (maturities, bps)."""
    loadings = pca["loadings"]
    stds = pca["factor_std"]
    shock = np.zeros(len(pca["maturities"]))
    for i, sig in enumerate(sigma_moves):
        if i < len(loadings):
            shock += sig * stds[i] * loadings[i]
    return pca["maturities"], shock


# ===========================================================================
# Spread mean-reversion (statistical signal on where a spread is likely to go)
# ===========================================================================
def mean_reversion(series):
    """AR(1)/Ornstein-Uhlenbeck stats for a spread series (in bps).
    Returns current, mean, std, z-score, AR(1) rho, and half-life in days."""
    s = series.dropna()
    if len(s) < 30:
        raise CurveDataError("Not enough history to estimate mean reversion.")
    cur, mean, std = float(s.iloc[-1]), float(s.mean()), float(s.std())
    z = (cur - mean) / std if std > 0 else 0.0
    x = s.shift(1).dropna()
    y = s.loc[x.index]
    rho, _ = np.polyfit(x.values, y.values, 1)
    half_life = float(-np.log(2) / np.log(rho)) if 0 < rho < 1 else np.nan
    return dict(current=cur, mean=mean, std=std, z=z, rho=float(rho),
                half_life_days=half_life)


# ===========================================================================
# Breakeven inflation (US only, nominal - real)
# ===========================================================================
def breakevens(nominal_interp, tips_latest):
    """Per-maturity breakeven = nominal(interp) - real(TIPS). Returns a df with
    Maturity, Nominal, Real, Breakeven (%)."""
    rows = []
    for _, r in tips_latest.iterrows():
        m = float(r["Maturity (Years)"])
        nom = float(nominal_interp(m))
        real = float(r["Real Yield (%)"])
        rows.append((m, nom, real, nom - real))
    return pd.DataFrame(rows, columns=["Maturity (Years)", "Nominal (%)",
                                       "Real (%)", "Breakeven (%)"])


# ===========================================================================
# Scenario shocks (classic parametric deformations)
# ===========================================================================
def shock_profiles(maturities, magnitude, pivot=5.0, butterfly_center=7.0):
    """Return {scenario: shocked_yield_delta_array(%)} over `maturities`."""
    t = np.asarray(maturities, dtype=float)
    return {
        f"Parallel +{magnitude*100:.0f}bp": np.full_like(t, magnitude),
        f"Parallel -{magnitude*100:.0f}bp": np.full_like(t, -magnitude),
        "Steepener": magnitude * (t - pivot) / 25.0,
        "Flattener": -magnitude * (t - pivot) / 25.0,
        "Butterfly": magnitude * (1 - 2 * np.exp(-0.5 * ((t - butterfly_center) / 5.0) ** 2)),
    }
