"""
All user-facing explanatory copy for the terminal, kept out of app.py.

Scannable, English. Two pieces:
  GUIDE         - the "Guide" tab body (markdown).
  HOW_TO_READ   - short per-chart blurbs shown in "How to read this" expanders.
"""

# ===========================================================================
# Guide tab
# ===========================================================================
GUIDE = """
### What this is
A workbench to **read and forecast the term structure of interest rates** — the
yields a government pays to borrow at every maturity, from 1 month to 30 years.
The curve is the single most information-dense chart in finance: it prices the
market's expectations for **policy rates, growth, inflation and recession** all
at once. This tool extracts them.

*Educational use only — not investment advice.*

---

### The yield curve in 20 seconds
- **x-axis** = maturity (years) · **y-axis** = yield (%).
- **Normal (upward):** long > short → base case for orderly growth.
- **Inverted (downward):** short > long → has **preceded every US recession** in 60 years.
- **Flat:** transition between the two.

---

### The four prediction engines
Each looks at the same curve from a different angle; together they turn a hunch
into a structured, measurable view.

| Engine | Answers | Strength | Blind spot |
|---|---|---|---|
| **① Forwards** | What is the market *already* pricing? | Objective, arbitrage-free baseline | It's the consensus — often wrong in the same direction |
| **② PCA** | *How* can the curve move? | Reduces every move to 3 shapes (Level/Slope/Curvature) | Describes, doesn't predict direction |
| **③ NSS fit** | What's the clean *shape*? | Smooths, extrapolates >30Y, gives 3 readable numbers | A static snapshot, not dynamics |
| **④ Mean reversion** | Is a spread stretched? | The one real *directional* signal | Only for spreads; no timing |

**How they combine — the workflow:**
1. **Diagnose** the shape → *Curve* + *History*
2. **Read the market's forecast** → *Forwards* (your baseline)
3. **Express your own view** as a shock to Level/Slope/Curvature → *Factors (PCA)*
4. **Check the statistical pull** on the spread you care about → *Mean Reversion*
5. **Stress-test** the impact → *Scenarios*

①gives the consensus, ②the vocabulary, ③the shape, ④the signal. No single one is enough.

---

### Tab-by-tab cheat-sheet
| Tab | Shows | Read it as |
|---|---|---|
| 📈 **Curve** | Today's curve + NSS fit + curve N days ago | Slope = regime; gap vs past = what shifted |
| 🌐 **History** | 3D surface, date explorer, 2s10s + recessions | Eras of the curve; inversions before recessions |
| 🔮 **Forwards** | Spot vs forward, implied rate path | The market's own forecast for policy rates |
| 🧬 **Factors (PCA)** | Level/Slope/Curvature + σ-scenario builder | Which 3 moves drive the curve, and how much |
| 📉 **Mean Reversion** | Spread vs its mean ±1σ/±2σ, z-score, half-life | Rich/cheap vs history + the pull back |
| 💰 **Inflation** (US) | Nominal / Real / Breakeven | The inflation the market is pricing |
| ⚡ **Scenarios** | Parallel / steepener / flattener / butterfly | Manual stress test of a curve view |
| ⚖️ **Rates Risk** | Duration / DV01 / convexity, key-rate DV01, scenario P&L | The €/$ risk of a bond to curve moves |

---

### Data & honesty
- **US** curve from **FRED** (Treasury nominal + TIPS + NBER recessions); **Euro Area AAA** from the **ECB Data Portal**; **Japan** (JGB) from the **Ministry of Finance** — the last two are nominal-only.
- Nothing is fabricated: a missing value shows "—" or a named error.
- Forwards and mean reversion are **expectations / tendencies**, never guarantees.
"""


