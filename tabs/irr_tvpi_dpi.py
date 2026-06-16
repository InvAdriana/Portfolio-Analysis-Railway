import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pyxirr import xirr
from utils.excel_export import excel_download_btn
from utils.calculations import convert_amount

# ── 📉 IRR / TVPI / DPI ──

def render(ctx, mode="IRR"):
    # Unpack context
    report_curr = ctx.get("report_curr")
    as_of_date_dt = ctx.get("as_of_date_dt")
    fx_map = ctx.get("fx_map")
    fx_today = ctx.get("fx_today")
    curr_sym = ctx.get("curr_sym")
    df_char = ctx.get("df_char")
    df_char_filt = ctx.get("df_char_filt")
    df_final = ctx.get("df_final")
    df_coinv = ctx.get("df_coinv")
    df_flows_raw = ctx.get("df_flows_raw")
    all_flows_rep_global = ctx.get("all_flows_rep_global")
    g_irr = ctx.get("g_irr")
    s_stats = ctx.get("s_stats")
    v_stats = ctx.get("v_stats")
    t_nav = ctx.get("t_nav")
    t_comm = ctx.get("t_comm")
    t_paid = ctx.get("t_paid")
    t_dist = ctx.get("t_dist")
    calc_quarterly_evolutions = ctx.get("calc_quarterly_evolutions")
    calc_pooled_irr = ctx.get("calc_pooled_irr")
    calc_wav_duration = ctx.get("calc_wav_duration")
    _dur_total = ctx.get("_dur_total")
    money_cols = ctx.get("money_cols")
    as_of_date = ctx.get("as_of_date")

    sel4 = st.radio("💱 Moneda de cálculo", CURR_OPTIONS, horizontal=True, key="curr_irr",
                    index=DEFAULT_IDX.get(report_curr, 0))
    cc4  = CURR_KEYS[sel4]
    st.caption(f"ℹ️ {curr_caption(cc4)}")
    irr_ev4, _, _, _ = calc_quarterly_evolutions(cc4)
    df_irr4 = pd.DataFrame(irr_ev4)
    q_cols_irr4 = [c for c in df_irr4.columns if c != 'Fund']
    df_irr4 = df_irr4[['Fund'] + q_cols_irr4[::-1]]
    meta = df_final[['Fund','Strategy','Vintage']]
    df_irr4 = meta.merge(df_irr4, on='Fund', how='right')
    q_cols4 = [c for c in df_irr4.columns if c not in ['Fund','Strategy','Vintage']]
    fmt_irr = {c: '{:.2f}%' for c in q_cols4}
    for grupo_nombre, estrategias in GRUPOS_EV.items():
        df_g = df_irr4[df_irr4['Strategy'].isin(estrategias)].copy()
        if df_g.empty: continue
        df_g = df_g.sort_values(['Vintage','Fund'])
        df_g.index = range(1, len(df_g) + 1)
        st.markdown(f"### {grupo_nombre}")
        st.dataframe(df_g.style.format(fmt_irr, na_rep="-"),
                     use_container_width=True, height=min(50 + len(df_g)*36, 600))
        excel_download_btn(df_g.reset_index(), f"IRR {grupo_nombre.split()[-1]}",
                           f"irr_{grupo_nombre.split()[-1].lower()}_{cc4}.xlsx",
                           "IRR", f"IRR {grupo_nombre} — {cc4}",
                           report_curr, key=f"dl_irr_{grupo_nombre}")
        st.markdown("---")

    if tab_active("📈 TVPI"):
    sel5 = st.radio("💱 Moneda de cálculo", CURR_OPTIONS, horizontal=True, key="curr_tvpi",
                    index=DEFAULT_IDX.get(report_curr, 0))
    cc5  = CURR_KEYS[sel5]
    st.caption(f"ℹ️ {curr_caption(cc5)}")
    irr_ev5, tvpi_ev5, _, _ = calc_quarterly_evolutions(cc5)
    df_irr5  = pd.DataFrame(irr_ev5).set_index('Fund')
    df_irr5  = df_irr5[df_irr5.columns[::-1]]
    df_tvpi5 = pd.DataFrame(tvpi_ev5)
    q_cols_tvpi5 = [c for c in df_tvpi5.columns if c != 'Fund']
    df_tvpi5 = df_tvpi5[['Fund'] + q_cols_tvpi5[::-1]]
    meta = df_final[['Fund','Strategy','Vintage']]
    df_tvpi5 = meta.merge(df_tvpi5, on='Fund', how='right')
    q_cols5 = [c for c in df_tvpi5.columns if c not in ['Fund','Strategy','Vintage']]
    fmt_tvpi = {c: '{:.2f}x' for c in q_cols5}
    for grupo_nombre, estrategias in GRUPOS_EV.items():
        df_g = df_tvpi5[df_tvpi5['Strategy'].isin(estrategias)].copy()
        if df_g.empty: continue
        df_g = df_g.sort_values(['Vintage','Fund'])
        df_g.index = range(1, len(df_g) + 1)
        st.markdown(f"### {grupo_nombre}")
        st.dataframe(df_g.style.format(fmt_tvpi, na_rep="-"),
                     use_container_width=True, height=min(50 + len(df_g)*36, 600))
        excel_download_btn(df_g.reset_index(), f"TVPI {grupo_nombre.split()[-1]}",
                           f"tvpi_{grupo_nombre.split()[-1].lower()}_{cc5}.xlsx",
                           "TVPI", f"TVPI {grupo_nombre} — {cc5}",
                           report_curr, key=f"dl_tvpi_{grupo_nombre}")
        st.markdown("---")

    if tab_active("💰 DPI"):
    sel6 = st.radio("💱 Moneda de cálculo", CURR_OPTIONS, horizontal=True, key="curr_dpi",
                    index=DEFAULT_IDX.get(report_curr, 0))
    cc6  = CURR_KEYS[sel6]
    st.caption(f"ℹ️ {curr_caption(cc6)}")
    _, _, dpi_ev6, _ = calc_quarterly_evolutions(cc6)
    df_dpi6 = pd.DataFrame(dpi_ev6)
    q_cols_dpi6 = [c for c in df_dpi6.columns if c != 'Fund']
    df_dpi6 = df_dpi6[['Fund'] + q_cols_dpi6[::-1]]
    meta = df_final[['Fund','Strategy','Vintage']]
    df_dpi6 = meta.merge(df_dpi6, on='Fund', how='right')
    q_cols6 = [c for c in df_dpi6.columns if c not in ['Fund','Strategy','Vintage']]
    fmt_dpi = {c: '{:.2f}x' for c in q_cols6}
    for grupo_nombre, estrategias in GRUPOS_EV.items():
        df_g = df_dpi6[df_dpi6['Strategy'].isin(estrategias)].copy()
        if df_g.empty: continue
        df_g = df_g.sort_values(['Vintage','Fund'])
        df_g.index = range(1, len(df_g) + 1)
        st.markdown(f"### {grupo_nombre}")
        st.dataframe(df_g.style.format(fmt_dpi, na_rep="-"),
                     use_container_width=True, height=min(50 + len(df_g)*36, 600))
        excel_download_btn(df_g.reset_index(), f"DPI {grupo_nombre.split()[-1]}",
                           f"dpi_{grupo_nombre.split()[-1].lower()}_{cc6}.xlsx",
                           "DPI", f"DPI {grupo_nombre} — {cc6}",
                           report_curr, key=f"dl_dpi_{grupo_nombre}")
        st.markdown("---")

