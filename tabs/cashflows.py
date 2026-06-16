import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pyxirr import xirr
from utils.excel_export import excel_download_btn
from utils.calculations import convert_amount

# ── 💸 Cash Flows ──

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

    st.subheader(f"Cash Flows del Portfolio ({report_curr})")
    if not df_final.empty:
        # Selector trimestral / anual
        cf_view = st.radio("Vista", ["Trimestral", "Anual"], horizontal=True, key="cf_view")

        # Usar la fecha máxima de los datos (no la fecha de corte del filtro)
        cf_end_date = df_flows_raw['Date'].max()
        mo_end  = cf_end_date.month
        qm_end  = ((mo_end-1)//3+1)*3
        cf_end_qend = pd.Timestamp(cf_end_date.year, qm_end, 1) + pd.offsets.MonthEnd(0)

        # Siempre calcular trimestral como base
        q_dates_cf = pd.date_range(start=df_flows_raw['Date'].min(), end=cf_end_qend, freq='QE')
        cf_rows = []
        for q_d in q_dates_cf:
            qs = q_d - pd.tseries.offsets.QuarterEnd()
            total_calls = total_dists = total_nav = 0.0
            for f_name in df_final['Fund'].tolist():
                f_mt = df_char[df_char['Fund'] == f_name].iloc[0]
                f_fl = df_flows_raw[df_flows_raw['Fund'] == f_name].copy()
                first_flow = f_fl['Date'].min() if not f_fl.empty else f_mt['Fecha Commitment']
                if first_flow > q_d: continue
                f_curr_ind = f_mt['Currency']
                q_flows = f_fl[(f_fl['Date'] > qs) & (f_fl['Date'] <= q_d)]
                for _, r in q_flows.iterrows():
                    amt_rep = convert_amount(r['Amount'], f_curr_ind, report_curr, fx_map.get(r['Date'].date(), fx_today))
                    if 'call' in r['Type'].lower(): total_calls += abs(amt_rep)
                    elif 'dist' in r['Type'].lower(): total_dists += amt_rep
                nav_hist = f_fl[f_fl['Date'] <= q_d]
                nav_entries_q = nav_hist[nav_hist['Type'].str.contains('NAV', case=False)].sort_values('Date')
                if not nav_entries_q.empty:
                    ln_q   = nav_entries_q.iloc[-1]
                    later_q = nav_hist[nav_hist['Date'] > ln_q['Date']]
                    nav_loc_q = (float(ln_q['Amount'])
                                 + abs(float(later_q[later_q['Type'].str.contains('Call', case=False)]['Amount'].sum()))
                                 - float(later_q[later_q['Type'].str.contains('Dist', case=False)]['Amount'].sum()))
                    total_nav += convert_amount(nav_loc_q, f_curr_ind, report_curr, fx_map.get(q_d.date(), fx_today))
                else:
                    calls_accum = abs(float(nav_hist[nav_hist['Type'].str.contains('Call', case=False)]['Amount'].sum()))
                    dists_accum = float(nav_hist[nav_hist['Type'].str.contains('Dist', case=False)]['Amount'].sum())
                    nav_cost = max(calls_accum - dists_accum, 0)
                    total_nav += convert_amount(nav_cost, f_curr_ind, report_curr, fx_map.get(q_d.date(), fx_today))
            cf_rows.append({
                "Período": q_d.strftime('%d-%m-%Y'),
                "Año": q_d.year,
                "Capital Calls": -total_calls,
                "Distribuciones": total_dists,
                "NAV": total_nav,
                "Net Cash Flow": total_dists - total_calls
            })

        df_cf_q = pd.DataFrame(cf_rows)

        if cf_view == "Anual":
            # Agregar por año: calls y dists suman, NAV toma el último del año
            df_cf_a = df_cf_q.groupby('Año').agg({
                'Capital Calls': 'sum',
                'Distribuciones': 'sum',
                'Net Cash Flow': 'sum',
                'NAV': 'last'   # NAV del último trimestre del año
            }).reset_index()
            df_cf_a['Año'] = df_cf_a['Año'].astype(str)
            df_cf = df_cf_a.set_index('Año').iloc[::-1]  # más reciente primero
            periodo_label = "Año"
            titulo_grafico = f"Capital Calls, Distribuciones y NAV por Año ({report_curr})"
            titulo_tabla   = "#### Detalle por año"
            dl_key = "dl_cf_a"
            dl_file = f"cashflows_anual_{report_curr}.xlsx"
        else:
            df_cf = df_cf_q.set_index('Período').drop(columns='Año').iloc[::-1]
            periodo_label = "Trimestre"
            titulo_grafico = f"Capital Calls, Distribuciones y NAV por Trimestre ({report_curr})"
            titulo_tabla   = "#### Detalle por trimestre"
            dl_key = "dl_cf_q"
            dl_file = f"cashflows_trimestral_{report_curr}.xlsx"

        # ── Gráfico ───────────────────────────────────────────────────────
        # Para el gráfico usar orden cronológico
        df_cf_chart = df_cf.iloc[::-1]
        fig_cf = go.Figure()
        fig_cf.add_trace(go.Bar(name="Capital Calls", x=df_cf_chart.index, y=df_cf_chart["Capital Calls"],
                                marker_color="#ED7D31",
                                text=[f"{v/1e6:,.1f}" for v in df_cf_chart["Capital Calls"]], textposition="outside"))
        fig_cf.add_trace(go.Bar(name="Distribuciones", x=df_cf_chart.index, y=df_cf_chart["Distribuciones"],
                                marker_color="#92D050",
                                text=[f"{v/1e6:,.1f}" for v in df_cf_chart["Distribuciones"]], textposition="outside"))
        fig_cf.add_trace(go.Scatter(name="NAV", x=df_cf_chart.index, y=df_cf_chart["NAV"],
                                    mode="lines+markers", line=dict(color="#FFC000", width=2),
                                    marker=dict(size=6), yaxis="y2"))
        fig_cf.update_layout(
            barmode="relative", height=500, plot_bgcolor="white",
            yaxis=dict(title=f"Cash Flow ({report_curr} M)", showgrid=True, gridcolor="lightgrey", tickformat=",.0f"),
            yaxis2=dict(title=f"NAV ({report_curr})", overlaying="y", side="right", showgrid=False, tickformat=",.0f"),
            legend=dict(orientation="h", y=1.08),
            title=titulo_grafico,
            xaxis=dict(tickangle=-45),
        )
        st.plotly_chart(fig_cf, use_container_width=True)

        # ── Debug (solo trimestral) ───────────────────────────────────────
        if cf_view == "Trimestral":
            with st.expander("🔍 Debug: desglose por fondo en un trimestre", expanded=False):
                q_debug = st.selectbox("Trimestre a inspeccionar",
                                       options=list(df_cf.index), index=0, key="cf_debug_q")
                q_d_dbg = pd.to_datetime(q_debug, dayfirst=True)
                qs_dbg  = q_d_dbg - pd.tseries.offsets.QuarterEnd()
                debug_rows = []
                for f_name in df_final['Fund'].tolist():
                    f_mt = df_char[df_char['Fund'] == f_name].iloc[0]
                    f_curr_ind = f_mt['Currency']
                    f_fl_dbg = df_flows_raw[df_flows_raw['Fund'] == f_name].copy()
                    first_flow_dbg = f_fl_dbg['Date'].min() if not f_fl_dbg.empty else f_mt['Fecha Commitment']
                    if first_flow_dbg > q_d_dbg: continue
                    q_fl = f_fl_dbg[(f_fl_dbg['Date'] > qs_dbg) & (f_fl_dbg['Date'] <= q_d_dbg)]
                    for _, r in q_fl.iterrows():
                        amt_rep = convert_amount(r['Amount'], f_curr_ind, report_curr,
                                                 fx_map.get(r['Date'].date(), fx_today))
                        debug_rows.append({
                            'Fund': f_name, 'Currency': f_curr_ind,
                            'Date': r['Date'].strftime('%d/%m/%Y'),
                            'Type': r['Type'],
                            'Amount (orig)': r['Amount'],
                            f'Amount ({report_curr})': amt_rep,
                        })
                if debug_rows:
                    df_dbg = pd.DataFrame(debug_rows)
                    st.dataframe(df_dbg.style.format({
                        'Amount (orig)': '{:,.0f}',
                        f'Amount ({report_curr})': '{:,.0f}'
                    }), use_container_width=True)
                    calls_dbg = df_dbg[df_dbg['Type'].str.contains('Call', case=False)][f'Amount ({report_curr})'].sum()
                    dists_dbg = df_dbg[df_dbg['Type'].str.contains('Dist', case=False)][f'Amount ({report_curr})'].sum()
                    st.write(f"**Total Calls:** {calls_dbg:,.0f} | **Total Dists:** {dists_dbg:,.0f}")
                else:
                    st.info("Sin flujos en este trimestre.")

        # ── Tabla ─────────────────────────────────────────────────────────
        st.markdown(titulo_tabla)
        fmt_cf = {"Capital Calls":"{:,.0f}","Distribuciones":"{:,.0f}","NAV":"{:,.0f}","Net Cash Flow":"{:,.0f}"}
        def color_netcf(val):
            return f"background-color: {'#d4edda' if val >= 0 else '#f8d7da'}"
        st.dataframe(df_cf.style.format(fmt_cf).map(color_netcf, subset=["Net Cash Flow"]),
                     use_container_width=True)
        excel_download_btn(df_cf.reset_index(), "Cash Flows", dl_file, "Cash Flows",
                           f"Cash Flows — {report_curr}", report_curr, key=dl_key)
        st.markdown("---")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total Capital Calls",  f"{curr_sym}{abs(df_cf['Capital Calls'].sum())/1e6:,.1f} M")
        c2.metric("Total Distribuciones", f"{curr_sym}{df_cf['Distribuciones'].sum()/1e6:,.1f} M")
        c3.metric("NAV Actual",           f"{curr_sym}{t_nav/1e6:,.1f} M")
        c4.metric("Net Cash Flow Total",  f"{curr_sym}{df_cf['Net Cash Flow'].sum()/1e6:,.1f} M")

        # ── Detalle por fondo (tabla transpuesta, en miles) ───────────────
        st.markdown("---")
        st.markdown("#### Detalle por fondo (en miles)")

        # Construir datos por fondo y período
        fund_cf_data = {}
        for f_name in df_final['Fund'].tolist():
            f_mt = df_char[df_char['Fund'] == f_name].iloc[0]
            f_fl = df_flows_raw[df_flows_raw['Fund'] == f_name].copy()
            first_flow = f_fl['Date'].min() if not f_fl.empty else f_mt['Fecha Commitment']
            f_curr_ind = f_mt['Currency']
            fund_cf_data[f_name] = {}

            for q_d in q_dates_cf:
                qs = q_d - pd.tseries.offsets.QuarterEnd()
                if first_flow > q_d: continue
                q_flows = f_fl[(f_fl['Date'] > qs) & (f_fl['Date'] <= q_d)]
                f_calls = f_dists = 0.0
                for _, r in q_flows.iterrows():
                    amt = convert_amount(r['Amount'], f_curr_ind, report_curr,
                                        fx_map.get(r['Date'].date(), fx_today))
                    if 'call' in r['Type'].lower(): f_calls += abs(amt)
                    elif 'dist' in r['Type'].lower(): f_dists += amt
                if f_calls == 0 and f_dists == 0:
                    continue
                # Clave según vista seleccionada
                if cf_view == "Anual":
                    period_key = str(q_d.year)
                else:
                    period_key = q_d.strftime('%d-%m-%Y')
                if period_key not in fund_cf_data[f_name]:
                    fund_cf_data[f_name][period_key] = {'CC': 0.0, 'Dist': 0.0, 'NCF': 0.0}
                fund_cf_data[f_name][period_key]['CC']   += f_calls
                fund_cf_data[f_name][period_key]['Dist'] += f_dists
                fund_cf_data[f_name][period_key]['NCF']  += f_dists - f_calls

        # Períodos únicos ordenados (más reciente primero)
        # OJO: formato DD-MM-YYYY no ordena bien como string → parsear como fecha
        raw_periods = set(p for fd in fund_cf_data.values() for p in fd.keys())
        if cf_view == "Anual":
            all_periods = sorted(raw_periods, key=lambda x: int(x), reverse=True)
        else:
            all_periods = sorted(raw_periods,
                                 key=lambda x: pd.to_datetime(x, dayfirst=True),
                                 reverse=True)

        GRUPOS_CF = {
            "🏦 Private Equity": ["Buyout","Secondaries","Growth Equity","Venture Capital","Fund of Funds"],
            "🎯 Co-Investments": ["Single Co-Inv"],
            "💳 Private Credit": ["Credit"],
            "🏢 Real Estate":    ["Real Estate"],
        }

        def fmt_k(v):
            """Formatea valor en miles con separador de miles."""
            if v == 0: return '-'
            return f"{v/1e3:,.0f}"

        def ncf_color(v):
            if v > 0: return '#00703c'
            if v < 0: return '#c00000'
            return '#888'

        # Construir HTML de la tabla con sticky headers y scroll dual
        n_periods = len(all_periods)

        # Estilos base con sticky
        th_base  = "style='background:#002060;color:white;padding:5px 6px;font-size:11px;font-weight:600;text-align:center;border:1px solid #1a3a6a;position:sticky;top:0;z-index:2;'"
        th_sub   = "style='background:#0d2d5e;color:#b0c8e8;padding:4px 4px;font-size:10px;font-weight:600;text-align:center;border:1px solid #1a3a6a;white-space:nowrap;position:sticky;top:28px;z-index:2;'"
        th_total = "style='background:#1a4a8a;color:white;padding:5px 6px;font-size:11px;font-weight:600;text-align:center;border:1px solid #1a3a6a;position:sticky;top:0;z-index:2;'"
        th_fondo = "style='background:#002060;color:white;padding:5px 8px;font-size:11px;font-weight:600;text-align:left;border:1px solid #1a3a6a;position:sticky;top:0;left:0;z-index:3;'"
        th_vint  = "style='background:#002060;color:white;padding:5px 6px;font-size:11px;font-weight:600;text-align:center;border:1px solid #1a3a6a;position:sticky;top:0;left:160px;z-index:3;'"
        th_sub_f = "style='background:#0d2d5e;color:#b0c8e8;padding:4px 4px;font-size:10px;font-weight:600;text-align:left;border:1px solid #1a3a6a;position:sticky;top:28px;left:0;z-index:3;'"
        th_sub_v = "style='background:#0d2d5e;color:#b0c8e8;padding:4px 4px;font-size:10px;font-weight:600;text-align:center;border:1px solid #1a3a6a;position:sticky;top:28px;left:160px;z-index:3;'"
        td_name  = "style='padding:4px 8px;font-size:11px;text-align:left;border:1px solid #dde;white-space:nowrap;position:sticky;left:0;z-index:1;'"
        td_vint  = "style='padding:4px 6px;font-size:11px;text-align:center;border:1px solid #dde;color:#666;position:sticky;left:160px;z-index:1;'"
        td_base  = "style='padding:4px 6px;font-size:11px;text-align:right;border:1px solid #dde;'"
        tr_group = "style='background:#dce8f5;'"
        tr_even  = "style='background:#f7f9fc;'"
        tr_odd   = "style='background:#ffffff;'"

        # Contenedor con scroll y barra superior duplicada via JS
        html = """
<style>
.cf-scroll-wrap { overflow-x: auto; max-height: 600px; overflow-y: auto; border: 1px solid #dde; border-radius: 6px; }
.cf-scroll-wrap table { border-collapse: collapse; font-family: Inter, sans-serif; }
.cf-scroll-wrap thead th { position: sticky; }
</style>
<div class="cf-scroll-wrap">
<table>
"""
        # ── Header row 1 ─────────────────────────────────────────────────
        html += f"<thead><tr>"
        html += f"<th rowspan='2' {th_fondo}>Fondo</th>"
        html += f"<th rowspan='2' {th_vint}>Vintage</th>"
        html += f"<th colspan='3' {th_total}>Total</th>"
        for p in all_periods:
            html += f"<th colspan='3' {th_base}>{p}</th>"
        html += "</tr>"

        # ── Header row 2 (CC / Dist / NCF) ───────────────────────────────
        html += "<tr>"
        for _ in range(n_periods + 1):  # +1 para Total
            html += f"<th {th_sub}>CC</th><th {th_sub}>Dist</th><th {th_sub}>NCF</th>"
        html += "</tr></thead><tbody>"

        # ── Filas de datos ────────────────────────────────────────────────
        row_idx = 0
        for grupo_nombre, estrategias in GRUPOS_CF.items():
            funds_g_df = df_final[df_final['Strategy'].isin(estrategias)][['Fund','Vintage']]
            if funds_g_df.empty: continue

            # Fila de grupo (agregado)
            g_totals = {'CC': 0.0, 'Dist': 0.0, 'NCF': 0.0}
            g_by_period = {p: {'CC': 0.0, 'Dist': 0.0, 'NCF': 0.0} for p in all_periods}
            for f_name in funds_g_df['Fund']:
                for p in all_periods:
                    for m in ['CC','Dist','NCF']:
                        val = fund_cf_data.get(f_name, {}).get(p, {}).get(m, 0.0)
                        g_by_period[p][m] += val
                        g_totals[m] += val if p == all_periods[0] or True else 0

            # Recalcular totales de grupo correctamente
            g_totals = {m: sum(g_by_period[p][m] for p in all_periods) for m in ['CC','Dist','NCF']}

            html += f"<tr {tr_group}>"
            html += f"<td {td_name} style='padding:4px 8px;font-size:11px;text-align:left;border:1px solid #dde;font-weight:700;background:#dce8f5;'>{grupo_nombre}</td>"
            html += f"<td {td_vint} style='background:#dce8f5;'></td>"
            for m in ['CC','Dist','NCF']:
                v = g_totals[m]
                color = f"color:{ncf_color(v)};" if m == 'NCF' else ''
                html += f"<td style='padding:4px 6px;font-size:11px;text-align:right;border:1px solid #dde;font-weight:700;background:#dce8f5;{color}'>{fmt_k(v)}</td>"
            for p in all_periods:
                for m in ['CC','Dist','NCF']:
                    v = g_by_period[p][m]
                    color = f"color:{ncf_color(v)};" if m == 'NCF' else ''
                    html += f"<td style='padding:4px 6px;font-size:11px;text-align:right;border:1px solid #dde;font-weight:700;background:#dce8f5;{color}'>{fmt_k(v)}</td>"
            html += "</tr>"

            # Filas individuales
            funds_sorted = funds_g_df.sort_values(['Vintage','Fund']).values.tolist()
            for f_name, vintage in funds_sorted:
                if f_name not in fund_cf_data: continue
                f_totals = {m: sum(fund_cf_data[f_name].get(p, {}).get(m, 0.0) for p in all_periods)
                            for m in ['CC','Dist','NCF']}
                if all(abs(v) < 0.01 for v in f_totals.values()): continue

                tr_style = tr_even if row_idx % 2 == 0 else tr_odd
                html += f"<tr {tr_style}>"
                html += f"<td {td_name}>&nbsp;&nbsp;{f_name}</td>"
                vint_str = str(int(vintage)) if pd.notna(vintage) else ''
                html += f"<td {td_vint}>{vint_str}</td>"
                for m in ['CC','Dist','NCF']:
                    v = f_totals[m]
                    color = f"color:{ncf_color(v)};" if m == 'NCF' else ''
                    html += f"<td style='padding:4px 6px;font-size:11px;text-align:right;border:1px solid #dde;{color}'>{fmt_k(v)}</td>"
                for p in all_periods:
                    for m in ['CC','Dist','NCF']:
                        v = fund_cf_data[f_name].get(p, {}).get(m, 0.0)
                        color = f"color:{ncf_color(v)};" if m == 'NCF' else ''
                        html += f"<td style='padding:4px 6px;font-size:11px;text-align:right;border:1px solid #dde;{color}'>{fmt_k(v)}</td>"
                html += "</tr>"
                row_idx += 1

        html += "</tbody></table></div>"
        st.markdown(html, unsafe_allow_html=True)

        # Botón descarga Excel
        # Construir df plano para descarga
        dl_rows = []
        for grupo_nombre, estrategias in GRUPOS_CF.items():
            funds_g_df = df_final[df_final['Strategy'].isin(estrategias)][['Fund','Vintage']]
            if funds_g_df.empty: continue
            for f_name, vintage in funds_g_df.sort_values(['Vintage','Fund']).values.tolist():
                if f_name not in fund_cf_data: continue
                row = {'Fondo': f_name, 'Grupo': grupo_nombre.split(' ',1)[1],
                       'Vintage': int(vintage) if pd.notna(vintage) else ''}
                for p in all_periods:
                    for m in ['CC','Dist','NCF']:
                        row[f"{p} {m}"] = fund_cf_data[f_name].get(p, {}).get(m, 0.0) / 1e3
                dl_rows.append(row)
        if dl_rows:
            df_dl = pd.DataFrame(dl_rows)
            excel_download_btn(df_dl, "CF Detalle",
                               f"cashflows_detalle_{report_curr}.xlsx",
                               "CF Detalle", f"Cash Flows por Fondo — {report_curr}",
                               report_curr, key="dl_cf_detail")

