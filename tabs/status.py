import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pyxirr import xirr
from utils.excel_export import excel_download_btn
from utils.calculations import convert_amount

# ── 📊 Status ──

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

    t_tv   = t_dist + t_nav
    t_unf  = max(t_comm - t_paid, 0)
    t_gl   = t_tv - t_paid
    g_tvpi = t_tv / t_paid if t_paid > 0 else 0
    g_dpi  = t_dist / t_paid if t_paid > 0 else 0
    # N° inversiones y relaciones: solo fondos con Fecha Commitment <= as_of
    df_committed = df_final[df_final['committed'] == True]
    n_funds = len(df_committed)
    n_gps   = df_char_filt[df_char_filt['Fecha Commitment'] <= as_of_date_dt]['GP'].nunique()

    st.markdown("""
    <style>
    .kpi-row { display:flex; gap:0px; border:1.5px solid #d0d8e8; border-radius:10px; overflow:hidden; margin-bottom:22px; }
    .kpi-cell { flex:1; text-align:center; padding:14px 8px 12px 8px; border-right:1px solid #d0d8e8; background:#fff; }
    .kpi-cell:last-child { border-right:none; }
    .kpi-cell:hover { background:#f4f7fc; }
    .kpi-v { font-size:20px; font-weight:700; color:#002060; line-height:1.2; }
    .kpi-l { font-size:10px; font-weight:600; letter-spacing:0.8px; text-transform:uppercase; color:#7a93b8; margin-top:4px; text-decoration:underline; }
    .perf-box { border:1.5px solid #d0d8e8; border-radius:10px; padding:20px 16px; background:#fff; height:100%; }
    .perf-row { display:flex; justify-content:space-between; align-items:baseline; padding:12px 0; border-bottom:1px solid #eef1f7; }
    .perf-row:last-child { border-bottom:none; }
    .perf-metric { font-size:28px; font-weight:700; color:#002060; }
    .perf-label { font-size:11px; color:#7a93b8; font-weight:600; letter-spacing:0.8px; text-transform:uppercase; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="kpi-row">
      <div class="kpi-cell"><div class="kpi-v">{curr_sym}{t_comm/1e6:,.1f} MM</div><div class="kpi-l">Commitment</div></div>
      <div class="kpi-cell"><div class="kpi-v">{n_funds}</div><div class="kpi-l">Inversiones</div></div>
      <div class="kpi-cell"><div class="kpi-v">{n_gps}</div><div class="kpi-l">Relaciones</div></div>
      <div class="kpi-cell"><div class="kpi-v">{curr_sym}{t_paid/1e6:,.1f} MM</div><div class="kpi-l">Paid-In</div></div>
      <div class="kpi-cell"><div class="kpi-v">{curr_sym}{t_unf/1e6:,.1f} MM</div><div class="kpi-l">Unfunded</div></div>
      <div class="kpi-cell"><div class="kpi-v">{curr_sym}{t_dist/1e6:,.1f} MM</div><div class="kpi-l">Distributed</div></div>
      <div class="kpi-cell"><div class="kpi-v">{curr_sym}{t_nav/1e6:,.1f} MM</div><div class="kpi-l">NAV</div></div>
      <div class="kpi-cell"><div class="kpi-v">{curr_sym}{t_tv/1e6:,.1f} MM</div><div class="kpi-l">Total Value</div></div>
      <div class="kpi-cell"><div class="kpi-v">{curr_sym}{t_gl/1e6:,.1f} MM</div><div class="kpi-l">Utilidad</div></div>
    </div>
    """, unsafe_allow_html=True)

    l_c, r_c = st.columns([4, 1])
    with l_c:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Commitment', x=['Commitment'], y=[t_comm],
            marker_color='#002060',
            text=[f"<b>{t_comm/1e6:,.1f}</b>"], textposition='inside',
            textfont=dict(color='white', size=13), width=0.6,
        ))
        fig.add_trace(go.Bar(
            name='Paid-In', x=['Allocation'], y=[t_paid],
            marker_color='#ED7D31',
            text=[f"<b>{t_paid/1e6:,.1f}</b>"], textposition='inside',
            textfont=dict(color='white', size=13), width=0.6,
        ))
        fig.add_trace(go.Bar(
            name='Unfunded', x=['Allocation'], y=[t_unf],
            marker_color='rgba(0,0,0,0)',
            marker_line_color='#002060', marker_line_width=2,
            text=[f"<b>{t_unf/1e6:,.1f}</b>"], textposition='outside',
            textfont=dict(color='#002060', size=13), width=0.6,
        ))
        for name, val, color in [
            ('Distributed', t_dist, '#92D050'),
            ('NAV',         t_nav,  '#FFC000'),
            ('Total Value', t_tv,   '#4472C4'),
        ]:
            fig.add_trace(go.Bar(
                name=name, x=[name], y=[val],
                marker_color=color,
                text=[f"<b>{val/1e6:,.1f}</b>"], textposition='inside',
                textfont=dict(color='white', size=13), width=0.6,
            ))
        max_val = max(t_comm, t_tv)
        fig.update_layout(
            barmode='stack', height=460,
            plot_bgcolor='white', paper_bgcolor='white',
            showlegend=True,
            legend=dict(orientation='h', y=1.08, font=dict(size=11)),
            title=dict(text=f"Portfolio Value Composition ({report_curr} MM)",
                       font=dict(size=14, color='#002060'), x=0),
            yaxis=dict(showgrid=True, gridcolor='#eef1f7', zeroline=False,
                       tickfont=dict(color='#999'), range=[0, max_val * 1.25]),
            xaxis=dict(tickfont=dict(size=13, color='#002060')),
            margin=dict(t=60, b=10, l=10, r=10),
        )
        st.plotly_chart(fig, use_container_width=True)

    with r_c:
        st.markdown(f"""
        <div class="perf-box" style="min-width:110px">
          <div class="perf-row"><div>
            <div class="perf-metric" style="font-size:22px">{g_irr:.2f}%</div>
            <div class="perf-label">Net IRR</div>
          </div></div>
          <div class="perf-row"><div>
            <div class="perf-metric" style="font-size:22px">{g_tvpi:.2f}x</div>
            <div class="perf-label">TVPI</div>
          </div></div>
          <div class="perf-row"><div>
            <div class="perf-metric" style="font-size:22px">{g_dpi:.2f}x</div>
            <div class="perf-label">DPI</div>
          </div></div>
          <div class="perf-row"><div>
            <div class="perf-metric" style="font-size:22px">{(t_nav/t_paid):.2f}x</div>
            <div class="perf-label">RVPI</div>
          </div></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    div1, div2 = st.columns(2)
    ASSET_GROUPS = {
        "Private Equity": ["Buyout", "Secondaries", "Growth Equity", "Venture Capital", "Fund of Funds"],
        "Co-Investments": ["Single Co-Inv"],
        "Private Credit": ["Credit"],
        "Real Estate":    ["Real Estate"],
    }
    ASSET_COLORS = ['#002060', '#ED7D31', '#FFC000', '#4472C4']
    df_nav_asset = df_final.copy()
    def map_group(s):
        for g, strats in ASSET_GROUPS.items():
            if s in strats: return g
        return "Otros"
    df_nav_asset['Asset Group'] = df_nav_asset['Strategy'].apply(map_group)
    nav_by_asset = df_nav_asset.groupby('Asset Group')['NAV'].sum().reset_index()
    nav_by_asset = nav_by_asset[nav_by_asset['NAV'] > 0]

    with div1:
        fig_div1 = go.Figure(go.Pie(
            labels=nav_by_asset['Asset Group'], values=nav_by_asset['NAV'],
            marker=dict(colors=ASSET_COLORS[:len(nav_by_asset)]),
            textinfo='label+percent', textfont=dict(size=14),
            hovertemplate='%{label}<br>NAV: ' + curr_sym + '%{value:,.0f}<br>%{percent}<extra></extra>',
            hole=0.35,
        ))
        fig_div1.update_layout(
            title=dict(text="% NAV por Tipo de Activo", font=dict(size=14, color='#002060'), x=0),
            height=500, showlegend=True,
            legend=dict(orientation='h', y=-0.06, font=dict(size=12)),
            margin=dict(t=50, b=60, l=40, r=40),
        )
        st.plotly_chart(fig_div1, use_container_width=True)

    GEO_COLORS = ['#002060', '#ED7D31', '#4472C4', '#FFC000', '#92D050']
    df_nav_geo = df_final.merge(df_char_filt[['Fund','Geography']], on='Fund', how='left')
    df_nav_geo['Geography'] = df_nav_geo['Geography'].fillna('Unknown')
    nav_by_geo = df_nav_geo.groupby('Geography')['NAV'].sum().reset_index()
    nav_by_geo = nav_by_geo[nav_by_geo['NAV'] > 0]

    with div2:
        fig_div2 = go.Figure(go.Pie(
            labels=nav_by_geo['Geography'], values=nav_by_geo['NAV'],
            marker=dict(colors=GEO_COLORS[:len(nav_by_geo)]),
            textinfo='label+percent', textfont=dict(size=14),
            hovertemplate='%{label}<br>NAV: ' + curr_sym + '%{value:,.0f}<br>%{percent}<extra></extra>',
            hole=0.35,
        ))
        fig_div2.update_layout(
            title=dict(text="% NAV por Geografía", font=dict(size=14, color='#002060'), x=0),
            height=500, showlegend=True,
            legend=dict(orientation='h', y=-0.06, font=dict(size=12)),
            margin=dict(t=50, b=60, l=40, r=40),
        )
        st.plotly_chart(fig_div2, use_container_width=True)

    money_cols = ['Commitment', 'Paid-In', 'Unfunded', 'Distributed', 'NAV', 'Total Value']