# ===========================================================================
# Per-chart "How to read this" blurbs
# ===========================================================================
HOW_TO_READ = {
    "curve": """
**Shows:** today's curve (green), its **NSS model fit** (cyan = the smooth
version), and the curve **N days ago** (dashed).
**Read it as:** the *slope* tells you the regime (up = normal, down = inverted).
The *gap* to the dashed curve tells you what moved — whole curve up/down = a
level shift; only the long end = a steepener; only the front = changed rate
expectations.
**Params:** *Compare vs N days ago* moves the dashed line · *Interpolation*
changes smoothness.
""",
    "interpolation": """
**Shows:** the curve as a continuous function (green) through the observed
points (amber), plus any **custom maturities** you priced (purple).
**Why:** providers only publish fixed maturities; interpolation lets you price
any point (e.g. 4.5Y) and any spread.
**Read it as:** *linear* connects points with straight lines and never invents a
value between them; *cubic* is smoother but can overshoot. Use linear for
numbers, cubic for looks.
""",
    "surface": """
**Shows:** the whole curve through time — x = maturity, y = date, height/colour =
yield.
**Read it as:** whole *eras* at a glance — the floor of near-zero rates
(2020–21), the steep climb (2022–23), the recent inversion. Drag to rotate.
**Params:** *History (years)* sets how far back it goes.
""",
    "explorer": """
**Shows:** any single day's curve, optionally vs a second date.
**Read it as:** the y-axis is **locked across all history**, so level shifts are
visually honest — a curve that looks low really *is* low versus the past.
""",
    "spread": """
**Shows:** the 2s10s spread over time, with the **zero line** (inversion
threshold) and grey **recession bands** (US only).
**Read it as:** dips below zero = inversions. Note how they cluster *before* the
grey bands — that's the recession-warning track record.
""",
    "forward": """
**Shows:** today's **spot** curve (green) vs the **forward** curve (purple) — the
future rate the market implies at each starting point.
**Read it as:** forward *below* spot = the market prices rates falling; *above* =
rising. This is the market's own forecast, extracted by no-arbitrage.
**Params:** *Forward horizon* sets the window (e.g. 5Y forward).
""",
    "implied_path": """
**Shows:** the 1Y rate the curve implies starting each year forward — the
**market-implied path of the policy rate**, vs today's rate (dashed line).
**Read it as:** bars below the line = priced *cuts*; above = *hikes*. It's a
forecast priced into bonds, **not** a guarantee — realized rates routinely differ.
""",
    "pca": """
**Shows (left):** how much of daily curve moves each factor explains.
**Shows (right):** the **loadings** — the shape of each move across maturities.
**Read the loadings:** *flat & same-sign* = **Level** (whole curve up/down);
*negative-to-positive* = **Slope** (short vs long move oppositely); *ends vs
middle* = **Curvature** (belly vs wings). Their height shows *which* maturities
each factor moves most.
""",
    "pca_scenario": """
**Shows:** today's curve reshaped by your factor shocks.
**Read it as:** move each factor in units of its historical daily **σ**; the
curve deforms the way that factor *empirically* moves it. This is the data-driven
way to build a scenario — a forecast of the whole curve becomes a view on just
three numbers.
""",
    "mean_reversion": """
**Shows:** the chosen spread vs its **mean** (amber) and **±1σ/±2σ** bands, with
the current point marked.
**Read it as:** a high **z-score** = rich vs history (tends to fall back); low =
cheap (tends to rise). **Half-life** is how long it typically takes to close half
the gap. It's a statistical tendency, **not** a timing signal.
""",
    "inflation": """
**Shows:** the **Nominal** curve, the **Real** curve (TIPS), and the
**Breakeven** (Nominal − Real) vs the 2% target.
**Read it as:** breakeven = the average annual inflation the market prices for
each horizon. Above 2% = the market expects the central bank to overshoot; below
= undershoot.
""",
    "breakeven_history": """
**Shows:** the 10Y breakeven inflation over time vs the 2% target.
**Read it as:** the market's evolving inflation expectation — rising = inflation
fears building; falling = fading.
""",
    "scenarios": """
**Shows:** today's curve plus four classic **deformations**; the second chart
shows the shock (bps) each applies per maturity.
**Read it as:** *Parallel* = broad repricing · *Steepener* = long end sells off
(growth/inflation) · *Flattener* = front end sells off (hikes) · *Butterfly* =
belly moves against the wings.
**Params:** *magnitude* = size · *pivot* = where steepener/flattener rotates ·
*butterfly center* = where the belly sits.
""",
    "price_yield": """
**Shows:** the bond's value as the whole curve shifts in parallel (green,
curved) vs the straight-line **duration estimate** (dashed).
**Read it as:** the gap between the two *is* **convexity**. The real price line
bows above the straight one — so duration overstates losses and understates
gains. Bigger gap = more convexity.
""",
    "key_rate": """
**Shows:** the DV01 (P&L per 1bp) coming from a bump at *each* maturity pillar —
the bars sum to the total DV01.
**Read it as:** *where* on the curve the bond's rate risk lives. A plain bond
concentrates almost all of it at its maturity; the shape matters once you hold
several bonds. This is what makes a position sensitive to twists, not just
parallel moves.
""",
    "scenario_pnl": """
**Shows:** the bond's exact reprice P&L under each curve shock (green = gain,
red = loss).
**Read it as:** the euro/dollar impact of each move — parallel shifts hit
hardest for a single bond, twists (steepener/flattener/butterfly) much less. The
note below shows how duration + convexity reproduce the parallel move almost
exactly.
**Params:** shock *magnitude / pivot / butterfly center* (sidebar).
""",
}
