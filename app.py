"""
Family Office OS — Alternative Assets Monitor
Entry point. Lógica separada en módulos bajo utils/ y tabs/.
"""
import streamlit as st
import pandas as pd
from datetime import timedelta
import traceback

# ── Utils ─────────────────────────────────────────────────────────────────────
from utils.drive       import load_excel_from_drive
from utils.calculations import (get_fx_map_institutional, convert_amount,
                                 load_data, compute_portfolio,
                                 _calc_quarterly_evolutions, _calc_pooled_irr)
from utils.excel_export import df_to_excel_bytes, excel_download_btn
from utils.styles       import inject_css
from utils.sidebar      import render_sidebar

# ── Tabs ──────────────────────────────────────────────────────────────────────
from tabs import (status, vintage, estrategia, portfolio,
                  irr_tvpi_dpi, rentabilidad, cashflows,
                  commitment_pace, point_in_time, simulacion)

# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Family Office OS",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Family Office OS — Alternative Assets Monitor"}
)

import os

inject_css()

# ─────────────────────────────────────────────────────────────────────────────
try:
    # Cargar datos
    df_char, df_flows_raw, df_coinv = load_data()

    # Sidebar → retorna todo lo necesario para el cuerpo principal
    ctx = render_sidebar(df_char, df_flows_raw, df_coinv)
    # ctx contiene: report_curr, as_of_date_dt, fx_map, fx_today,
    #               df_char_filt, df_final, all_flows_rep_global,
    #               curr_sym, g_irr, s_stats, v_stats, t_nav, t_comm,
    #               t_paid, t_dist, calc_quarterly_evolutions, calc_pooled_irr,
    #               calc_wav_duration, _dur_total

    # ── Header ────────────────────────────────────────────────────────────────
    st.title("🏛️ Alternative Assets Monitor")
    st.markdown("---")

    # ── Tab navigation ────────────────────────────────────────────────────────
    TAB_NAMES = [
        "📊 Status", "📅 Vintage", "🎯 Estrategia", "💼 Portfolio",
        "📉 IRR", "📈 TVPI", "💰 DPI", "🔄 Rent.",
        "💸 Cash Flows", "📆 Commitment Pace",
        "📍 Point in Time", "🔮 Simulación"
    ]

    if 'active_tab' not in st.session_state:
        st.session_state['active_tab'] = TAB_NAMES[0]

    st.markdown('<div class="tab-radio">', unsafe_allow_html=True)
    active_tab = st.radio(
        "navegación", TAB_NAMES,
        index=TAB_NAMES.index(st.session_state['active_tab']),
        horizontal=True,
        label_visibility="collapsed",
        key="tab_radio"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    st.session_state['active_tab'] = active_tab

    def tab_active(name):
        return active_tab == name

    # ── Render tabs ───────────────────────────────────────────────────────────
    if tab_active("📊 Status"):          status.render(ctx)
    elif tab_active("📅 Vintage"):       vintage.render(ctx)
    elif tab_active("🎯 Estrategia"):    estrategia.render(ctx)
    elif tab_active("💼 Portfolio"):     portfolio.render(ctx)
    elif tab_active("📉 IRR"):           irr_tvpi_dpi.render(ctx, "IRR")
    elif tab_active("📈 TVPI"):          irr_tvpi_dpi.render(ctx, "TVPI")
    elif tab_active("💰 DPI"):           irr_tvpi_dpi.render(ctx, "DPI")
    elif tab_active("🔄 Rent."):         rentabilidad.render(ctx)
    elif tab_active("💸 Cash Flows"):    cashflows.render(ctx)
    elif tab_active("📆 Commitment Pace"): commitment_pace.render(ctx)
    elif tab_active("📍 Point in Time"): point_in_time.render(ctx)
    elif tab_active("🔮 Simulación"):    simulacion.render(ctx)

except Exception as e:
    st.error(f"Error detectado: {e}")
    st.code(traceback.format_exc(), language="python")
