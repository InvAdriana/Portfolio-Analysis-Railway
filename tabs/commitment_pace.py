import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pyxirr import xirr
from utils.excel_export import excel_download_btn
from utils.calculations import convert_amount

# ── 📆 Commitment Pace ──

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

    st.subheader(f"Commitment Pace ({report_curr})")
    CO_INV_STRATS = ["Single Co-Inv"]
    df_pace = df_char_filt.copy()
    df_pace['Commitment_Rep'] = df_pace.apply(
        lambda r: convert_amount(r['Commitment'], r['Currency'], report_curr,
                                 fx_map.get(r['Fecha Commitment'].date(), fx_today)), axis=1)
    df_pace['Año Commitment'] = df_pace['Fecha Commitment'].dt.year
    df_pace['Es CoInv']       = df_pace['Strategy'].isin(CO_INV_STRATS)
    def build_pace_chart(df_src, group_col, title):
        grp = df_src.groupby([group_col,'Es CoInv'])['Commitment_Rep'].sum().reset_index()
        years = sorted(df_src[group_col].unique())
        fondos_y=[];coinv_y=[];total_y=[];pct_coinv=[]
        for y in years:
            sub   = grp[grp[group_col]==y]
            f_val = float(sub[~sub['Es CoInv']]['Commitment_Rep'].sum())
            c_val = float(sub[sub['Es CoInv']]['Commitment_Rep'].sum())
            tot   = f_val + c_val
            fondos_y.append(f_val);coinv_y.append(c_val);total_y.append(tot)
            pct_coinv.append(c_val/tot*100 if tot>0 else 0)
        years_str = [str(y) for y in years]
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Fondos', x=years_str, y=[v/1e6 for v in fondos_y],
                             marker_color='#002060', text=[f"<b>{v/1e6:.1f}</b>" for v in fondos_y],
                             textposition='inside', textfont=dict(color='white',size=12), yaxis='y1'))
        fig.add_trace(go.Bar(name='Single Co-Inv', x=years_str, y=[v/1e6 for v in coinv_y],
                             marker_color='#ED7D31',
                             text=[f"<b>{v/1e6:.1f}</b>" if v>0 else '' for v in coinv_y],
                             textposition='inside', textfont=dict(color='white',size=12), yaxis='y1'))
        fig.add_trace(go.Scatter(x=years_str, y=[v/1e6 for v in total_y], mode='text',
                                 text=[f"<b>{v/1e6:.1f}</b>" for v in total_y],
                                 textposition='top center', textfont=dict(size=13,color='#002060'),
                                 showlegend=False, yaxis='y1'))
        fig.add_trace(go.Scatter(name='% Co-Inv', x=years_str, y=pct_coinv,
                                 mode='lines+markers+text', line=dict(color='#4472C4',width=2),
                                 marker=dict(size=7),
                                 text=[f"<b>{v:.0f}%</b>" if v>0 else '-' for v in pct_coinv],
                                 textposition='top center', textfont=dict(size=12,color='#4472C4'),
                                 yaxis='y2'))
        max_mm = max(total_y)/1e6 if total_y else 1
        fig.update_layout(barmode='stack', title=title, height=480, plot_bgcolor='white',
                          legend=dict(orientation='h',y=1.08),
                          yaxis=dict(title=f'Commitment ({report_curr} MM)',showgrid=True,gridcolor='lightgrey',range=[0,max_mm*1.35]),
                          yaxis2=dict(title='% Co-Inv',overlaying='y',side='right',showgrid=False,range=[-110,110],ticksuffix='%'),
                          xaxis=dict(type='category'), margin=dict(t=80,b=40))
        return fig

    def build_pace_table(df_src, group_col):
        """Tabla % compromiso por estrategia: años en filas (más nuevo primero), estrategias en columnas."""
        grp = df_src.groupby([group_col, 'Strategy'])['Commitment_Rep'].sum().reset_index()
        years = sorted(df_src[group_col].unique(), reverse=True)  # más nuevo primero
        strategies = sorted(df_src['Strategy'].unique())
        rows = []
        for y in years:
            total_y = grp[grp[group_col] == y]['Commitment_Rep'].sum()
            row = {'Año': str(int(y))}
            for strat in strategies:
                strat_y = float(grp[(grp[group_col] == y) & (grp['Strategy'] == strat)]['Commitment_Rep'].sum())
                row[strat] = (strat_y / total_y * 100) if total_y > 0 else 0.0
            row['Total'] = 100.0 if total_y > 0 else 0.0
            rows.append(row)
        df_tbl = pd.DataFrame(rows).set_index('Año')
        fmt = {c: '{:.1f}%' for c in df_tbl.columns}
        def highlight_total_col(row):
            return ['font-weight:bold; background-color:#eef1f7' if c == 'Total'
                    else '' for c in row.index]
        st.dataframe(
            df_tbl.style.format(fmt).apply(highlight_total_col, axis=1),
            use_container_width=True,
            height=min(50 + len(df_tbl) * 35, 400)
        )

    st.markdown("#### Por Vintage Year")
    st.plotly_chart(build_pace_chart(df_pace,'Vintage',f'Commitment por Vintage Year ({report_curr} MM)'),
                    use_container_width=True)
    st.markdown("##### % Compromiso por Estrategia — Vintage Year")
    build_pace_table(df_pace, 'Vintage')
    st.markdown("---")
    st.markdown("#### Por Año de Fecha Commitment")
    st.plotly_chart(build_pace_chart(df_pace,'Año Commitment',f'Commitment por Año de Inversión ({report_curr} MM)'),
                    use_container_width=True)
    st.markdown("##### % Compromiso por Estrategia — Año Commitment")
    build_pace_table(df_pace, 'Año Commitment')

    # TAB 10 — POINT IN TIME
    # =========================================================================
