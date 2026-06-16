import streamlit as st
import pandas as pd
from datetime import timedelta
from utils.calculations import (get_fx_map_institutional, convert_amount,
                                 compute_portfolio, _calc_quarterly_evolutions,
                                 _calc_pooled_irr)

def render_sidebar(df_char, df_flows_raw, df_coinv):
    """
    Renders sidebar and computes all shared state.
    Returns a context dict with everything tabs need.
    """
    
    # ── Alarma de calidad de datos ────────────────────────────────────────────
    dq = st.session_state.get('_data_quality_errors')
    if dq:
    bad_calls = dq['bad_calls']
    bad_dists = dq['bad_dists']
    with st.expander("⚠️ Errores de datos detectados en Cashflows — haz clic para ver", expanded=False):
        if not bad_calls.empty:
            st.markdown(
                f"**🔴 Capital Calls con signo positivo** — deberían ser negativos "
                f"({len(bad_calls)} flujo{'s' if len(bad_calls)>1 else ''}):"
            )
            bad_calls_show = bad_calls.copy()
            bad_calls_show['Date'] = bad_calls_show['Date'].dt.strftime('%d/%m/%Y')
            st.dataframe(
                bad_calls_show.style.format({'Amount': '{:,.0f}'}),
                use_container_width=True,
                height=min(150, 40 + len(bad_calls_show) * 35),
            )
        if not bad_dists.empty:
            st.markdown(
                f"**🔴 Distribuciones con signo negativo** — deberían ser positivas "
                f"({len(bad_dists)} flujo{'s' if len(bad_dists)>1 else ''}):"
            )
            bad_dists_show = bad_dists.copy()
            bad_dists_show['Date'] = bad_dists_show['Date'].dt.strftime('%d/%m/%Y')
            st.dataframe(
                bad_dists_show.style.format({'Amount': '{:,.0f}'}),
                use_container_width=True,
                height=min(150, 40 + len(bad_dists_show) * 35),
            )
        st.caption(
            "Corrige estos valores en la hoja **Cashflows** de `datos.xlsx`. "
            "Los signos incorrectos distorsionan el cálculo de TIR y los totales."
        )
    
    # Logo header
    st.sidebar.markdown("""
    <div class="sb-logo">
      <div class="sb-logo-mark">FO</div>
      <div>
    <div class="sb-logo-name">Family Office OS</div>
    <div class="sb-logo-sub">Alternative Assets</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ── Configuración (moneda + fecha) ────────────────────────────────────────
    st.sidebar.markdown('<div class="sb-section-label">Configuración</div>',
                    unsafe_allow_html=True)
    
    report_curr = st.sidebar.selectbox("Moneda de Reporte", ["USD", "EUR", "GBP"],
                                    label_visibility="visible")
    curr_sym    = {"USD": "$", "EUR": "€", "GBP": "£"}[report_curr]
    as_of_date  = st.sidebar.date_input("Fecha de Corte",
                                     value=df_flows_raw['Date'].max().date())
    as_of_date_dt = pd.to_datetime(as_of_date)
    
    # fx_map cubre desde el primer flujo hasta la fecha máxima de datos
    # (necesario para Cash Flows que muestra todos los trimestres independiente del corte)
    fx_map_end = max(pd.Timestamp(as_of_date), df_flows_raw['Date'].max())
    fx_map = get_fx_map_institutional(
    df_flows_raw['Date'].min() - timedelta(days=30), fx_map_end
    )
    # fx_map ahora siempre devuelve un mapa válido (con fallback si la API falla)
    # Verificar si se usaron tasas de fallback mostrando un aviso suave
    as_of_key = as_of_date.date() if hasattr(as_of_date, 'date') else as_of_date
    fx_today  = fx_map.get(as_of_key, {"USD": 1.08, "GBP": 0.86})
    if fx_today == {"USD": 1.08, "GBP": 0.86}:
    st.sidebar.caption("⚠️ Tasas BCE no disponibles — usando EUR/USD 1.08, EUR/GBP 0.86")
    
    # Tasas BCE pill
    st.sidebar.markdown(f"""
    <div class="sb-rates">
      <div class="sb-rates-title">Tasas BCE</div>
      <div class="sb-rate-row">
    <span class="sb-rate-key">EUR / USD</span>
    <span class="sb-rate-val">{fx_today['USD']:.4f}</span>
      </div>
      <div class="sb-rate-row">
    <span class="sb-rate-key">EUR / GBP</span>
    <span class="sb-rate-val">{fx_today['GBP']:.4f}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ── Filtros — estilo CobaltLP (expanders colapsables) ────────────────────
    st.sidebar.markdown('<div class="sb-section-label">Chart Filters</div>',
                    unsafe_allow_html=True)
    
    all_gps    = sorted(df_char["GP"].unique().tolist())
    all_funds  = sorted(df_char["Fund"].unique().tolist())
    all_strats = sorted(df_char["Strategy"].unique().tolist())
    all_geos   = sorted(df_char["Geography"].unique().tolist()) if "Geography" in df_char.columns else []
    
    # Inicializar selecciones en session_state
    if "gp_sel"    not in st.session_state: st.session_state["gp_sel"]    = all_gps
    if "fund_sel"  not in st.session_state: st.session_state["fund_sel"]  = all_funds
    if "strat_sel" not in st.session_state: st.session_state["strat_sel"] = all_strats
    if "geo_sel"   not in st.session_state: st.session_state["geo_sel"]   = all_geos
    
    # Expander GP
    with st.sidebar.expander("⬥  GP / Manager", expanded=False):
    sel_all_gp = st.checkbox("Seleccionar todos", value=True, key="chk_gp")
    gp_filt = st.multiselect(
        "GP", all_gps,
        default=all_gps if sel_all_gp else st.session_state["gp_sel"],
        key="ms_gp", label_visibility="collapsed"
    )
    
    # Expander Estrategia
    with st.sidebar.expander("⬥  Style / Focus", expanded=False):
    sel_all_strat = st.checkbox("Seleccionar todas", value=True, key="chk_strat")
    strat_filt = st.multiselect(
        "Estrategia", all_strats,
        default=all_strats if sel_all_strat else st.session_state["strat_sel"],
        key="ms_strat", label_visibility="collapsed"
    )
    
    # Expander Vintage Year
    all_vintages = sorted(df_char["Vintage"].dropna().unique().astype(int).tolist())
    with st.sidebar.expander("⬥  Vintage Year", expanded=False):
    sel_all_vint = st.checkbox("Seleccionar todos", value=True, key="chk_vint")
    vint_filt = st.multiselect(
        "Vintage", all_vintages,
        default=all_vintages if sel_all_vint else [],
        key="ms_vint", label_visibility="collapsed"
    )
    
    # Expander Fondo
    with st.sidebar.expander("⬥  Fund", expanded=False):
    sel_all_fund = st.checkbox("Seleccionar todos", value=True, key="chk_fund")
    fund_filt = st.multiselect(
        "Fondo", all_funds,
        default=all_funds if sel_all_fund else st.session_state["fund_sel"],
        key="ms_fund", label_visibility="collapsed"
    )
    
    # Expander Geografía (si existe la columna)
    if all_geos:
    with st.sidebar.expander("⬥  Geography", expanded=False):
        sel_all_geo = st.checkbox("Seleccionar todas", value=True, key="chk_geo")
        geo_filt = st.multiselect(
            "Geografía", all_geos,
            default=all_geos if sel_all_geo else st.session_state["geo_sel"],
            key="ms_geo", label_visibility="collapsed"
        )
    else:
    geo_filt = []
    
    # Botón Clear All (filtros)
    st.sidebar.markdown('<div class="sb-clear-btn">', unsafe_allow_html=True)
    if st.sidebar.button("Clear All", key="btn_clear"):
    for key in ["chk_gp", "chk_fund", "chk_strat", "chk_vint", "chk_geo"]:
        if key in st.session_state:
            st.session_state[key] = False
    st.rerun()
    # Botón limpiar caché de cálculos
    if st.sidebar.button("🔄 Recalcular todo", key="btn_clear_cache",
                      help="Limpia el caché y recalcula todos los datos desde cero"):
    st.cache_data.clear()
    st.rerun()
    if st.sidebar.button("☁️ Recargar datos Drive", key="btn_reload_drive",
                      help="Fuerza releer datos.xlsx desde Google Drive"):
    load_data.clear()
    st.rerun()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────────
    # 6. APLICAR FILTROS
    # ─────────────────────────────────────────────────────────────────────────
    # Para cada filtro: si el multiselect está vacío Y el checkbox "todos" está
    # desmarcado → filtrar por lista vacía (mostrar nada).
    # Si el multiselect está vacío Y el checkbox "todos" está marcado → no filtrar.
    
    mask_gp    = df_char["GP"].isin(gp_filt)       if gp_filt    else (pd.Series(True,  index=df_char.index) if sel_all_gp   else pd.Series(False, index=df_char.index))
    mask_fund  = df_char["Fund"].isin(fund_filt)    if fund_filt  else (pd.Series(True,  index=df_char.index) if sel_all_fund else pd.Series(False, index=df_char.index))
    mask_strat = df_char["Strategy"].isin(strat_filt) if strat_filt else (pd.Series(True, index=df_char.index) if sel_all_strat else pd.Series(False, index=df_char.index))
    
    df_char_filt = df_char[mask_gp & mask_fund & mask_strat].copy()
    
    # Filtro vintage — convertir a int para evitar mismatch float vs int
    if vint_filt:
    df_char_filt = df_char_filt[
        df_char_filt["Vintage"].fillna(-1).astype(int).isin(vint_filt)
    ]
    elif not sel_all_vint:
    df_char_filt = df_char_filt.iloc[0:0]
    
    # Filtro geografía
    if all_geos:
    if geo_filt:
        df_char_filt = df_char_filt[df_char_filt["Geography"].isin(geo_filt)]
    elif not sel_all_geo:
        df_char_filt = df_char_filt.iloc[0:0]
    
    data_hash = hash(tuple(df_flows_raw[['Fund','Date','Type','Amount']].values.tobytes()))
    df_final, all_flows_rep_global = compute_portfolio(
    df_char_filt.reset_index(drop=True),
    df_flows_raw,
    report_curr,
    as_of_date_dt,
    fx_map,
    (tuple(sorted(df_char_filt['Fund'].tolist())),
     str(as_of_date_dt.date()), report_curr,
     round(fx_today.get('USD', 1.0), 6),
     data_hash),
    )
    if not df_final.empty:
    df_final.index = range(1, len(df_final) + 1)
    
    # ─────────────────────────────────────────────────────────────────────────
    # 7. FUNCIONES DE ANÁLISIS (sin cambios)
    # ─────────────────────────────────────────────────────────────────────────
    def calc_quarterly_evolutions(calc_curr):
    # Hash del contenido de los datos para detectar cambios en el Excel
    data_hash = hash(tuple(df_flows_raw[['Fund','Date','Type','Amount']].values.tobytes()))
    return _calc_quarterly_evolutions(
        calc_curr, df_final, df_flows_raw, df_char,
        as_of_date_dt, fx_map, fx_today,
        (tuple(sorted(df_final['Fund'].tolist())),
         str(as_of_date_dt.date()), calc_curr,
         round(fx_today.get('USD', 1.0), 6),
         data_hash),
        "v6",
    )
    
    def calc_pooled_irr(group_df):
    fund_list  = tuple(sorted(group_df['Fund'].tolist()))
    nav_total  = float(group_df['NAV'].sum())
    return _calc_pooled_irr(
        fund_list, nav_total, report_curr, as_of_date_dt,
        df_flows_raw, df_char, fx_map, fx_today
    )
    
    v_stats = df_final.groupby('Vintage').agg({
    'Commitment': 'sum', 'Paid-In': 'sum', 'Unfunded': 'sum',
    'Distributed': 'sum', 'NAV': 'sum', 'Total Value': 'sum'
    }).reset_index()
    v_stats['TVPI']  = v_stats['Total Value'] / v_stats['Paid-In']
    v_stats['DPI']   = v_stats['Distributed'] / v_stats['Paid-In']
    v_stats['IRR %'] = v_stats['Vintage'].apply(
    lambda v: calc_pooled_irr(df_final[df_final['Vintage'] == v])
    )
    
    s_stats = df_final.groupby('Strategy').agg({
    'Commitment': 'sum', 'Paid-In': 'sum', 'Unfunded': 'sum',
    'Distributed': 'sum', 'NAV': 'sum', 'Total Value': 'sum'
    }).reset_index()
    s_stats['TVPI']  = s_stats['Total Value'] / s_stats['Paid-In']
    s_stats['DPI']   = s_stats['Distributed'] / s_stats['Paid-In']
    s_stats['IRR %'] = s_stats['Strategy'].apply(
    lambda s: calc_pooled_irr(df_final[df_final['Strategy'] == s])
    )
    
    def calc_wav_duration(group_df):
    funds = group_df['Fund'].tolist()
    flows_list = []
    for fund in funds:
        f_meta  = df_char[df_char['Fund'] == fund].iloc[0]
        f_curr  = f_meta['Currency']
        f_flows = df_flows_raw[
            (df_flows_raw['Fund'] == fund) & (df_flows_raw['Date'] <= as_of_date_dt)
            & (df_flows_raw['Type'].str.contains('Call', case=False))
        ].copy()
        if f_flows.empty:
            continue
        f_flows['Amt_Rep'] = [
            abs(convert_amount(r['Amount'], f_curr, report_curr, fx_map.get(r['Date'].date(), fx_today)))
            for _, r in f_flows.iterrows()
        ]
        f_flows['Years'] = (as_of_date_dt - f_flows['Date']).dt.days / 365.25
        flows_list.append(f_flows[['Amt_Rep', 'Years']])
    if not flows_list:
        return 0
    agg     = pd.concat(flows_list, ignore_index=True)
    total_w = agg['Amt_Rep'].sum()
    if total_w == 0:
        return 0
    return (agg['Amt_Rep'] * agg['Years']).sum() / total_w
    
    s_stats['Duration (yrs)'] = s_stats['Strategy'].apply(
    lambda s: calc_wav_duration(df_final[df_final['Strategy'] == s])
    )
    _dur_total = calc_wav_duration(df_final)
    
    # ─────────────────────────────────────────────────────────────────────────
    # 8. PERFORMANCE GLOBAL POOLED (sin cambios)
    # ─────────────────────────────────────────────────────────────────────────
    t_comm = df_final[df_final['committed'] == True]['Commitment'].sum()
    t_paid = df_final['Paid-In'].sum()
    t_dist = df_final['Distributed'].sum()
    t_nav  = df_final['NAV'].sum()
    try:
    f_p_agg = pd.concat(all_flows_rep_global, ignore_index=True).groupby('Date')['Amt_Rep'].sum().reset_index()
    nav_date = pd.Timestamp(as_of_date_dt)
    if nav_date in f_p_agg['Date'].values:
        f_p_agg.loc[f_p_agg['Date'] == nav_date, 'Amt_Rep'] += float(t_nav)
        irr_dates   = f_p_agg['Date'].tolist()
        irr_amounts = f_p_agg['Amt_Rep'].tolist()
    else:
        irr_dates   = f_p_agg['Date'].tolist() + [nav_date]
        irr_amounts = f_p_agg['Amt_Rep'].tolist() + [float(t_nav)]
    g_irr = xirr(irr_dates, irr_amounts) * 100
    if g_irr < -99:
        g_irr = 0
    except:
    g_irr = 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # 9. TABS — contenido 100% original sin cambios
    # ─────────────────────────────────────────────────────────────────────────

    # ── Return context dict ───────────────────────────────────────────────────
    return {
        'report_curr':              report_curr,
        'as_of_date':               as_of_date,
        'as_of_date_dt':            as_of_date_dt,
        'fx_map':                   fx_map,
        'fx_today':                 fx_today,
        'curr_sym':                 curr_sym,
        'df_char':                  df_char,
        'df_char_filt':             df_char_filt,
        'df_final':                 df_final,
        'df_coinv':                 df_coinv,
        'df_flows_raw':             df_flows_raw,
        'all_flows_rep_global':     all_flows_rep_global,
        'g_irr':                    g_irr,
        's_stats':                  s_stats,
        'v_stats':                  v_stats,
        't_nav':                    t_nav,
        't_comm':                   t_comm,
        't_paid':                   t_paid,
        't_dist':                   t_dist,
        't_tv':                     t_dist + t_nav,
        'money_cols':               ['Commitment','Paid-In','Unfunded','Distributed','NAV','Total Value'],
        'calc_quarterly_evolutions': calc_quarterly_evolutions,
        'calc_pooled_irr':          calc_pooled_irr,
        'calc_wav_duration':        calc_wav_duration,
        '_dur_total':               _dur_total,
    }
