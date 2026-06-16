import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pyxirr import xirr
from utils.excel_export import excel_download_btn
from utils.calculations import convert_amount

# ── 🔄 Rent. ──

def render(ctx):
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

    sel7 = st.radio("💱 Moneda de cálculo", CURR_OPTIONS, horizontal=True, key="curr_rent",
                    index=DEFAULT_IDX.get(report_curr, 0))
    cc7  = CURR_KEYS[sel7]
    st.caption(f"ℹ️ {curr_caption(cc7)}")
    _, _, _, ret_ev7 = calc_quarterly_evolutions(cc7)
    df_ret7 = pd.DataFrame(ret_ev7)
    q_cols_ret7 = [c for c in df_ret7.columns if c != 'Fund']
    df_ret7 = df_ret7[['Fund'] + q_cols_ret7[::-1]]
    meta = df_final[['Fund','Strategy','Vintage']]
    df_ret7 = meta.merge(df_ret7, on='Fund', how='right')
    q_cols7 = [c for c in df_ret7.columns if c not in ['Fund','Strategy','Vintage']]
    fmt_ret = {c: '{:.2f}%' for c in q_cols7}
    for grupo_nombre, estrategias in GRUPOS_EV.items():
        df_g = df_ret7[df_ret7['Strategy'].isin(estrategias)].copy()
        if df_g.empty: continue
        df_g = df_g.sort_values(['Vintage','Fund'])
        df_g.index = range(1, len(df_g) + 1)
        st.markdown(f"### {grupo_nombre}")
        st.dataframe(df_g.style.format(fmt_ret, na_rep="N/A"),
                     use_container_width=True, height=min(50 + len(df_g)*36, 600))
        excel_download_btn(df_g.reset_index(), f"Rent. {grupo_nombre.split()[-1]}",
                           f"rent_{grupo_nombre.split()[-1].lower()}_{cc7}.xlsx",
                           "Rentabilidad", f"Rentabilidad {grupo_nombre} — {cc7}",
                           report_curr, key=f"dl_rent_{grupo_nombre}")
        st.markdown("---")

