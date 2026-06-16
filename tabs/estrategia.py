import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pyxirr import xirr
from utils.excel_export import excel_download_btn
from utils.calculations import convert_amount

# ── 🎯 Estrategia ──

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

    fund_count_s = df_final.groupby('Strategy')['Fund'].count().reset_index().rename(columns={'Fund': '# Inv'})
    s_stats = s_stats.merge(fund_count_s, on='Strategy', how='left')

    STRAT_ORDER = ['Buyout','Growth Equity','Secondaries','Venture Capital','Fund of Funds','Single Co-Inv','Real Estate','Credit']
    s_stats['_order'] = s_stats['Strategy'].apply(lambda x: STRAT_ORDER.index(x) if x in STRAT_ORDER else 999)
    s_stats = s_stats.sort_values('_order').drop(columns='_order').reset_index(drop=True)

    # Totales globales para % columns
    total_comm  = s_stats['Commitment'].sum()
    total_nav   = s_stats['NAV'].sum()
    total_paid  = s_stats['Paid-In'].sum()
    total_funds = s_stats['# Inv'].sum()

    PE_STRATS = ['Buyout','Growth Equity','Secondaries','Venture Capital','Fund of Funds','Single Co-Inv']

    def build_row(label, mask, indent=False):
        sub = s_stats[mask]
        if sub.empty: return None
        comm  = sub['Commitment'].sum()
        paid  = sub['Paid-In'].sum()
        unf   = sub['Unfunded'].sum()
        dist  = sub['Distributed'].sum()
        nav   = sub['NAV'].sum()
        tv    = sub['Total Value'].sum()
        n_inv = int(sub['# Inv'].sum())
        irr   = calc_pooled_irr(df_final[df_final['Strategy'].isin(sub['Strategy'].tolist())])
        tvpi  = tv / paid if paid > 0 else 0
        dpi   = dist / paid if paid > 0 else 0
        dur   = calc_wav_duration(df_final[df_final['Strategy'].isin(sub['Strategy'].tolist())])
        return {
            'Strategy':         ('  ' if indent else '') + label,
            '# Inv':            n_inv,
            'Commit (MM)':      comm / 1e6,
            'Paid In (MM)':     paid / 1e6,
            'Unfunded (MM)':    unf  / 1e6,
            'Distributed (MM)': dist / 1e6,
            'NAV (MM)':         nav  / 1e6,
            'IRR':              irr,
            'TVPI':             tvpi,
            'DPI':              dpi,
            '% Comm':           comm / total_comm * 100 if total_comm > 0 else 0,
            '% NAV':            nav  / total_nav  * 100 if total_nav  > 0 else 0,
            '% Paid In':        paid / total_paid * 100 if total_paid > 0 else 0,
            'Duration (yrs)':   dur,
        }

    rows = []

    # Private Equity header
    pe_mask = s_stats['Strategy'].isin(PE_STRATS)
    pe_row  = build_row('Private Equity', pe_mask, indent=False)
    if pe_row: rows.append(pe_row)

    # PE sub-strategies
    for strat in PE_STRATS:
        mask = s_stats['Strategy'] == strat
        if not s_stats[mask].empty:
            r = build_row(strat, mask, indent=True)
            if r: rows.append(r)

    # Other top-level strategies
    for strat in ['Real Estate', 'Credit']:
        mask = s_stats['Strategy'] == strat
        if not s_stats[mask].empty:
            r = build_row(strat, mask, indent=False)
            if r: rows.append(r)

    # Remaining strategies not in the predefined lists
    defined = PE_STRATS + ['Real Estate', 'Credit']
    for strat in s_stats['Strategy'].tolist():
        if strat not in defined:
            mask = s_stats['Strategy'] == strat
            r = build_row(strat, mask, indent=False)
            if r: rows.append(r)

    # Total row
    rows.append({
        'Strategy':         'Total',
        '# Inv':            int(total_funds),
        'Commit (MM)':      total_comm / 1e6,
        'Paid In (MM)':     total_paid / 1e6,
        'Unfunded (MM)':    s_stats['Unfunded'].sum() / 1e6,
        'Distributed (MM)': s_stats['Distributed'].sum() / 1e6,
        'NAV (MM)':         total_nav / 1e6,
        'IRR':              g_irr,
        'TVPI':             s_stats['Total Value'].sum() / total_paid if total_paid > 0 else 0,
        'DPI':              s_stats['Distributed'].sum() / total_paid if total_paid > 0 else 0,
        '% Comm':           100.0,
        '% NAV':            100.0,
        '% Paid In':        100.0,
        'Duration (yrs)':   _dur_total,
    })

    df_hier = pd.DataFrame(rows)

    fmt_hier = {
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

    group_headers = {'Private Equity', 'Real Estate', 'Credit'}
    header_rows = {'Private Equity', 'Real Estate', 'Credit', 'Total'}
    def style_hier(row):
        name = row['Strategy'].strip()
        if name == 'Total':
            return ['font-weight:bold; background-color:#eef1f7'] * len(row)
        if name in group_headers:
            return ['font-weight:bold; background-color:#dce8f5'] * len(row)
        return ['color:#444444; font-size:12px'] * len(row)

    st.dataframe(
        df_hier.style.format(fmt_hier).apply(style_hier, axis=1),
        use_container_width=True,
        height=min(50 + len(df_hier) * 35, 600),
        hide_index=True,
    )
    excel_download_btn(df_hier, "Estrategia", f"estrategia_{report_curr}.xlsx",
                       "Estrategia", f"Portfolio por Estrategia — {report_curr}",
                       report_curr, key="dl_strat")
    st.markdown("---")
    s_sorted   = s_stats.reset_index(drop=True)
    strategies = s_sorted['Strategy'].tolist()
    irr_vals   = s_sorted['IRR %'].tolist()
    tvpi_vals  = s_sorted['TVPI'].tolist()
    fig_strat  = go.Figure()
    fig_strat.add_trace(go.Bar(
        name='IRR %', x=strategies, y=irr_vals, marker_color='#002060',
        text=[f"<b>{v:.1f}%</b>" for v in irr_vals], textposition='inside',
        textfont=dict(color='white', size=13), yaxis='y1',
    ))
    fig_strat.add_trace(go.Scatter(
        name='TVPI', x=strategies, y=tvpi_vals, mode='markers+text',
        marker=dict(symbol='diamond', size=14, color='#ED7D31'),
        text=[f"<b>{v:.2f}x</b>" for v in tvpi_vals], textposition='top center',
        textfont=dict(size=12, color='#ED7D31'), yaxis='y2',
    ))
    max_irr  = max(irr_vals)  if irr_vals  else 1
    max_tvpi = max(tvpi_vals) if tvpi_vals else 1
    fig_strat.update_layout(
        title=f'Performance by Strategy ({as_of_date_dt.strftime("%d/%m/%Y")})',
        height=480, plot_bgcolor='white', showlegend=True,
        legend=dict(orientation='h', y=1.08),
        yaxis=dict(showgrid=True, gridcolor='lightgrey', ticksuffix='%',
                   range=[0, max_irr * 1.5], title='IRR %'),
        yaxis2=dict(overlaying='y', side='right', showgrid=False,
                    range=[0, max_tvpi * 1.5], ticksuffix='x', title='TVPI'),
        xaxis=dict(type='category'), margin=dict(t=80, b=60),
    )
    st.plotly_chart(fig_strat, use_container_width=True)

