"""
Dark finance-terminal theme (shared across the finance tool suite).

Single source of visual truth: the color palette, the Streamlit CSS injection,
and a Plotly layout factory, so every chart in the app looks like it came from
the same system. Bloomberg-terminal styling: near-black background,
high-contrast bright text, amber as the primary UI accent, monospace
everywhere. Saturated green/red/blue are reserved for *data semantics*.
"""

import plotly.graph_objects as go

# ---- Core palette ----------------------------------------------------------
BG = "#08090c"          # app background (near black)
PANEL = "#101319"       # card / chart background
PANEL_2 = "#181d26"     # slightly raised surface
BORDER = "#2c3542"      # hairline borders
GRID = "#1b2029"        # chart gridlines
TEXT = "#f2f5fa"        # primary text (bright, high contrast)
MUTED = "#b3bccb"       # secondary text (brighter than before, still legible)

ACCENT = "#ff9e1b"      # Bloomberg amber — primary UI accent (title, tabs, buttons)
GREEN = "#12e29a"       # nominal curve / positive
BLUE = "#3d9bff"        # real (TIPS) / secondary series
AMBER = "#ff9e1b"       # breakeven / caution
RED = "#ff4d5e"         # inversion / losses / errors
PURPLE = "#c792ea"      # forward curve
CYAN = "#4fd6e6"        # NSS model fit

# Categorical palette for per-series lines (distinct, terminal-bright).
ASSET_COLORS = [
    "#12e29a", "#3d9bff", "#ff9e1b", "#ff4d5e", "#c792ea",
    "#4fd6e6", "#f78c6c", "#a3be8c", "#e5c07b", "#ff7eb6",
    "#82aaff", "#7fdbca", "#d19a66", "#98c379",
]

# Blue -> teal -> amber sequential scale for the historical curve surface
# (color encodes time: old = deep blue, recent = amber).
TIME_SCALE = [
    [0.0, "#1b3a5b"],
    [0.35, "#2f6f8f"],
    [0.6, "#2bb6a0"],
    [0.8, "#e5c07b"],
    [1.0, "#ff9e1b"],
]

# Red -> neutral -> green diverging scale for signed change / z-score heatmaps.
DIVERGING = [[0.0, RED], [0.5, "#243044"], [1.0, GREEN]]

FONT = "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, monospace"


