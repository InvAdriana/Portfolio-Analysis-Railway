import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pyxirr import xirr
from utils.excel_export import excel_download_btn
from utils.calculations import convert_amount

# ── 💼 Portfolio ──

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

    fmt_p = {c: '{:,.0f}' for c in money_cols if c in df_final.columns}
    fmt_p.update({'TVPI': '{:.2f}x', 'DPI': '{:.2f}x', 'IRR %': '{:.2f}%'})
    GRUPOS = {
        "🏦 Private Equity": ["Buyout","Secondaries","Growth Equity","Venture Capital","Fund of Funds"],
        "🎯 Co-Investments": ["Single Co-Inv"],
        "💳 Private Credit": ["Credit"],
        "🏢 Real Estate":    ["Real Estate"],
    }
    for grupo_nombre, estrategias in GRUPOS.items():
        df_grupo = df_final[df_final['Strategy'].isin(estrategias)].copy()
        if df_grupo.empty: continue
        df_grupo.index = range(1, len(df_grupo) + 1)
        st.markdown(f"### {grupo_nombre}")
        st.dataframe(df_grupo.style.format(fmt_p), use_container_width=True,
                     height=min(50 + len(df_grupo) * 36, 600))
        excel_download_btn(df_grupo, grupo_nombre.split()[-1],
                           f"portfolio_{grupo_nombre.split()[-1].lower()}_{report_curr}.xlsx",
                           grupo_nombre.split()[-1], f"{grupo_nombre} — {report_curr}",
                           report_curr, key=f"dl_port_{grupo_nombre}")
        t_paid_g = df_grupo['Paid-In'].sum(); t_dist_g = df_grupo['Distributed'].sum()
        t_nav_g  = df_grupo['NAV'].sum();     t_tv_g   = df_grupo['Total Value'].sum()
        t_comm_g = df_grupo['Commitment'].sum()
        try:
            flows_g = []
            for fn in df_grupo['Fund'].tolist():
                fm = df_char[df_char['Fund'] == fn].iloc[0]; fc = fm['Currency']
                ff = df_flows_raw[(df_flows_raw['Fund'] == fn) & (df_flows_raw['Date'] <= as_of_date_dt)].copy()
                ff['Amt_Rep'] = [convert_amount(r['Amount'], fc, report_curr, fx_map.get(r['Date'].date(), fx_today)) for _, r in ff.iterrows()]
                flows_g.append(ff[~ff['Type'].str.contains('NAV', case=False)][['Date','Amt_Rep']])
            agg_g = pd.concat(flows_g, ignore_index=True).groupby('Date')['Amt_Rep'].sum().reset_index()
            # Sumar NAV al último flujo si coincide con as_of, o agregar como fila nueva
            nav_date = pd.Timestamp(as_of_date_dt)
            if nav_date in agg_g['Date'].values:
                agg_g.loc[agg_g['Date'] == nav_date, 'Amt_Rep'] += float(t_nav_g)
                irr_dates   = agg_g['Date'].tolist()
                irr_amounts = agg_g['Amt_Rep'].tolist()
            else:
                irr_dates   = agg_g['Date'].tolist() + [nav_date]
                irr_amounts = agg_g['Amt_Rep'].tolist() + [float(t_nav_g)]
            irr_g = xirr(irr_dates, irr_amounts) * 100
            if irr_g < -99 or irr_g > 500: irr_g = 0
        except: irr_g = 0
        tvpi_g = t_tv_g / t_paid_g if t_paid_g > 0 else 0
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Commitment", f"{curr_sym}{t_comm_g/1e6:,.1f} M")
        c2.metric("Paid-In",    f"{curr_sym}{t_paid_g/1e6:,.1f} M")
        c3.metric("NAV",        f"{curr_sym}{t_nav_g/1e6:,.1f} M")
        c4.metric("Pooled IRR", f"{irr_g:.2f}%")
        c5.metric("TVPI",       f"{tvpi_g:.2f}x")
        st.markdown("---")

    CURR_OPTIONS = ["USD", "EUR", "GBP", "Local (moneda origen)"]
    CURR_KEYS    = {"USD":"USD","EUR":"EUR","GBP":"GBP","Local (moneda origen)":"Local"}
    DEFAULT_IDX  = {"USD":0,"EUR":1,"GBP":2}
    def curr_caption(cc):
    if cc == "Local":
        return "Flujos en moneda original de cada fondo — sin conversión FX."
    return f"Flujos convertidos a {cc} usando tipos de cambio históricos BCE."

    GRUPOS_EV = {
    "🏦 Private Equity": ["Buyout","Secondaries","Growth Equity","Venture Capital","Fund of Funds"],
    "🎯 Co-Investments": ["Single Co-Inv"],
    "💳 Private Credit": ["Credit"],
    "🏢 Real Estate":    ["Real Estate"],
    }

