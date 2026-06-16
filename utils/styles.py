import streamlit as st

def inject_css():
    """Inject all global CSS styles."""
    # ── Ocultar branding de Streamlit ─────────────────────────────────────────
    st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    .stDeployButton {display: none !important;}
    </style>
    """, unsafe_allow_html=True)

    # ── Sidebar dark theme + tab radio ────────────────────────────────────────
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

/* ── Sidebar base ── */
[data-testid="stSidebar"] {
    background-color: #0d1929 !important;
    border-right: 1px solid #1a2e45 !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
}

/* ── Ocultar labels nativos de Streamlit dentro del sidebar ── */
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stMultiSelect label,
[data-testid="stSidebar"] .stCheckbox label span,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #3a6080 !important;
    font-size: 13px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    font-weight: 600 !important;
}

/* ── Selectbox y multiselect dentro del sidebar ── */
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stMultiSelect > div > div {
    background-color: #0a1622 !important;
    border: 1px solid #1a3350 !important;
    border-radius: 5px !important;
    color: #8ab0cc !important;
    font-size: 14px !important;
}

/* Tags del multiselect (las pastillas) */
[data-testid="stSidebar"] .stMultiSelect span[data-baseweb="tag"] {
    background-color: #0e2a45 !important;
    border: 1px solid #1a4a70 !important;
    color: #5baee8 !important;
    font-size: 13px !important;
    border-radius: 3px !important;
}

/* ── Checkbox ── */
[data-testid="stSidebar"] .stCheckbox > label {
    color: #4a6d8c !important;
    font-size: 14px !important;
}

/* ── Botones en sidebar ── */
[data-testid="stSidebar"] .stButton > button {
    background-color: #1a5fd4 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 5px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    width: 100% !important;
    padding: 8px 0 !important;
    margin-top: 4px !important;
    transition: background 0.15s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #1450b0 !important;
}

/* ── Info box (tasas BCE) ── */
[data-testid="stSidebar"] .stAlert {
    background-color: #0a1622 !important;
    border: 1px solid #1a3350 !important;
    border-radius: 5px !important;
    color: #5baee8 !important;
    font-size: 13px !important;
}

/* ── Separador ── */
[data-testid="stSidebar"] hr {
    border-color: #1a2e45 !important;
    margin: 8px 0 !important;
}

/* ── Scrollbar del sidebar ── */
[data-testid="stSidebar"] ::-webkit-scrollbar       { width: 4px; }
[data-testid="stSidebar"] ::-webkit-scrollbar-track { background: #0a1118; }
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb { background: #1a3350; border-radius: 2px; }

/* ── Bloque de header del sidebar (logo) ── */
.sb-logo {
    padding: 16px 16px 14px;
    border-bottom: 1px solid #1a2e45;
    margin-bottom: 4px;
    display: flex; align-items: center; gap: 10px;
}
.sb-logo-mark {
    width: 32px; height: 32px;
    background: #1a5fd4;
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; font-weight: 700; color: #fff;
    flex-shrink: 0;
}
.sb-logo-name  { font-size: 15px; font-weight: 600; color: #d4e8f8; letter-spacing: -0.2px; }
.sb-logo-sub   { font-size: 10px; color: #2a4a6a; letter-spacing: 0.1em; text-transform: uppercase; }

/* ── Sección de filtros ── */
.sb-section-label {
    padding: 10px 16px 4px;
    font-size: 11px; font-weight: 700;
    color: #2a4560;
    text-transform: uppercase; letter-spacing: 0.12em;
    border-top: 1px solid #1a2e45;
    margin-top: 6px;
}

/* ── Fila de configuración (moneda / fecha) ── */
.sb-config-label {
    font-size: 11px; font-weight: 600;
    color: #2a4560;
    text-transform: uppercase; letter-spacing: 0.1em;
    margin-bottom: 2px; padding: 0 2px;
}

/* ── Tasas BCE pill ── */
.sb-rates {
    background: #0a1622;
    border: 1px solid #1a3350;
    border-radius: 5px;
    padding: 10px 14px;
    margin: 4px 0 8px;
    font-size: 13px;
}
.sb-rates-title {
    font-size: 11px; font-weight: 700;
    color: #2a4560; letter-spacing: 0.1em;
    text-transform: uppercase; margin-bottom: 6px;
}
.sb-rate-row { display: flex; justify-content: space-between; margin-bottom: 3px; }
.sb-rate-key { color: #3a6080; }
.sb-rate-val { color: #5baee8; font-weight: 600; font-family: monospace; }

/* ── Expander de filtros (CobaltLP style) ── */
[data-testid="stSidebar"] .streamlit-expanderHeader {
    background-color: #0c1e30 !important;
    border: none !important;
    border-bottom: 1px solid #1a2e45 !important;
    border-radius: 0 !important;
    color: #ffffff !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    padding: 10px 16px !important;
    letter-spacing: 0.02em !important;
}
[data-testid="stSidebar"] .streamlit-expanderHeader:hover {
    background-color: #0e2235 !important;
    color: #ffffff !important;
}
[data-testid="stSidebar"] .streamlit-expanderHeader svg {
    color: #5baee8 !important;
}
[data-testid="stSidebar"] .streamlit-expanderContent {
    background-color: #091520 !important;
    border: none !important;
    border-bottom: 1px solid #1a2e45 !important;
    border-radius: 0 !important;
    padding: 12px 14px !important;
}

/* Forzar blanco en TODOS los selectores posibles del expander */
[data-testid="stSidebar"] details > summary,
[data-testid="stSidebar"] details > summary p,
[data-testid="stSidebar"] details > summary span,
[data-testid="stSidebar"] details > summary div,
[data-testid="stSidebar"] details summary *,
[data-testid="stSidebar"] [data-testid="stExpander"] summary,
[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
[data-testid="stSidebar"] [data-testid="stExpander"] summary span {
    color: #ffffff !important;
    font-size: 14px !important;
    font-weight: 500 !important;
}
[data-testid="stSidebar"] details > summary:hover,
[data-testid="stSidebar"] details > summary:hover * {
    color: #ffffff !important;
    background-color: #0e2235 !important;
}

/* ── Botón descarga Excel compacto ── */
.stDownloadButton > button {
    background-color: transparent !important;
    border: 1px solid #d0d8e8 !important;
    border-radius: 5px !important;
    color: #5a7fa0 !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    padding: 3px 10px !important;
    height: 28px !important;
    line-height: 1 !important;
    transition: all 0.15s !important;
}
.stDownloadButton > button:hover {
    background-color: #f0f4fa !important;
    border-color: #1a5fd4 !important;
    color: #1a5fd4 !important;
}

/* ── Botón Clear All del sidebar (no tocar con el estilo de arriba) ── */
.sb-clear-btn {
    margin: 10px 16px 6px;
}
</style>
""", unsafe_allow_html=True)

    # ── Tab radio navigation ──────────────────────────────────────────────────
    st.markdown("""
    <style>
    div.tab-radio > div[role="radiogroup"] {
        display: flex; flex-wrap: wrap; gap: 2px;
        border-bottom: 2px solid #e0e6f0;
        padding-bottom: 0; margin-bottom: 16px;
    }
    div.tab-radio > div[role="radiogroup"] > label {
        padding: 8px 14px !important;
        border-radius: 6px 6px 0 0 !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        color: #5a7fa0 !important;
        border: 1px solid transparent !important;
        border-bottom: none !important;
        cursor: pointer;
        margin-bottom: -2px !important;
        background: transparent !important;
        transition: all 0.15s;
    }
    div.tab-radio > div[role="radiogroup"] > label:hover {
        color: #002060 !important;
        background: #f0f4fa !important;
    }
    div.tab-radio > div[role="radiogroup"] > label:has(input:checked) {
        color: #1a5fd4 !important;
        border-color: #e0e6f0 !important;
        border-bottom-color: white !important;
        background: white !important;
        font-weight: 600 !important;
    }
    div.tab-radio > div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)
