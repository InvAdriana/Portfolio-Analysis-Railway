import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pyxirr import xirr
from utils.excel_export import excel_download_btn
from utils.calculations import convert_amount

# ── 📍 Point in Time ──

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

    st.markdown("### 📍 Point in Time — Rendimiento por Período")
    st.caption("Calcula Money-Weighted Return (MWR/IRR) y Time-Weighted Return (TWR) "
               "entre dos fechas seleccionadas, por estrategia y total.")

    # ── Selectores de fecha ───────────────────────────────────────────────
    pit_col1, pit_col2 = st.columns(2)
    with pit_col1:
        min_date_pit = df_flows_raw['Date'].min().date()
        pit_start = st.date_input("📅 Fecha inicio", key="pit_start",
                                   value=min_date_pit,
                                   min_value=min_date_pit)
    with pit_col2:
        pit_end = st.date_input("📅 Fecha fin", key="pit_end",
                                 value=as_of_date,
                                 max_value=as_of_date)

    pit_start_dt = pd.Timestamp(pit_start)
    pit_end_dt   = pd.Timestamp(pit_end)

    if pit_start_dt >= pit_end_dt:
        st.error("La fecha de inicio debe ser anterior a la fecha fin.")
    elif df_final.empty:
        st.info("Sin datos en el portfolio filtrado.")
    else:
        # ── Funciones de cálculo ──────────────────────────────────────────

        def get_nav_at(fund_name, f_curr, date_ts):
            """NAV de un fondo en una fecha específica (interpolado desde cashflows)."""
            f_fl = df_flows_raw[
                (df_flows_raw['Fund'] == fund_name) &
                (df_flows_raw['Date'] <= date_ts)
            ].copy()
            nav_entries = f_fl[f_fl['Type'].str.contains('NAV', case=False)].sort_values('Date')
            if not nav_entries.empty:
                ln = nav_entries.iloc[-1]
                later = f_fl[f_fl['Date'] > ln['Date']]
                nav_loc = (float(ln['Amount'])
                           + abs(float(later[later['Type'].str.contains('Call', case=False)]['Amount'].sum()))
                           - float(later[later['Type'].str.contains('Dist', case=False)]['Amount'].sum()))
                return convert_amount(nav_loc, f_curr, report_curr,
                                     fx_map.get(date_ts.date(), fx_today))
            # Sin NAV: usar paid-in acumulado como proxy
            calls = abs(f_fl[f_fl['Type'].str.contains('Call', case=False)]['Amount'].sum())
            dists = f_fl[f_fl['Type'].str.contains('Dist', case=False)]['Amount'].sum()
            return convert_amount(max(calls - dists, 0), f_curr, report_curr,
                                  fx_map.get(date_ts.date(), fx_today))

        def calc_mwr_period(fund_list, start_dt, end_dt):
            """
            Money-Weighted Return (IRR) entre start y end.
            Devuelve (mwr_ann_total, mwr_anualizado).
            El xirr ya es una tasa anualizada por definición.
            El total se obtiene: (1 + mwr_anual)^(días/365) - 1
            """
            all_flows = []
            nav_start_total = 0.0
            nav_end_total   = 0.0

            for fund in fund_list:
                f_meta = df_char[df_char['Fund'] == fund]
                if f_meta.empty: continue
                f_meta = f_meta.iloc[0]
                f_curr = f_meta['Currency']

                nav_s = get_nav_at(fund, f_curr, start_dt)
                nav_e = get_nav_at(fund, f_curr, end_dt)
                nav_start_total += nav_s
                nav_end_total   += nav_e

                mid_flows = df_flows_raw[
                    (df_flows_raw['Fund'] == fund) &
                    (df_flows_raw['Date'] > start_dt) &
                    (df_flows_raw['Date'] <= end_dt) &
                    (~df_flows_raw['Type'].str.contains('NAV', case=False))
                ].copy()
                for _, r in mid_flows.iterrows():
                    amt = convert_amount(r['Amount'], f_curr, report_curr,
                                         fx_map.get(r['Date'].date(), fx_today))
                    all_flows.append({'Date': r['Date'], 'Amt': amt})

            if nav_start_total <= 0 and not all_flows:
                return 0.0, 0.0

            flow_df  = pd.DataFrame(all_flows) if all_flows else pd.DataFrame(columns=['Date','Amt'])
            flow_agg = flow_df.groupby('Date')['Amt'].sum().reset_index() if not flow_df.empty \
                       else pd.DataFrame(columns=['Date','Amt'])

            dates   = [start_dt] + flow_agg['Date'].tolist() + [end_dt]
            amounts = [-nav_start_total] + flow_agg['Amt'].tolist() + [nav_end_total]

            from collections import defaultdict
            merged = defaultdict(float)
            for d, a in zip(dates, amounts):
                merged[d] += a
            dates_m   = sorted(merged.keys())
            amounts_m = [merged[d] for d in dates_m]

            if len(dates_m) < 2:
                return 0.0, 0.0
            try:
                mwr_ann = xirr(dates_m, amounts_m) * 100   # ya es anualizado
                if mwr_ann <= -99:
                    return 0.0, 0.0
                days = (end_dt - start_dt).days
                if days <= 0:
                    return mwr_ann, mwr_ann
                # Total del período: (1 + mwr_ann/100)^(días/365) - 1
                mwr_ann_total_pct = ((1 + mwr_ann / 100) ** (days / 365.25) - 1) * 100
                return mwr_ann_total_pct, mwr_ann
            except:
                return 0.0, 0.0

        def calc_twr_period(fund_list, start_dt, end_dt):
            """
            Time-Weighted Return entre start y end.
            Devuelve (twr_ann_total_pct, twr_anualizado_pct).
            """
            q_dates    = pd.date_range(start=start_dt, end=end_dt, freq='QE')
            eval_dates = sorted(set([start_dt] + q_dates.tolist() + [end_dt]))
            clean_dates = [eval_dates[0]]
            for d in eval_dates[1:]:
                if (d - clean_dates[-1]).days >= 1:
                    clean_dates.append(d)

            if len(clean_dates) < 2:
                return 0.0, 0.0

            product = 1.0
            for i in range(len(clean_dates) - 1):
                t0 = clean_dates[i]
                t1 = clean_dates[i + 1]
                nav_t0 = nav_t1 = calls_period = dists_period = 0.0

                for fund in fund_list:
                    f_meta = df_char[df_char['Fund'] == fund]
                    if f_meta.empty: continue
                    f_meta = f_meta.iloc[0]
                    f_curr = f_meta['Currency']
                    nav_t0 += get_nav_at(fund, f_curr, t0)
                    nav_t1 += get_nav_at(fund, f_curr, t1)
                    sub = df_flows_raw[
                        (df_flows_raw['Fund'] == fund) &
                        (df_flows_raw['Date'] > t0) &
                        (df_flows_raw['Date'] <= t1) &
                        (~df_flows_raw['Type'].str.contains('NAV', case=False))
                    ]
                    for _, r in sub.iterrows():
                        amt = convert_amount(r['Amount'], f_curr, report_curr,
                                             fx_map.get(r['Date'].date(), fx_today))
                        if r['Type'].lower().find('call') >= 0:
                            calls_period += abs(amt)
                        elif r['Type'].lower().find('dist') >= 0:
                            dists_period += amt

                denom = nav_t0 + calls_period
                if denom <= 0:
                    continue
                product *= (nav_t1 + dists_period) / denom

            twr_acum = product - 1
            days = (end_dt - start_dt).days
            if days <= 0:
                return twr_acum * 100, twr_acum * 100
            twr_ann_total_pct = twr_acum * 100
            twr_ann_pct   = ((1 + twr_acum) ** (365.25 / days) - 1) * 100
            if twr_ann_pct <= -9999:
                return 0.0, 0.0
            return twr_ann_total_pct, twr_ann_pct

        # ── Calcular por estrategia ───────────────────────────────────────
        STRAT_ORDER_PIT = ['Buyout','Growth Equity','Secondaries','Venture Capital',
                           'Fund of Funds','Single Co-Inv','Real Estate','Credit']

        pit_rows = []
        strategies_in_portfolio = df_final['Strategy'].unique().tolist()
        strategies_ordered = [s for s in STRAT_ORDER_PIT if s in strategies_in_portfolio] + \
                              [s for s in strategies_in_portfolio if s not in STRAT_ORDER_PIT]

        with st.spinner("Calculando rendimientos del período..."):
            for strat in strategies_ordered:
                funds_strat = df_final[df_final['Strategy'] == strat]['Fund'].tolist()
                if not funds_strat: continue

                nav_s = sum(get_nav_at(f, df_char[df_char['Fund']==f].iloc[0]['Currency'],
                                       pit_start_dt) for f in funds_strat
                           if not df_char[df_char['Fund']==f].empty)
                nav_e = sum(get_nav_at(f, df_char[df_char['Fund']==f].iloc[0]['Currency'],
                                       pit_end_dt) for f in funds_strat
                           if not df_char[df_char['Fund']==f].empty)

                # Flujos del período
                calls_p = dists_p = 0.0
                for fund in funds_strat:
                    fm = df_char[df_char['Fund']==fund]
                    if fm.empty: continue
                    f_curr = fm.iloc[0]['Currency']
                    mid = df_flows_raw[
                        (df_flows_raw['Fund']==fund) &
                        (df_flows_raw['Date'] > pit_start_dt) &
                        (df_flows_raw['Date'] <= pit_end_dt) &
                        (~df_flows_raw['Type'].str.contains('NAV', case=False))
                    ]
                    for _, r in mid.iterrows():
                        amt = convert_amount(r['Amount'], f_curr, report_curr,
                                             fx_map.get(r['Date'].date(), fx_today))
                        if 'call' in r['Type'].lower(): calls_p += abs(amt)
                        elif 'dist' in r['Type'].lower(): dists_p += amt

                mwr_tot, mwr_ann = calc_mwr_period(funds_strat, pit_start_dt, pit_end_dt)
                twr_tot, twr_ann = calc_twr_period(funds_strat, pit_start_dt, pit_end_dt)
                n_funds_s = len(funds_strat)

                pit_rows.append({
                    'Estrategia':       strat,
                    'N° Fondos':        n_funds_s,
                    'NAV Inicio':       nav_s,
                    'Capital Calls':    calls_p,
                    'Distribuciones':   dists_p,
                    'NAV Fin':          nav_e,
                    'MWR Total':        mwr_tot,
                    'MWR Anualizado':   mwr_ann,
                    'TWR Total':        twr_tot,
                    'TWR Anualizado':   twr_ann,
                })

            # Total portfolio
            all_funds = df_final['Fund'].tolist()
            mwr_tot_total, mwr_ann_total = calc_mwr_period(all_funds, pit_start_dt, pit_end_dt)
            twr_tot_total, twr_ann_total = calc_twr_period(all_funds, pit_start_dt, pit_end_dt)
            nav_s_total = sum(
                get_nav_at(f, df_char[df_char['Fund']==f].iloc[0]['Currency'], pit_start_dt)
                for f in all_funds if not df_char[df_char['Fund']==f].empty)
            nav_e_total = sum(
                get_nav_at(f, df_char[df_char['Fund']==f].iloc[0]['Currency'], pit_end_dt)
                for f in all_funds if not df_char[df_char['Fund']==f].empty)
            calls_total = sum(r['Capital Calls'] for r in pit_rows)
            dists_total = sum(r['Distribuciones'] for r in pit_rows)

        df_pit = pd.DataFrame(pit_rows)

        # ── Métricas globales ─────────────────────────────────────────────
        st.markdown(f"""
        <div style='background:#f0f7ff;border-left:3px solid #1a5fd4;
        padding:10px 16px;border-radius:4px;font-size:12px;margin:12px 0 16px'>
        📅 <b>Período:</b> {pit_start.strftime('%d/%m/%Y')} → {pit_end.strftime('%d/%m/%Y')}
        &nbsp;&nbsp;|&nbsp;&nbsp;
        <b>NAV Inicio:</b> {curr_sym}{nav_s_total/1e6:,.2f}M
        &nbsp;&nbsp;|&nbsp;&nbsp;
        <b>NAV Fin:</b> {curr_sym}{nav_e_total/1e6:,.2f}M
        &nbsp;&nbsp;|&nbsp;&nbsp;
        <b>Calls:</b> {curr_sym}{calls_total/1e6:,.2f}M
        &nbsp;&nbsp;|&nbsp;&nbsp;
        <b>Distribuciones:</b> {curr_sym}{dists_total/1e6:,.2f}M
        </div>
        """, unsafe_allow_html=True)

        km1, km2, km3 = st.columns(3)
        km1, km2 = st.columns(2)
        with km1:
            st.markdown("**MWR (Money-Weighted)**")
            ma1, ma2 = st.columns(2)
            ma1.metric("Total período", f"{mwr_tot_total:.2f}%",
                        help="Retorno total acumulado del período")
            ma2.metric("Anualizado (IRR)", f"{mwr_ann_total:.2f}%",
                        help="IRR anualizado: trata NAV inicio como inversión y NAV fin como retorno")
        with km2:
            st.markdown("**TWR (Time-Weighted)**")
            ta1, ta2 = st.columns(2)
            ta1.metric("Total período", f"{twr_tot_total:.2f}%",
                        help="Retorno total acumulado sin efecto de timing")
            ta2.metric("Anualizado", f"{twr_ann_total:.2f}%",
                        help="TWR anualizado: (1 + TWR_total)^(365/días) - 1")
        nav_change = nav_e_total - nav_s_total + dists_total - calls_total
        st.markdown("---")
        st.metric("Ganancia del Período", f"{curr_sym}{nav_change/1e6:,.2f}M",
                   help="(NAV Fin + Distribuciones) - (NAV Inicio + Capital Calls)")

        st.markdown("---")

        # ── Tabla agregada por estrategia ────────────────────────────────
        st.markdown("#### Rendimiento por Estrategia")

        fmt_pit = {
            'N° Fondos':      '{:.0f}',
            'NAV Inicio':     '{:,.0f}',
            'Capital Calls':  '{:,.0f}',
            'Distribuciones': '{:,.0f}',
            'NAV Fin':        '{:,.0f}',
            'MWR Total':      '{:.2f}%',
            'MWR Anualizado': '{:.2f}%',
            'TWR Total':      '{:.2f}%',
            'TWR Anualizado': '{:.2f}%',
        }

        def color_returns(val):
            if isinstance(val, (int, float)):
                if val > 0:   return 'color:#00703c; font-weight:600'
                elif val < 0: return 'color:#c00000; font-weight:600'
            return ''

        def highlight_pit_total(row):
            if row.name == 'Total':
                return ['font-weight:bold; background-color:#eef1f7'] * len(row)
            return [''] * len(row)

        if not df_pit.empty:
            # Tabla completa con fila TOTAL
            total_pit_row = pd.DataFrame([{
                'Estrategia':       'TOTAL',
                'N° Fondos':        df_final['Fund'].nunique(),
                'NAV Inicio':       nav_s_total,
                'Capital Calls':    calls_total,
                'Distribuciones':   dists_total,
                'NAV Fin':          nav_e_total,
                'MWR Total':        mwr_tot_total,
                'MWR Anualizado':   mwr_ann_total,
                'TWR Total':        twr_tot_total,
                'TWR Anualizado':   twr_ann_total,
            }])
            df_pit_display = pd.concat([df_pit, total_pit_row], ignore_index=True)
            df_pit_display.index = list(range(1, len(df_pit)+1)) + ['Total']

            st.dataframe(
                df_pit_display.style
                    .format(fmt_pit)
                    .apply(highlight_pit_total, axis=1)
                    .map(color_returns, subset=['MWR Total','MWR Anualizado','TWR Total','TWR Anualizado']),
                use_container_width=True,
                height=min(60 + len(df_pit_display) * 36, 500)
            )
            excel_download_btn(df_pit_display.reset_index(), "Point in Time",
                               f"point_in_time_{report_curr}.xlsx", "Point in Time",
                               f"Rendimiento {pit_start.strftime('%d/%m/%Y')} → {pit_end.strftime('%d/%m/%Y')}",
                               report_curr, key="dl_pit")

            # ── Detalle por estrategia (expandible) ───────────────────────
            st.markdown("---")
            st.markdown("#### Detalle por Estrategia")
            st.caption("Haz clic en una estrategia para ver sus fondos individuales.")

            fmt_f = {
                'NAV Inicio':     '{:,.0f}',
                'Capital Calls':  '{:,.0f}',
                'Distribuciones': '{:,.0f}',
                'NAV Fin':        '{:,.0f}',
                'MWR Total':      '{:.2f}%',
                'MWR Anualizado': '{:.2f}%',
                'TWR Total':      '{:.2f}%',
                'TWR Anualizado': '{:.2f}%',
            }

            for _, srow in df_pit.iterrows():
                strat      = srow['Estrategia']
                funds_list = df_final[df_final['Strategy'] == strat]['Fund'].tolist()
                mwr_color  = '🟢' if srow['MWR Total'] > 0 else '🔴'

                with st.expander(
                    f"{mwr_color} **{strat}** — "
                    f"MWR: {srow['MWR Total']:.2f}% ({srow['MWR Anualizado']:.2f}% ann)  |  "
                    f"TWR: {srow['TWR Total']:.2f}% ({srow['TWR Anualizado']:.2f}% ann)  |  "
                    f"{int(srow['N° Fondos'])} fondos",
                    expanded=False
                ):
                    fund_rows = []
                    for fund in funds_list:
                        fm = df_char[df_char['Fund'] == fund]
                        if fm.empty: continue
                        f_curr = fm.iloc[0]['Currency']
                        gp     = fm.iloc[0]['GP']
                        nav_s_f = get_nav_at(fund, f_curr, pit_start_dt)
                        nav_e_f = get_nav_at(fund, f_curr, pit_end_dt)
                        calls_f = dists_f = 0.0
                        mid_f = df_flows_raw[
                            (df_flows_raw['Fund'] == fund) &
                            (df_flows_raw['Date'] > pit_start_dt) &
                            (df_flows_raw['Date'] <= pit_end_dt) &
                            (~df_flows_raw['Type'].str.contains('NAV', case=False))
                        ]
                        for _, r in mid_f.iterrows():
                            amt = convert_amount(r['Amount'], f_curr, report_curr,
                                                 fx_map.get(r['Date'].date(), fx_today))
                            if 'call' in r['Type'].lower(): calls_f += abs(amt)
                            elif 'dist' in r['Type'].lower(): dists_f += amt

                        mwr_f_tot, mwr_f_ann = calc_mwr_period([fund], pit_start_dt, pit_end_dt)
                        twr_f_tot, twr_f_ann = calc_twr_period([fund], pit_start_dt, pit_end_dt)
                        fund_rows.append({
                            'Fund':           fund,
                            'GP':             gp,
                            'NAV Inicio':     nav_s_f,
                            'Capital Calls':  calls_f,
                            'Distribuciones': dists_f,
                            'NAV Fin':        nav_e_f,
                            'MWR Total':      mwr_f_tot,
                            'MWR Anualizado': mwr_f_ann,
                            'TWR Total':      twr_f_tot,
                            'TWR Anualizado': twr_f_ann,
                        })

                    df_funds_pit = pd.DataFrame(fund_rows)
                    if not df_funds_pit.empty:
                        df_funds_pit.index = range(1, len(df_funds_pit) + 1)
                        st.dataframe(
                            df_funds_pit.style
                                .format(fmt_f)
                                .map(color_returns,
                                          subset=['MWR Total','MWR Anualizado','TWR Total','TWR Anualizado']),
                            use_container_width=True,
                            height=min(50 + len(df_funds_pit) * 35, 420)
                        )

        # ── Gráfico comparativo MWR vs TWR ────────────────────────────────
        st.markdown("---")
        st.markdown("#### MWR vs TWR por Estrategia")
        if not df_pit.empty:
            strats_pit = df_pit['Estrategia'].tolist()
            mwr_vals   = df_pit['MWR Anualizado'].tolist()
            twr_vals   = df_pit['TWR Anualizado'].tolist()

            fig_pit = go.Figure()
            fig_pit.add_trace(go.Bar(
                name='MWR Anualizado', x=strats_pit, y=mwr_vals,
                marker_color='#002060',
                text=[f"<b>{v:.1f}%</b>" for v in mwr_vals],
                textposition='outside', textfont=dict(size=11, color='#002060'),
            ))
            fig_pit.add_trace(go.Bar(
                name='TWR Anualizado', x=strats_pit, y=twr_vals,
                marker_color='#4472C4',
                text=[f"<b>{v:.1f}%</b>" for v in twr_vals],
                textposition='outside', textfont=dict(size=11, color='#4472C4'),
            ))
            # Línea de portfolio total
            fig_pit.add_hline(y=mwr_ann_total, line_dash='dash', line_color='#ED7D31',
                               annotation_text=f"MWR Total: {mwr_ann_total:.1f}%",
                               annotation_position="top right")
            fig_pit.add_hline(y=twr_ann_total, line_dash='dot', line_color='#92D050',
                               annotation_text=f"TWR Total: {twr_ann_total:.1f}%",
                               annotation_position="bottom right")
            max_abs = max(abs(v) for v in mwr_vals + twr_vals + [mwr_ann_total, twr_ann_total]) * 1.4
            fig_pit.update_layout(
                barmode='group', height=460, plot_bgcolor='white',
                title=f'MWR vs TWR por Estrategia — {pit_start.strftime("%d/%m/%Y")} a {pit_end.strftime("%d/%m/%Y")}',
                yaxis=dict(showgrid=True, gridcolor='#eef1f7', ticksuffix='%',
                           zeroline=True, zerolinecolor='#aaa', zerolinewidth=1.5,
                           range=[-max_abs, max_abs]),
                legend=dict(orientation='h', y=1.08),
                xaxis=dict(type='category'),
                margin=dict(t=80, b=60),
            )
            st.plotly_chart(fig_pit, use_container_width=True)

            # Nota metodológica
            st.caption(
                "**MWR (Money-Weighted Return / IRR del período):** "
                "Refleja el retorno real obtenido considerando el timing y tamaño de los flujos. "
                "Penaliza si se invirtió más capital justo antes de un mal período. "
                "— "
                "**TWR Anualizado (Time-Weighted Return):** "
                "Elimina el efecto del timing de los flujos encadenando retornos sub-trimestrales, "
                "luego anualiza usando (1 + TWR_acum)^(365/días) − 1. "
                "Mide la habilidad del gestor independientemente de cuándo el inversor aportó capital."
            )

    # =========================================================================
    # TAB 11 — SIMULACIÓN
    # =========================================================================
