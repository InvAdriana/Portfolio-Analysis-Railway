import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pyxirr import xirr
from utils.excel_export import excel_download_btn
from utils.calculations import convert_amount

# ── 📅 Vintage ──

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

    fund_count_v = df_final.groupby('Vintage')['Fund'].count().reset_index().rename(columns={'Fund': '# Inv'})
    v_stats = v_stats.merge(fund_count_v, on='Vintage', how='left')
    v_stats = v_stats.sort_values('Vintage').reset_index(drop=True)

    total_comm_v = v_stats['Commitment'].sum()
    total_nav_v  = v_stats['NAV'].sum()
    total_paid_v = v_stats['Paid-In'].sum()
    total_funds_v = int(v_stats['# Inv'].sum())

    v_rows = []
    for _, row in v_stats.iterrows():
        paid = row['Paid-In']
        v_rows.append({
            'Vintage':          int(row['Vintage']),
            '# Inv':            int(row['# Inv']),
            'Commit (MM)':      row['Commitment'] / 1e6,
            'Paid In (MM)':     paid / 1e6,
            'Unfunded (MM)':    row['Unfunded'] / 1e6,
            'Distributed (MM)': row['Distributed'] / 1e6,
            'NAV (MM)':         row['NAV'] / 1e6,
            'IRR':              row['IRR %'],
            'TVPI':             row['TVPI'],
            'DPI':              row['DPI'],
            '% Comm':           row['Commitment'] / total_comm_v * 100 if total_comm_v > 0 else 0,
            '% NAV':            row['NAV'] / total_nav_v * 100 if total_nav_v > 0 else 0,
            '% Paid In':        paid / total_paid_v * 100 if total_paid_v > 0 else 0,
            'Duration (yrs)':   calc_wav_duration(df_final[df_final['Vintage'] == row['Vintage']]),
        })

    # Total row
    v_rows.append({
        'Vintage':          'Total',
        '# Inv':            total_funds_v,
        'Commit (MM)':      total_comm_v / 1e6,
        'Paid In (MM)':     total_paid_v / 1e6,
        'Unfunded (MM)':    v_stats['Unfunded'].sum() / 1e6,
        'Distributed (MM)': v_stats['Distributed'].sum() / 1e6,
        'NAV (MM)':         total_nav_v / 1e6,
        'IRR':              g_irr,
        'TVPI':             v_stats['Total Value'].sum() / total_paid_v if total_paid_v > 0 else 0,
        'DPI':              v_stats['Distributed'].sum() / total_paid_v if total_paid_v > 0 else 0,
        '% Comm':           100.0,
        '% NAV':            100.0,
        '% Paid In':        100.0,
        'Duration (yrs)':   _dur_total,
    })

    df_v = pd.DataFrame(v_rows)

    fmt_v = {
        '# Inv':            '{:.0f}',
        'Commit (MM)':      '{:,.1f}',
        'Paid In (MM)':     '{:,.1f}',
        'Unfunded (MM)':    '{:,.1f}',
        'Distributed (MM)': '{:,.1f}',
        'NAV (MM)':         '{:,.1f}',
        'IRR':              '{:.1f}%',
        'TVPI':             '{:.2f}x',
        'DPI':              '{:.2f}x',
        '% Comm':           '{:.1f}%',
        '% NAV':            '{:.1f}%',
        '% Paid In':        '{:.1f}%',
        'Duration (yrs)':   '{:.1f}',
    }

    def style_v(row):
        if str(row['Vintage']) == 'Total':
            return ['font-weight:bold; background-color:#eef1f7'] * len(row)
        return [''] * len(row)

    st.dataframe(
        df_v.style.format(fmt_v).apply(style_v, axis=1),
        use_container_width=True,
        height=min(50 + len(df_v) * 35, 600),
        hide_index=True,
    )
    excel_download_btn(df_v, "Vintage", f"vintage_{report_curr}.xlsx",
                       "Vintage", f"Portfolio por Vintage — {report_curr}",
                       report_curr, key="dl_vintage")
    st.markdown("---")
    gc1, gc2 = st.columns(2)
    v_sorted = df_v[df_v['Vintage'] != 'Total'].copy()
    vintages = v_sorted['Vintage'].astype(str).tolist()
    with gc1:
        fig_nav_v = go.Figure(go.Bar(
            x=vintages, y=v_sorted['% NAV'], marker_color='#4472C4',
            text=[f"<b>{v:.1f}%</b>" for v in v_sorted['% NAV']],
            textposition='outside', textfont=dict(size=14, color='#002060'),
        ))
        fig_nav_v.update_layout(
            title='% NAV por Vintage', height=450, plot_bgcolor='white', showlegend=False,
            yaxis=dict(showgrid=True, gridcolor='lightgrey', ticksuffix='%',
                       range=[0, v_sorted['% NAV'].max() * 1.25]),
            xaxis=dict(type='category'), margin=dict(t=60, b=40),
        )
        st.plotly_chart(fig_nav_v, use_container_width=True)
    with gc2:
        fig_comm_v = go.Figure(go.Bar(
            x=vintages, y=v_sorted['% Comm'], marker_color='#002060',
            text=[f"<b>{v:.1f}%</b>" for v in v_sorted['% Comm']],
            textposition='outside', textfont=dict(size=14, color='#002060'),
        ))
        fig_comm_v.update_layout(
            title='% Commitment por Vintage', height=450, plot_bgcolor='white', showlegend=False,
            yaxis=dict(showgrid=True, gridcolor='lightgrey', ticksuffix='%',
                       range=[0, v_sorted['% Comm'].max() * 1.25]),
            xaxis=dict(type='category'), margin=dict(t=60, b=40),
        )

