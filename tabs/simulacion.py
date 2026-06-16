import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pyxirr import xirr
from utils.excel_export import excel_download_btn
from utils.calculations import convert_amount

# ── 🔮 Simulación ──

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


    # ── Cargar curvas Hamilton Lane ───────────────────────────────────────
    @st.cache_data(ttl=60)
    def load_hl_curves():
        try:
            buf = load_excel_from_drive("curvas_cobalt")
        except Exception:
            return None
        sheets = ['Buyout','Growth','Secondaries','FoF',
                  'RealEstate','CreditDistressed','CreditOther']
        curves = {}
        for s in sheets:
            try:
                df = pd.read_excel(buf, sheet_name=s, header=None)
                buf.seek(0)
            except Exception:
                continue
            header_row = None
            for i, row in df.iterrows():
                if any(str(v).strip() == 'Contributions' for v in row.values):
                    header_row = i; break
            data = df.iloc[header_row+1:].copy()
            data = data[pd.to_numeric(data.iloc[:,0], errors='coerce').notna()].copy()
            is_growth = (s == 'Growth')
            if is_growth:
                # Growth: 0=quarter,1=contrib,2=dist,3=nav,4=unfunded
                #         6=contrib_pct,7=rate_return,8=dist_pct,9=nav_pct
                cdf = pd.DataFrame({
                    'quarter':       pd.to_numeric(data.iloc[:,0], errors='coerce').values,
                    'contributions': pd.to_numeric(data.iloc[:,1], errors='coerce').values,
                    'distributions': pd.to_numeric(data.iloc[:,2], errors='coerce').values,
                    'nav':           pd.to_numeric(data.iloc[:,3], errors='coerce').values,
                    'unfunded':      pd.to_numeric(data.iloc[:,4], errors='coerce').values,
                    'contrib_pct':   pd.to_numeric(data.iloc[:,6], errors='coerce').values,
                    'rate_return':   pd.to_numeric(data.iloc[:,7], errors='coerce').values,
                    'dist_pct':      pd.to_numeric(data.iloc[:,8], errors='coerce').values,
                    'nav_pct_commit':pd.to_numeric(data.iloc[:,9], errors='coerce').values,
                })
            else:
                # Others: 0=quarter,1=date,2=contrib,3=dist,4=nav,5=unfunded
                #         8=contrib_pct,9=rate_return,10=dist_pct,11=nav_pct
                cdf = pd.DataFrame({
                    'quarter':       pd.to_numeric(data.iloc[:,0], errors='coerce').values,
                    'contributions': pd.to_numeric(data.iloc[:,2], errors='coerce').values,
                    'distributions': pd.to_numeric(data.iloc[:,3], errors='coerce').values,
                    'nav':           pd.to_numeric(data.iloc[:,4], errors='coerce').values,
                    'unfunded':      pd.to_numeric(data.iloc[:,5], errors='coerce').values,
                    'contrib_pct':   pd.to_numeric(data.iloc[:,8],  errors='coerce').values,
                    'rate_return':   pd.to_numeric(data.iloc[:,9],  errors='coerce').values,
                    'dist_pct':      pd.to_numeric(data.iloc[:,10], errors='coerce').values,
                    'nav_pct_commit':pd.to_numeric(data.iloc[:,11], errors='coerce').values,
                })
            tir_r  = df[df.iloc[:,0]=='TIR']
            tvpi_r = df[df.iloc[:,0]=='TVPI']
            curves[s] = {
                'df':   cdf,
                'tir':  float(tir_r.iloc[0,1])  if not tir_r.empty  else None,
                'tvpi': float(tvpi_r.iloc[0,1]) if not tvpi_r.empty else None,
            }
        return curves

    STRAT_TO_CURVE = {
        'Buyout':         'Buyout',
        'Growth Equity':  'Growth',
        'Secondaries':    'Secondaries',
        'Venture Capital':'FoF',
        'Fund of Funds':  'FoF',
        'Single Co-Inv':  'Buyout',
        'Real Estate':    'RealEstate',
        'Credit':         'CreditOther',
    }
    CURVE_LABELS = {
        'Buyout':'Buyout','Growth':'Growth Equity','Secondaries':'Secondaries',
        'FoF':'Fund of Funds / VC','RealEstate':'Real Estate',
        'CreditDistressed':'Credit Distressed','CreditOther':'Credit Other',
    }

    def next_qend(dt):
        ts = pd.Timestamp(dt)
        mo = ts.month
        qm = ((mo-1)//3+1)*3
        return pd.Timestamp(ts.year, qm, 1) + pd.offsets.MonthEnd(0)

    def simulate_fund_hl(curve_name, commitment, current_nav,
                          current_unfunded, q_current, as_of_date, curves_dict):
        """
        Proyección usando ratios de la curva Hamilton Lane:
          Capital Call(t)  = contrib_pct(t)  × Unfunded(t-1)
          Distribuciones(t)= dist_pct(t)     × NAV(t-1)
          NAV(t)           = (NAV(t-1) - Dist(t) + Call(t)) × (1 + rate_return(t))

        Ancla: NAV y Unfunded reales del fondo en la fecha de corte.
        """
        crv    = curves_dict[curve_name]['df']
        # q_current = trimestre actual (ya transcurrido)
        # Proyectar desde q_current + 1 en adelante
        future = crv[crv['quarter'] > q_current].copy()
        if future.empty:
            return pd.DataFrame()

        # Estado inicial = valores reales del fondo hoy
        nav_t      = current_nav
        unfunded_t = current_unfunded

        # Primera fecha a proyectar = quarter end siguiente a as_of
        as_of_ts = pd.Timestamp(as_of_date)
        mo = as_of_ts.month
        qm = ((mo-1)//3+1)*3
        qdate = pd.Timestamp(as_of_ts.year, qm, 1) + pd.offsets.MonthEnd(0)
        if qdate <= as_of_ts:
            qdate += pd.offsets.QuarterEnd(1)

        rows = []
        for _, row in future.iterrows():
            contrib_pct = float(row['contrib_pct']) if pd.notna(row['contrib_pct']) else 0.0
            dist_pct    = float(row['dist_pct'])    if pd.notna(row['dist_pct'])    else 0.0
            rate_ret    = float(row['rate_return'])  if pd.notna(row['rate_return'])  else 0.0

            # Aplicar ratios al estado anterior
            call = contrib_pct * unfunded_t          # negativo (salida de caja del LP)
            dist = dist_pct    * nav_t               # positivo (entrada de caja al LP)

            # Clamp: no llamar más del unfunded disponible
            call = max(call, -unfunded_t)
            # Clamp: no distribuir más del NAV
            dist = min(dist, nav_t)

            # NAV(t) = (NAV(t-1) - Dist(t) + |Call(t)|) × (1 + RoR(t))
            # El capital llamado ENTRA al fondo → aumenta el NAV
            # Las distribuciones SALEN del fondo → reducen el NAV
            nav_new      = (nav_t - dist + abs(call)) * (1 + rate_ret)
            nav_new      = max(nav_new, 0.0)
            unfunded_new = max(unfunded_t + call, 0.0)   # call es negativo → unfunded baja

            rows.append({
                'date':          qdate,
                'quarter_num':   int(row['quarter']),
                'contributions': call,
                'distributions': dist,
                'nav':           nav_new,
                'unfunded':      unfunded_new,
                'net_cf':        dist + call,
            })

            nav_t      = nav_new
            unfunded_t = unfunded_new
            qdate      = qdate + pd.offsets.QuarterEnd(1)

            # Si NAV y unfunded llegan a 0, el fondo terminó
            if nav_t <= 0 and unfunded_t <= 0:
                break

        return pd.DataFrame(rows)

    def simulate_coinv(fund_name, commitment, current_nav,
                       exit_date, tvpi_eff, as_of_date):
        """
        Proyección lineal co-inversión:
        - NAV crece linealmente desde current_nav hasta commitment * tvpi_eff
        - En trimestre de exit: distribución total, NAV → 0
        - No hay más capital calls
        """
        as_of_ts  = pd.Timestamp(as_of_date)
        exit_ts   = pd.Timestamp(exit_date)
        exit_qend = next_qend(exit_ts)
        nav_target = commitment * tvpi_eff

        # Generar trimestres desde as_of hasta exit
        qdate = next_qend(as_of_ts)
        while qdate <= as_of_ts:
            qdate += pd.offsets.QuarterEnd(1)

        quarters = []
        q = qdate
        while q <= exit_qend + pd.offsets.QuarterEnd(1):
            quarters.append(q)
            q += pd.offsets.QuarterEnd(1)

        if not quarters:
            return pd.DataFrame()

        n = len(quarters)
        rows = []
        for i, qd in enumerate(quarters):
            is_exit = (qd >= exit_qend)
            if is_exit:
                # Exit quarter: distribuye todo el NAV
                nav_prev = nav_target if i > 0 else current_nav
                rows.append({
                    'date':          qd,
                    'quarter_num':   i + 1,
                    'contributions': 0.0,
                    'distributions': nav_target,
                    'nav':           0.0,
                    'unfunded':      0.0,
                    'net_cf':        nav_target,
                })
                break
            else:
                # Interpolación lineal del NAV
                # t va de 0 (hoy) a 1 (exit)
                t = (i + 1) / max(n - 1, 1)
                t = min(t, 1.0)
                nav_proj = current_nav + t * (nav_target - current_nav)
                rows.append({
                    'date':          qd,
                    'quarter_num':   i + 1,
                    'contributions': 0.0,
                    'distributions': 0.0,
                    'nav':           nav_proj,
                    'unfunded':      0.0,
                    'net_cf':        0.0,
                })
        return pd.DataFrame(rows)

    def agg_sim(sim_dict):
        """Agrega resultados de simulación por trimestre."""
        agg = {}
        for _, df_s in sim_dict.items():
            for _, r in df_s.iterrows():
                d = r['date']
                if d not in agg:
                    agg[d] = {'Capital Calls':0,'Distribuciones':0,'NAV':0,'Net Cash Flow':0}
                agg[d]['Capital Calls']  += abs(r['contributions'])
                agg[d]['Distribuciones'] += r['distributions']
                agg[d]['NAV']            += r['nav']
                agg[d]['Net Cash Flow']  += r['net_cf']
        df = pd.DataFrame.from_dict(agg, orient='index').sort_index()
        df['Capital Calls'] = -df['Capital Calls']
        df.index.name = 'Trimestre'
        return df

    def render_sim_chart_table(df_agg, title, report_curr, curr_sym, dl_key, dl_filename,
                                nav_actual=None, unfunded_actual=None, as_of_dt=None):
        """Renderiza gráfico + tabla + botón descarga para una simulación."""
        if df_agg.empty:
            st.info("Sin datos para proyectar.")
            return

        # Métricas
        mc1,mc2,mc3,mc4 = st.columns(4)
        mc1.metric("Calls futuros", f"{curr_sym}{abs(df_agg['Capital Calls'].sum())/1e6:,.1f}M")
        mc2.metric("Distribuciones futuras", f"{curr_sym}{df_agg['Distribuciones'].sum()/1e6:,.1f}M")
        peak_nav  = df_agg['NAV'].max()
        peak_date = df_agg['NAV'].idxmax()
        mc3.metric("NAV pico", f"{curr_sym}{peak_nav/1e6:,.1f}M")
        mc4.metric("Fecha NAV pico",
                    peak_date.strftime('%d/%m/%Y') if pd.notna(peak_date) else "—")

        # Estado actual (NAV y Unfunded de partida)
        if nav_actual is not None and as_of_dt is not None:
            as_of_str = pd.Timestamp(as_of_dt).strftime('%d/%m/%Y')
            st.markdown(
                f"<div style='background:#f0f7ff;border-left:3px solid #1a5fd4;"
                f"padding:8px 14px;border-radius:4px;font-size:12px;margin:8px 0'>"
                f"📌 <b>Estado en fecha de corte ({as_of_str}):</b> &nbsp;&nbsp;"
                f"NAV actual = <b>{curr_sym}{nav_actual/1e6:,.2f}M</b>"
                + (f" &nbsp;|&nbsp; Unfunded actual = <b>{curr_sym}{unfunded_actual/1e6:,.2f}M</b>"
                   if unfunded_actual is not None else "")
                + "</div>",
                unsafe_allow_html=True
            )

        st.markdown("---")

        dates_str = [d.strftime('%d-%m-%Y') for d in df_agg.index]
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Capital Calls', x=dates_str,
                              y=df_agg['Capital Calls']/1e6, marker_color='#ED7D31'))
        fig.add_trace(go.Bar(name='Distribuciones', x=dates_str,
                              y=df_agg['Distribuciones']/1e6, marker_color='#92D050'))
        fig.add_trace(go.Scatter(name='NAV Proyectado', x=dates_str,
                                  y=df_agg['NAV']/1e6, mode='lines+markers',
                                  line=dict(color='#FFC000', width=2),
                                  marker=dict(size=4), yaxis='y2'))
        fig.add_trace(go.Scatter(name='Net Cash Flow', x=dates_str,
                                  y=df_agg['Net Cash Flow']/1e6, mode='lines',
                                  line=dict(color='#4472C4', width=1.5, dash='dot'),
                                  yaxis='y2'))
        fig.update_layout(
            barmode='relative', height=480, plot_bgcolor='white',
            title=title,
            yaxis=dict(title=f'Cash Flow ({report_curr} M)',
                       showgrid=True, gridcolor='#eef1f7', tickformat=',.0f'),
            yaxis2=dict(title=f'NAV ({report_curr} M)', overlaying='y', side='right',
                        showgrid=False, tickformat=',.0f'),
            legend=dict(orientation='h', y=1.08),
            xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
            margin=dict(t=80, b=60),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Tabla — con fila de estado actual al inicio
        st.markdown("#### Tabla trimestral")
        df_tbl = df_agg.copy()
        df_tbl.index = [d.strftime('%d-%m-%Y') for d in df_agg.index]
        df_tbl.index.name = 'Trimestre'

        # Insertar fila de estado actual
        if nav_actual is not None and as_of_dt is not None:
            as_of_str = pd.Timestamp(as_of_dt).strftime('%d-%m-%Y')
            estado_row = pd.DataFrame([{
                'Capital Calls':  0.0,
                'Distribuciones': 0.0,
                'NAV':            nav_actual,
                'Net Cash Flow':  0.0,
            }], index=[f'► {as_of_str} (actual)'])
            if unfunded_actual is not None:
                estado_row['Unfunded'] = unfunded_actual
            df_tbl = pd.concat([estado_row, df_tbl])
            df_tbl.index.name = 'Trimestre'

        def color_ncf(val):
            if isinstance(val,(int,float)):
                return f"background-color: {'#d4edda' if val>=0 else '#f8d7da'}"
            return ''

        def highlight_actual(row):
            if str(row.name).startswith('►'):
                return ['background-color: #e8f0fe; font-weight: bold'] * len(row)
            return [''] * len(row)

        cols_fmt = {c:'{:,.0f}' for c in df_tbl.columns}
        st.dataframe(
            df_tbl.style
                  .format(cols_fmt)
                  .map(color_ncf, subset=['Net Cash Flow'])
                  .apply(highlight_actual, axis=1),
            use_container_width=True,
            height=min(420, 50+len(df_tbl)*30),
        )
        excel_download_btn(df_tbl.reset_index(), dl_filename, f"{dl_filename}.xlsx",
                           dl_filename, title, report_curr, key=f"dl_{dl_key}")

    # ── Cargar curvas ─────────────────────────────────────────────────────
    hl_curves = load_hl_curves()
    curves_ok = hl_curves is not None

    if not curves_ok:
        st.warning("⚠️ No se pudo cargar Curvas_Cobalt.xlsx desde Google Drive.")

    st.markdown("### 🔮 Simulación de Portfolio")

    # ── 3 sub-pestañas ────────────────────────────────────────────────────
    sim_tabs = st.tabs(["📈 Fondos", "🎯 Co-Inversiones", "🏛️ Portfolio Total"])

    # =====================================================================
    # SUB-TAB 1 — FONDOS (Curvas Hamilton Lane)
    # =====================================================================
    with sim_tabs[0]:
        st.markdown("#### Proyección Fondos — Curvas Hamilton Lane")
        st.caption("Cada fondo se acopla a su curva desde el trimestre actual "
                   "(basado en Fecha 1° Capital Call), usando el NAV real como ancla.")

        if not curves_ok:
            st.error("No se pudo cargar Curvas_Cobalt.xlsx desde Google Drive.")
        else:
            # Fondos hipotéticos
            st.markdown("##### ➕ Agregar fondo hipotético")
            hc1,hc2,hc3,hc4 = st.columns([2,2,1,1])
            with hc1: hypo_strat  = st.selectbox("Estrategia",
                           [s for s in STRAT_TO_CURVE if s != 'Single Co-Inv'],
                           key="hypo_strat_f")
            with hc2: hypo_comm   = st.number_input(f"Commitment ({curr_sym})",
                           min_value=100_000, value=5_000_000, step=500_000, key="hypo_comm_f")
            with hc3: hypo_yr     = st.number_input("Año inicio", 2020, 2035, 2026, key="hypo_yr_f")
            with hc4:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Agregar", key="btn_add_hypo_f"):
                    if "hypo_funds_f" not in st.session_state:
                        st.session_state["hypo_funds_f"] = []
                    st.session_state["hypo_funds_f"].append({
                        "Fund": f"Hipotético {hypo_strat[:6]} {hypo_yr}",
                        "Strategy": hypo_strat,
                        "Commitment": hypo_comm,
                    })
                    st.rerun()

            if "hypo_funds_f" not in st.session_state:
                st.session_state["hypo_funds_f"] = []
            for i, hf in enumerate(st.session_state["hypo_funds_f"]):
                ca,cb,cc,cd = st.columns([3,2,2,1])
                ca.write(hf["Fund"]); cb.write(hf["Strategy"])
                cc.write(f"{curr_sym}{hf['Commitment']/1e6:.1f}M")
                if cd.button("❌", key=f"del_hf_{i}"):
                    st.session_state["hypo_funds_f"].pop(i); st.rerun()

            st.markdown("---")

            # Construir lista fondos (excluye co-inversiones)
            COINV_STRATS = ['Single Co-Inv']
            sim_funds_f = []

            # Fondos ya en df_final (tienen flujos)
            funds_in_final = set(df_final['Fund'].tolist())

            # Incluir también fondos de df_char_filt que aún no han iniciado
            # (no están en df_final porque no tienen flujos hasta la fecha de corte)
            df_char_sim = df_char_filt[
                (~df_char_filt['Fund'].isin(funds_in_final)) &
                (~df_char_filt['Strategy'].isin(COINV_STRATS))
            ].copy()

            # Combinar: filas de df_final + filas de fondos sin iniciar
            rows_to_sim = []
            for _, frow in df_final[~df_final['Strategy'].isin(COINV_STRATS)].iterrows():
                rows_to_sim.append({
                    'Fund': frow['Fund'], 'Strategy': frow['Strategy'],
                    'Commitment': frow['Commitment'], 'NAV': frow['NAV'],
                    'Unfunded': frow['Unfunded'], 'Paid-In': frow['Paid-In'],
                    'from_final': True,
                })
            for _, crow in df_char_sim.iterrows():
                strat = crow.get('Strategy', '')
                if not STRAT_TO_CURVE.get(strat): continue
                fx_c = fx_map.get(crow['Fecha Commitment'].date(), fx_today)
                comm_rep = convert_amount(crow['Commitment'], crow['Currency'], report_curr, fx_c)
                rows_to_sim.append({
                    'Fund': crow['Fund'], 'Strategy': strat,
                    'Commitment': comm_rep, 'NAV': 0.0,
                    'Unfunded': comm_rep, 'Paid-In': 0.0,
                    'from_final': False,
                })

            for frow in rows_to_sim:
                strat = frow['Strategy']
                curve_name = STRAT_TO_CURVE.get(strat)
                if not curve_name: continue
                fund_name        = frow['Fund']
                commitment       = frow['Commitment']
                current_nav      = frow['NAV']
                current_unfunded = frow['Unfunded']

                # Saltar fondos terminados: NAV=0 pero tienen Paid-In
                if current_nav <= 0 and frow['Paid-In'] > 0:
                    continue

                char_row = df_char[df_char['Fund'] == fund_name]
                if char_row.empty: continue
                first_call_date = char_row['Fecha 1er Call'].iloc[0]
                if pd.isna(first_call_date): continue
                first_call_ts   = pd.Timestamp(first_call_date)
                mo = first_call_ts.month
                qm = ((mo-1)//3+1)*3
                first_call_qend = pd.Timestamp(first_call_ts.year, qm, 1) + pd.offsets.MonthEnd(0)
                as_of_ts    = pd.Timestamp(as_of_date_dt)
                months_diff = (as_of_ts.year - first_call_qend.year)*12 \
                              + (as_of_ts.month - first_call_qend.month)

                if months_diff < 0:
                    # Fondo aún no ha hecho primer call — proyectar desde Q1
                    q_current = 0
                    current_nav      = 0.0
                    current_unfunded = commitment
                else:
                    q_current = len(pd.date_range(first_call_qend, as_of_ts, freq='QE'))
                    crv_len   = len(hl_curves[curve_name]['df'])
                    q_current = min(q_current, crv_len - 1)

                sim_funds_f.append({
                    'name': fund_name, 'curve': curve_name,
                    'commitment': commitment, 'nav': current_nav,
                    'unfunded': current_unfunded,
                    'q_current': q_current, 'strategy': strat,
                    'first_call': first_call_qend,
                })

            # Hipotéticos
            for hf in st.session_state["hypo_funds_f"]:
                curve_name = STRAT_TO_CURVE.get(hf['Strategy'])
                if not curve_name: continue
                comm_rep = convert_amount(hf['Commitment'], 'USD', report_curr, fx_today)
                sim_funds_f.append({
                    'name': hf['Fund'], 'curve': curve_name,
                    'commitment': comm_rep, 'nav': 0.0,
                    'unfunded': comm_rep,   # hipotético: todo unfunded
                    'q_current': 1, 'strategy': hf['Strategy'],
                    'first_call': pd.Timestamp(as_of_date_dt),
                })

            # Simular
            all_sim_f = {}
            for sf in sim_funds_f:
                df_s = simulate_fund_hl(
                    sf['curve'], sf['commitment'], sf['nav'],
                    sf['unfunded'], sf['q_current'], as_of_date_dt, hl_curves
                )
                if not df_s.empty:
                    all_sim_f[sf['name']] = df_s

            df_agg_f = agg_sim(all_sim_f)
            # Totales actuales para mostrar en tabla
            total_nav_f      = sum(sf['nav']      for sf in sim_funds_f)
            total_unfunded_f = sum(sf['unfunded'] for sf in sim_funds_f)
            render_sim_chart_table(df_agg_f,
                f"Proyección Fondos — Curvas Hamilton Lane ({report_curr} M)",
                report_curr, curr_sym, "sim_fondos", "simulacion_fondos",
                nav_actual=total_nav_f,
                unfunded_actual=total_unfunded_f,
                as_of_dt=as_of_date_dt)

            # Detalle por fondo
            with st.expander("📋 Ver detalle por fondo", expanded=False):
                for sf in sim_funds_f:
                    if sf['name'] not in all_sim_f: continue
                    df_fd = all_sim_f[sf['name']]
                    fc_str = sf['first_call'].strftime('%d/%m/%Y') \
                             if hasattr(sf['first_call'],'strftime') else '—'
                    as_of_str = pd.Timestamp(as_of_date_dt).strftime('%d/%m/%Y')
                    st.markdown(f"**{sf['name']}** — {sf['strategy']} "
                                f"({CURVE_LABELS.get(sf['curve'],sf['curve'])}) "
                                f"| Commitment: {curr_sym}{sf['commitment']/1e6:.2f}M "
                                f"| 1er Call: {fc_str} "
                                f"| Trim. curva actual: **{'Aún no iniciado' if sf['q_current'] == 0 else sf['q_current']}**")
                    # Fila estado actual
                    as_of_label = f"► {pd.Timestamp(as_of_date_dt).strftime('%d-%m-%Y')} (actual)"
                    estado_fondo = pd.DataFrame([{
                        'Fecha':         as_of_str,
                        'Contributions': 0.0,
                        'Distributions': 0.0,
                        'NAV':           sf['nav'],
                        'Unfunded':      sf['unfunded'],
                        'Net CF':        0.0,
                    }], index=[as_of_label])
                    estado_fondo.index.name = 'Trim. Curva'

                    df_show = df_fd[['quarter_num','date','contributions',
                                     'distributions','nav','unfunded','net_cf']].copy()
                    df_show['date'] = df_show['date'].dt.strftime('%d-%m-%Y')
                    df_show.columns = ['Trim. Curva','Fecha','Contributions',
                                        'Distributions','NAV','Unfunded','Net CF']
                    df_show = df_show.set_index('Trim. Curva')

                    # Combinar fila actual + proyección
                    df_show_full = pd.concat([estado_fondo, df_show])

                    def hi_actual_row(row):
                        if str(row.name).startswith('►'):
                            return ['background-color:#e8f0fe;font-weight:bold'] * len(row)
                        return [''] * len(row)

                    st.dataframe(
                        df_show_full.style
                            .format({c:'{:,.0f}' for c in df_show_full.columns if c!='Fecha'})
                            .apply(hi_actual_row, axis=1),
                        use_container_width=True,
                        height=min(320, 50+len(df_show_full)*28))

    # =====================================================================
    # SUB-TAB 2 — CO-INVERSIONES
    # =====================================================================
    with sim_tabs[1]:
        st.markdown("#### Proyección Co-Inversiones — Modelo Lineal")

        coinv_ok = not df_coinv.empty
        if not coinv_ok:
            st.warning("No se encontró la pestaña `Characteristics_CoInv` en `datos.xlsx`. "
                       "Crea esa pestaña con las columnas: Fund, GP, Strategy, Currency, "
                       "Vintage, Commitment, Fecha Commitment, Geography, "
                       "Fecha 1° Capital Call, UW Exit Date, UW TVPI, "
                       "New Exit Date *(opcional)*, New TVPI *(opcional)*.")
        else:
            # Mostrar tabla de co-inversiones cargadas
            cols_show = ['Fund','GP','Commitment','Fecha 1° Capital Call',
                         'UW Exit Date','UW TVPI','New Exit Date','New TVPI']
            cols_show = [c for c in cols_show if c in df_coinv.columns]
            st.markdown("##### Co-inversiones cargadas")
            st.dataframe(df_coinv[cols_show].style.format(
                {c:'{:,.0f}' for c in ['Commitment'] if c in cols_show}),
                use_container_width=True, height=min(300, 50+len(df_coinv)*32))

            st.markdown("---")

            # Simular cada co-inversión
            all_sim_ci = {}
            skipped    = []

            for _, ci in df_coinv.iterrows():
                fund_name  = str(ci.get('Fund','')).strip()
                currency   = str(ci.get('Currency','USD')).strip().upper()

                # Commitment en moneda de reporte
                comm_raw = float(ci.get('Commitment', 0) or 0)
                commitment = convert_amount(comm_raw, currency, report_curr, fx_today)

                # NAV actual desde df_final (cashflows reales)
                nav_row = df_final[df_final['Fund'] == fund_name]
                current_nav = float(nav_row['NAV'].iloc[0]) if not nav_row.empty else 0.0

                # Exit date: New ?? UW
                exit_date = ci.get('New Exit Date') \
                            if pd.notna(ci.get('New Exit Date')) \
                            else ci.get('UW Exit Date')
                # TVPI: New ?? UW
                tvpi_eff  = float(ci.get('New TVPI'))  \
                            if pd.notna(ci.get('New TVPI')) \
                            else float(ci.get('UW TVPI', 1.5) or 1.5)

                if pd.isna(exit_date) or commitment <= 0:
                    skipped.append(fund_name)
                    continue

                # Solo proyectar si el exit es futuro
                if pd.Timestamp(exit_date) <= pd.Timestamp(as_of_date_dt):
                    skipped.append(f"{fund_name} (ya realizó exit)")
                    continue

                df_ci = simulate_coinv(fund_name, commitment, current_nav,
                                       exit_date, tvpi_eff, as_of_date_dt)
                if not df_ci.empty:
                    all_sim_ci[fund_name] = df_ci

            if skipped:
                st.caption(f"⚠️ Omitidos (sin datos o exit pasado): {', '.join(skipped)}")

            df_agg_ci = agg_sim(all_sim_ci)
            # Totales NAV actuales de co-inversiones
            total_nav_ci = sum(
                float(df_final[df_final['Fund']==str(ci.get('Fund','')).strip()]['NAV'].iloc[0])
                if not df_final[df_final['Fund']==str(ci.get('Fund','')).strip()].empty else 0.0
                for _, ci in df_coinv.iterrows()
                if str(ci.get('Fund','')).strip() in all_sim_ci
            )
            render_sim_chart_table(df_agg_ci,
                f"Proyección Co-Inversiones — Modelo Lineal ({report_curr} M)",
                report_curr, curr_sym, "sim_coinv", "simulacion_coinversiones",
                nav_actual=total_nav_ci,
                as_of_dt=as_of_date_dt)

            # Detalle por co-inversión
            with st.expander("📋 Ver detalle por co-inversión", expanded=False):
                for _, ci in df_coinv.iterrows():
                    fname = str(ci.get('Fund','')).strip()
                    if fname not in all_sim_ci: continue
                    currency  = str(ci.get('Currency','USD')).strip().upper()
                    comm_raw  = float(ci.get('Commitment',0) or 0)
                    commitment= convert_amount(comm_raw, currency, report_curr, fx_today)
                    nav_row   = df_final[df_final['Fund']==fname]
                    cur_nav   = float(nav_row['NAV'].iloc[0]) if not nav_row.empty else 0.0
                    exit_date = ci.get('New Exit Date') \
                                if pd.notna(ci.get('New Exit Date')) \
                                else ci.get('UW Exit Date')
                    tvpi_eff  = float(ci.get('New TVPI')) \
                                if pd.notna(ci.get('New TVPI')) \
                                else float(ci.get('UW TVPI',1.5) or 1.5)
                    st.markdown(
                        f"**{fname}** "
                        f"| Commitment: {curr_sym}{commitment/1e6:.2f}M "
                        f"| NAV actual: {curr_sym}{cur_nav/1e6:.2f}M "
                        f"| Exit: {pd.Timestamp(exit_date).strftime('%d/%m/%Y')} "
                        f"| TVPI efectivo: **{tvpi_eff:.2f}x** "
                        f"| NAV objetivo: {curr_sym}{commitment*tvpi_eff/1e6:.2f}M"
                    )
                    df_fd = all_sim_ci[fname].copy()
                    df_fd['date'] = df_fd['date'].dt.strftime('%d-%m-%Y')
                    df_fd = df_fd.rename(columns={
                        'quarter_num':'Trimestre','date':'Fecha',
                        'contributions':'Contributions','distributions':'Distributions',
                        'nav':'NAV','unfunded':'Unfunded','net_cf':'Net CF'
                    }).set_index('Trimestre')
                    st.dataframe(df_fd.style.format(
                        {c:'{:,.0f}' for c in df_fd.columns if c!='Fecha'}),
                        use_container_width=True,
                        height=min(300, 50+len(df_fd)*28))

    # =====================================================================
    # SUB-TAB 3 — PORTFOLIO TOTAL
    # =====================================================================
    with sim_tabs[2]:
        st.markdown("#### Proyección Portfolio Total")
        st.caption("Suma de fondos (curvas Hamilton Lane) + co-inversiones (modelo lineal).")

        # Combinar ambos diccionarios de simulaciones
        all_sim_total = {}
        if curves_ok and 'all_sim_f' in dir():
            all_sim_total.update(all_sim_f)
        if coinv_ok and 'all_sim_ci' in dir():
            all_sim_total.update(all_sim_ci)

        df_agg_total = agg_sim(all_sim_total)

        if df_agg_total.empty:
            st.info("Ejecuta primero las pestañas Fondos y Co-Inversiones para ver el total.")