def inject_css():
    """Return the app-wide CSS block (dark terminal styling + metric cards)."""
    return f"""
    <style>
    .stApp {{ background: {BG}; }}
    section[data-testid="stSidebar"] {{
        background: {PANEL};
        border-right: 1px solid {BORDER};
    }}
    section[data-testid="stSidebar"] * {{ color: {TEXT}; }}

    h1, h2, h3, h4 {{
        color: {TEXT};
        font-family: {FONT};
        letter-spacing: 0.02em;
    }}
    .app-title {{
        font-family: {FONT};
        font-size: 1.9rem;
        font-weight: 700;
        color: {TEXT};
        margin-bottom: 0.1rem;
    }}
    .app-title .accent {{ color: {ACCENT}; }}
    .app-sub {{ color: {MUTED}; font-family: {FONT}; font-size: 0.85rem; }}

    /* Sidebar widget labels — bright and bold, not muted gray */
    section[data-testid="stSidebar"] label {{
        color: {TEXT} !important; font-weight: 600; font-family: {FONT};
    }}
    /* Captions (the config explanations) — legible, not washed out */
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {{
        color: {MUTED} !important; font-family: {FONT};
    }}

    /* Text inputs: bright typed text, dim placeholder, amber focus border */
    .stTextInput input, .stDateInput input, .stNumberInput input {{
        color: {TEXT} !important; font-weight: 600; font-family: {FONT};
        -webkit-text-fill-color: {TEXT};
    }}
    .stTextInput input::placeholder {{ color: {MUTED}; opacity: 0.55; font-weight: 400; }}
    .stTextInput div[data-baseweb="input"]:focus-within,
    .stTextInput div[data-baseweb="base-input"]:focus-within {{
        border-color: {ACCENT} !important;
        box-shadow: 0 0 0 1px {ACCENT};
    }}
    [data-testid="InputInstructions"] {{
        position: static !important;
        color: {MUTED} !important; font-family: {FONT};
        font-size: 0.7rem; margin-top: 3px; opacity: 0.8;
    }}

    /* Metric cards */
    .kpi-row {{ display: flex; gap: 14px; flex-wrap: wrap; margin: 6px 0 4px 0; }}
    .kpi {{
        flex: 1 1 150px;
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 14px 16px;
        position: relative;
        overflow: hidden;
    }}
    .kpi::before {{
        content: "";
        position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
        background: var(--accent, {GREEN});
    }}
    .kpi .label {{
        color: {MUTED}; font-family: {FONT};
        font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em;
    }}
    .kpi .value {{
        color: {TEXT}; font-family: {FONT};
        font-size: 1.5rem; font-weight: 700; margin-top: 4px;
    }}
    .kpi .sub {{ color: {MUTED}; font-family: {FONT}; font-size: 0.72rem; margin-top: 2px; }}

    .section-tag {{
        color: {ACCENT}; font-family: {FONT}; font-size: 0.74rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: -6px;
    }}

    /* Maturity / factor chip strip */
    .asset-strip {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 2px 0 6px 0; }}
    .chip {{
        display: flex; align-items: center; gap: 8px;
        background: {PANEL}; border: 1px solid {BORDER};
        border-radius: 8px; padding: 7px 11px; font-family: {FONT};
    }}
    .chip .dot {{ width: 9px; height: 9px; border-radius: 50%; flex: none; }}
    .chip .tkr {{ color: {TEXT}; font-weight: 700; font-size: 0.82rem; }}
    .chip .desc {{ color: {MUTED}; font-size: 0.75rem; }}

    /* Signal callout box (bright, bordered) */
    .signal {{
        font-family: {FONT}; font-size: 0.86rem; line-height: 1.5;
        border-radius: 10px; padding: 12px 14px; margin: 4px 0 8px 0;
        border: 1px solid {BORDER}; background: {PANEL};
    }}
    .signal b {{ color: {TEXT}; }}
    .signal .lead {{ font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.08em; font-size: 0.72rem; }}

    /* Bright red validation alert */
    .ticker-alert {{
        color: {RED}; font-family: {FONT}; font-weight: 700; font-size: 0.8rem;
        background: rgba(255,77,94,0.10); border: 1px solid {RED};
        border-radius: 8px; padding: 8px 10px; margin-top: 6px;
    }}

    /* Tabs */
    button[data-baseweb="tab"] {{ font-family: {FONT}; color: {MUTED}; font-weight: 600; }}
    button[data-baseweb="tab"][aria-selected="true"] {{ color: {ACCENT}; }}
    div[data-baseweb="tab-highlight"] {{ background: {ACCENT}; }}

    /* Dataframe tweaks */
    .stDataFrame {{ border: 1px solid {BORDER}; border-radius: 8px; }}

    /* Buttons */
    .stButton>button, .stFormSubmitButton>button {{
        background: {ACCENT}; color: #1a1100; border: none;
        font-family: {FONT}; font-weight: 700; border-radius: 8px;
    }}
    .stButton>button:hover, .stFormSubmitButton>button:hover {{
        background: #ffb347; color: #1a1100;
    }}
    </style>
    """


def kpi_card(label, value, sub="", accent=GREEN):
    """Render one metric card as an HTML string."""
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (
        f'<div class="kpi" style="--accent:{accent}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>{sub_html}</div>'
    )


def signal_box(lead, body, accent=ACCENT):
    """Render an interpretive 'what this means' callout as an HTML string."""
    return (
        f'<div class="signal" style="border-left:3px solid {accent}">'
        f'<div class="lead" style="color:{accent}">{lead}</div>{body}</div>'
    )


def base_layout(fig: go.Figure, height=460, title=None, legend=True):
    """Apply the shared dark layout to a Plotly figure and return it."""
    # Always pass an explicit title dict. Passing title=None to this Plotly
    # version leaves title.text undefined, which renders as the literal string
    # "undefined" in the top-left of the chart.
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(family=FONT, color=TEXT, size=12),
        height=height,
        margin=dict(l=60, r=30, t=50 if title else 20, b=50),
        title=dict(text=title or "", font=dict(size=15, color=TEXT)),
        colorway=ASSET_COLORS,
        hoverlabel=dict(bgcolor=PANEL_2, bordercolor=BORDER, font=dict(family=FONT)),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color=MUTED),
            orientation="v",
        ) if legend else dict(),
        showlegend=legend,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=BORDER, linecolor=BORDER,
                     tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=BORDER, linecolor=BORDER,
                     tickfont=dict(color=MUTED))
    return fig
