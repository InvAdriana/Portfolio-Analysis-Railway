import pandas as pd
import numpy as np
import streamlit as st
from pyxirr import xirr
from datetime import datetime, timedelta
import requests

@st.cache_data(ttl=3600)
def get_fx_map_institutional(start_date, end_date):
    FALLBACK = {"USD": 1.08, "GBP": 0.86}
    try:
        # Limitar end_date a hoy para evitar errores con fechas futuras
        today = datetime.today().date()
        end_capped = min(end_date.date() if hasattr(end_date,'date') else end_date, today)
        url = f"https://api.frankfurter.app/{start_date.strftime('%Y-%m-%d')}..{end_capped.strftime('%Y-%m-%d')}?to=USD,GBP"
        response = requests.get(url, timeout=15)
        data = response.json()
        rates_raw = data.get('rates', {})
        if not rates_raw:
            raise ValueError("Empty rates")
        fx_dict = {}
        for date_str, v in rates_raw.items():
            fx_dict[datetime.strptime(date_str, '%Y-%m-%d').date()] = {
                "USD": float(v.get("USD", FALLBACK["USD"])),
                "GBP": float(v.get("GBP", FALLBACK["GBP"])),
            }
        full_range = pd.date_range(start_date, end_date)
        clean_map = {}
        last_v = FALLBACK.copy()
        for d in full_range:
            d_d = d.date()
            if d_d in fx_dict:
                last_v = fx_dict[d_d]
            clean_map[d_d] = dict(last_v)
        return clean_map
    except:
        # Si la API falla, devolver mapa con tasas de fallback para todo el rango
        full_range = pd.date_range(start_date, end_date)
        return {d.date(): FALLBACK.copy() for d in full_range}


def convert_amount(amount, from_curr, to_curr, fx_day):
    if from_curr == to_curr:
        return float(amount)
    rates = {"EUR": 1.0, "USD": fx_day["USD"], "GBP": fx_day["GBP"]}
    amount_in_eur = float(amount) / rates[from_curr]
    return amount_in_eur * rates[to_curr]


# ─────────────────────────────────────────────────────────────────────────────
# 3. CARGA DE DATOS (sin cambios)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)  # refresca desde Drive cada 5 minutos
def load_data():
    xl = pd.ExcelFile(load_excel_from_drive("datos"))

    df_char = pd.read_excel(xl, sheet_name="Characteristics")
    df_char.columns = df_char.columns.str.strip()
    df_char['Fecha Commitment'] = pd.to_datetime(df_char['Fecha Commitment'], dayfirst=True)
    df_char['Vintage']    = pd.to_numeric(df_char['Vintage'], errors='coerce')
    df_char['Commitment'] = pd.to_numeric(df_char['Commitment'], errors='coerce')
    df_char['Currency']   = df_char['Currency'].astype(str).str.strip().str.upper()
    df_char['GP']         = df_char['GP'].astype(str).str.strip()
    df_char['Fund']       = df_char['Fund'].astype(str).str.strip()
    df_char['Strategy']   = df_char['Strategy'].astype(str).str.strip()
    df_char['Geography']  = df_char['Geography'].astype(str).str.strip() if 'Geography' in df_char.columns else 'Unknown'
    # Fecha 1er Call en Characteristics (fondos) — columna opcional
    col_cc = None
    for c in df_char.columns:
        c_clean = c.strip().lower().replace('°','').replace('º','').replace('  ',' ')
        if 'fecha' in c_clean and ('1' in c_clean or 'primer' in c_clean) and 'call' in c_clean:
            col_cc = c
            break
    if col_cc:
        df_char['Fecha 1er Call'] = pd.to_datetime(df_char[col_cc], dayfirst=True, errors='coerce')
    else:
        df_char['Fecha 1er Call'] = pd.NaT
    df_char['Fecha 1er Call'] = df_char['Fecha 1er Call'].fillna(df_char['Fecha Commitment'])
    df_char = df_char.dropna(subset=['Commitment', 'Vintage'])

    # ── Characteristics_CoInv (pestaña separada para co-inversiones) ──────────
    df_coinv = pd.DataFrame()
    if 'Characteristics_CoInv' in xl.sheet_names:
        df_coinv = pd.read_excel(xl, sheet_name="Characteristics_CoInv")
        df_coinv.columns = df_coinv.columns.str.strip()
        # Columnas base
        for col_dt in ['Fecha Commitment']:
            if col_dt in df_coinv.columns:
                df_coinv[col_dt] = pd.to_datetime(df_coinv[col_dt], dayfirst=True, errors='coerce')
        for col_num in ['Commitment', 'Vintage', 'UW TVPI', 'New TVPI']:
            if col_num in df_coinv.columns:
                df_coinv[col_num] = pd.to_numeric(df_coinv[col_num], errors='coerce')
        for col_dt2 in ['Fecha 1° Capital Call', 'UW Exit Date', 'New Exit Date']:
            if col_dt2 in df_coinv.columns:
                df_coinv[col_dt2] = pd.to_datetime(df_coinv[col_dt2], dayfirst=True, errors='coerce')
        for col_str in ['Fund', 'GP', 'Strategy', 'Currency', 'Geography']:
            if col_str in df_coinv.columns:
                df_coinv[col_str] = df_coinv[col_str].astype(str).str.strip()
        if 'Currency' in df_coinv.columns:
            df_coinv['Currency'] = df_coinv['Currency'].str.upper()
        if 'Strategy' not in df_coinv.columns:
            df_coinv['Strategy'] = 'Single Co-Inv'
        df_coinv = df_coinv.dropna(subset=['Commitment'])

        # ── CRÍTICO: agregar co-inversiones a df_char para que TODAS las
        # pestañas existentes (Status, Portfolio, IRR, etc.) sigan funcionando ──
        df_coinv_base = df_coinv.copy()

        # Fecha 1er Call
        if 'Fecha 1° Capital Call' in df_coinv_base.columns:
            df_coinv_base['Fecha 1er Call'] = df_coinv_base['Fecha 1° Capital Call']
        elif 'Fecha Commitment' in df_coinv_base.columns:
            df_coinv_base['Fecha 1er Call'] = df_coinv_base['Fecha Commitment']
        else:
            df_coinv_base['Fecha 1er Call'] = pd.NaT
        if 'Fecha Commitment' in df_coinv_base.columns:
            df_coinv_base['Fecha 1er Call'] = df_coinv_base['Fecha 1er Call'].fillna(
                df_coinv_base['Fecha Commitment'])

        # Vintage obligatorio para df_char — usar año de Fecha Commitment si falta
        if 'Vintage' not in df_coinv_base.columns or df_coinv_base['Vintage'].isna().all():
            if 'Fecha Commitment' in df_coinv_base.columns:
                df_coinv_base['Vintage'] = pd.to_datetime(
                    df_coinv_base['Fecha Commitment'], errors='coerce').dt.year
        else:
            df_coinv_base['Vintage'] = pd.to_numeric(df_coinv_base['Vintage'], errors='coerce')
            if 'Fecha Commitment' in df_coinv_base.columns:
                df_coinv_base['Vintage'] = df_coinv_base['Vintage'].fillna(
                    pd.to_datetime(df_coinv_base['Fecha Commitment'], errors='coerce').dt.year)

        if 'Geography' not in df_coinv_base.columns:
            df_coinv_base['Geography'] = 'Unknown'

        # Columnas mínimas para df_char
        cols_base = ['Fund','GP','Strategy','Currency','Vintage','Commitment',
                     'Fecha Commitment','Geography','Fecha 1er Call']
        coinv_for_char = df_coinv_base[[c for c in cols_base
                                        if c in df_coinv_base.columns]].copy()
        coinv_for_char = coinv_for_char.dropna(subset=['Commitment'])

        # Unir al df_char principal — evitar duplicados
        existing_funds = set(df_char['Fund'].tolist())
        coinv_new = coinv_for_char[~coinv_for_char['Fund'].isin(existing_funds)]
        if not coinv_new.empty:
            df_char = pd.concat([df_char, coinv_new], ignore_index=True)

    df_flows_raw = pd.read_excel(xl, sheet_name="Cashflows")
    df_flows_raw.columns = df_flows_raw.columns.str.strip()
    df_flows_raw['Date']   = pd.to_datetime(df_flows_raw['Date'], dayfirst=True)
    df_flows_raw['Amount'] = pd.to_numeric(df_flows_raw['Amount'], errors='coerce').fillna(0)
    df_flows_raw['Fund']   = df_flows_raw['Fund'].astype(str).str.strip()
    df_flows_raw['Type']   = df_flows_raw['Type'].astype(str).str.strip()
    df_flows_raw = df_flows_raw.dropna(subset=['Date'])

    # ── Validación de calidad de datos ───────────────────────────────────────
    # Capital Calls positivos (deberían ser negativos)
    bad_calls = df_flows_raw[
        df_flows_raw['Type'].str.contains('Call', case=False) &
        (df_flows_raw['Amount'] > 0)
    ][['Fund','Date','Type','Amount']].copy()

    # Distribuciones negativas (deberían ser positivas)
    bad_dists = df_flows_raw[
        df_flows_raw['Type'].str.contains('Dist', case=False) &
        (df_flows_raw['Amount'] < 0)
    ][['Fund','Date','Type','Amount']].copy()

    # Guardar en session_state para mostrar en la UI
    import streamlit as _st
    if not bad_calls.empty or not bad_dists.empty:
        _st.session_state['_data_quality_errors'] = {
            'bad_calls': bad_calls,
            'bad_dists': bad_dists,
        }
    else:
        _st.session_state['_data_quality_errors'] = None

    return df_char, df_flows_raw, df_coinv


# ─────────────────────────────────────────────────────────────────────────────
# 4. COMPUTE PORTFOLIO (sin cambios)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Calculando portfolio...")
def compute_portfolio(_df_char_filt, _df_flows_raw, report_curr, as_of_date_dt, _fx_map,
                      cache_key=None):  # cache_key sin _ para que Streamlit lo use como hash
    stats_list = []
    all_cf_list = []
    fx_today = _fx_map.get(as_of_date_dt.date(), {"USD": 1.08, "GBP": 0.86})

    for _, f_meta in _df_char_filt.iterrows():
        fund, f_curr = f_meta['Fund'], f_meta['Currency']
        f_flows = _df_flows_raw[
            (_df_flows_raw['Fund'] == fund) & (_df_flows_raw['Date'] <= as_of_date_dt)
        ].copy()

        # Si no hay flujos hasta la fecha de corte, saltar
        if f_flows.empty:
            continue

        f_flows['Amt_Rep'] = [
            convert_amount(r['Amount'], f_curr, report_curr, _fx_map.get(r['Date'].date(), fx_today))
            for _, r in f_flows.iterrows()
        ]
        calls_rep = abs(sum(f_flows[f_flows['Type'].str.contains('Call', case=False)]['Amt_Rep']))
        dists_rep = sum(f_flows[f_flows['Type'].str.contains('Dist', case=False)]['Amt_Rep'])
        nav_entries = f_flows[f_flows['Type'].str.contains('NAV', case=False)].sort_values('Date')
        if not nav_entries.empty:
            ln = nav_entries.iloc[-1]
            later_f = f_flows[f_flows['Date'] > ln['Date']]
            nav_loc = (float(ln['Amount'])
                       + abs(float(later_f[later_f['Type'].str.contains('Call', case=False)]['Amount'].sum()))
                       - float(later_f[later_f['Type'].str.contains('Dist', case=False)]['Amount'].sum()))
            nav_rep = convert_amount(nav_loc, f_curr, report_curr, fx_today)
            nav_period = f"{(ln['Date'].month - 1) // 3 + 1}Q{ln['Date'].strftime('%y')}"
        else:
            nav_rep, nav_period = calls_rep, "Cost"

        # Commitment solo si Fecha Commitment <= as_of_date_dt
        if f_meta['Fecha Commitment'] <= as_of_date_dt:
            fx_commit = _fx_map.get(f_meta['Fecha Commitment'].date(), fx_today)
            comm_rep = convert_amount(f_meta['Commitment'], f_curr, report_curr, fx_commit)
        else:
            comm_rep = 0  # No comprometido aún en la fecha de corte

        cf_df = f_flows[~f_flows['Type'].str.contains('NAV', case=False)][['Date', 'Amt_Rep']].copy()
        all_cf_list.append(cf_df)
        try:
            nav_date = pd.Timestamp(as_of_date_dt)
            cf_agg = cf_df.groupby('Date')['Amt_Rep'].sum().reset_index()
            if nav_date in cf_agg['Date'].values:
                cf_agg.loc[cf_agg['Date'] == nav_date, 'Amt_Rep'] += float(nav_rep)
                tir_rep = xirr(cf_agg['Date'].tolist(), cf_agg['Amt_Rep'].tolist()) * 100
            else:
                tir_rep = xirr(cf_agg['Date'].tolist() + [nav_date],
                               cf_agg['Amt_Rep'].tolist() + [float(nav_rep)]) * 100
        except:
            tir_rep = 0
        stats_list.append({
            "Fund": fund, "GP": f_meta['GP'], "Strategy": f_meta['Strategy'],
            "Vintage": f_meta['Vintage'], "Periodo NAV": nav_period,
            "Commitment": comm_rep, "Paid-In": calls_rep, "Unfunded": max(comm_rep - calls_rep, 0),
            "Distributed": dists_rep, "NAV": nav_rep, "Total Value": dists_rep + nav_rep,
            "IRR %": tir_rep,
            "TVPI": (dists_rep + nav_rep) / (calls_rep if calls_rep > 0 else 1),
            "DPI": dists_rep / (calls_rep if calls_rep > 0 else 1),
            "committed": f_meta['Fecha Commitment'] <= as_of_date_dt,  # flag para contar inversiones
        })
    return pd.DataFrame(stats_list), all_cf_list



@st.cache_data(show_spinner=False)
def _calc_quarterly_evolutions(calc_curr, _df_final, _df_flows_raw, _df_char,
                                as_of_date_dt, _fx_map, fx_today, _cache_key, _version="v4"):
    """Cálculo cacheado de evoluciones trimestrales IRR/TVPI/DPI/Rent."""
    from pyxirr import xirr as _xirr
    irr_ev_l, tvpi_ev_l, dpi_ev_l, ret_ev_l = [], [], [], []
    if _df_final.empty:
        return irr_ev_l, tvpi_ev_l, dpi_ev_l, ret_ev_l
    nav_flows = _df_flows_raw[_df_flows_raw['Type'].str.contains('NAV', case=False)]
    last_nav_date = nav_flows['Date'].max() if not nav_flows.empty else as_of_date_dt
    q_dates = pd.date_range(start=_df_flows_raw['Date'].min(), end=last_nav_date, freq='QE')

    for f_name in _df_final['Fund'].tolist():
        f_i, f_t, f_d, f_r = {'Fund': f_name}, {'Fund': f_name}, {'Fund': f_name}, {'Fund': f_name}
        f_fl_raw = _df_flows_raw[_df_flows_raw['Fund'] == f_name].copy()
        f_mt_rows = _df_char[_df_char['Fund'] == f_name]
        if f_mt_rows.empty: continue
        f_mt = f_mt_rows.iloc[0]
        f_curr_ind, p_n_rep = f_mt['Currency'], 0
        # Usar fecha del primer flujo real en vez de Fecha Commitment
        # (puede haber fondos con flows antes de la firma oficial)
        first_flow_date = f_fl_raw['Date'].min() if not f_fl_raw.empty else f_mt['Fecha Commitment']

        def cv(amt, fx_day, f_curr_ind=f_curr_ind):
            if calc_curr == "Local":
                return float(amt)
            return convert_amount(amt, f_curr_ind, calc_curr, fx_day)

        for q_d in q_dates:
            if first_flow_date > q_d:
                for d in [f_i, f_t, f_d, f_r]:
                    d[q_d.strftime('%d-%m-%Y')] = None
                continue
            q_fx = _fx_map.get(q_d.date(), fx_today)
            q_f  = f_fl_raw[f_fl_raw['Date'] <= q_d].copy()
            q_f['Amt_R'] = [
                cv(r['Amount'], _fx_map.get(r['Date'].date(), fx_today))
                for _, r in q_f.iterrows()
            ]
            q_nv_l = q_f[q_f['Type'].str.contains('NAV', case=False)].sort_values('Date')
            if not q_nv_l.empty:
                qn  = q_nv_l.iloc[-1]
                n_l = (float(qn['Amount'])
                       + abs(float(q_f[q_f['Date'] > qn['Date']][q_f['Type'].str.contains('Call', case=False)]['Amount'].sum()))
                       - float(q_f[q_f['Date'] > qn['Date']][q_f['Type'].str.contains('Dist', case=False)]['Amount'].sum()))
                n_r = cv(n_l, q_fx)
            else:
                n_r = abs(sum(q_f[q_f['Type'].str.contains('Call', case=False)]['Amt_R']))
            # Verificar si hay un NAV en este trimestre (no necesariamente en el último día)
            qs_check = q_d - pd.tseries.offsets.QuarterEnd()
            nav_this_q = q_f[
                q_f['Type'].str.contains('NAV', case=False) &
                (q_f['Date'] > qs_check) & (q_f['Date'] <= q_d)
            ]
            if not nav_this_q.empty:
                qs     = q_d - pd.tseries.offsets.QuarterEnd()
                cf_q   = f_fl_raw[(f_fl_raw['Date'] > qs) & (f_fl_raw['Date'] <= q_d)].copy()
                qc     = cv(abs(float(cf_q[cf_q['Type'].str.contains('Call', case=False)]['Amount'].sum())), q_fx)
                qd_val = cv(float(cf_q[cf_q['Type'].str.contains('Dist', case=False)]['Amount'].sum()), q_fx)
                if p_n_rep == 0:
                    # Primer trimestre activo: denominador = capital neto invertido (calls - dists)
                    denom = qc - qd_val
                else:
                    denom = p_n_rep - qd_val + qc
                if denom <= 0:
                    f_r[q_d.strftime('%d-%m-%Y')] = None
                else:
                    ret = ((n_r / denom) - 1) * 100
                    f_r[q_d.strftime('%d-%m-%Y')] = ret if -100 < ret < 500 else None
            else:
                f_r[q_d.strftime('%d-%m-%Y')] = None
            p_n_rep = n_r
            tqc = abs(sum(q_f[q_f['Type'].str.contains('Call', case=False)]['Amt_R']))
            tqd = sum(q_f[q_f['Type'].str.contains('Dist', case=False)]['Amt_R'])

            if not nav_this_q.empty:
                # Solo calcular IRR y TVPI si hay NAV en este trimestre
                f_t[q_d.strftime('%d-%m-%Y')] = (tqd + n_r) / (tqc if tqc > 0 else 1)
                f_d[q_d.strftime('%d-%m-%Y')] = tqd / (tqc if tqc > 0 else 1)
                try:
                    f_i[q_d.strftime('%d-%m-%Y')] = _xirr(
                        q_f[~q_f['Type'].str.contains('NAV', case=False)]['Date'].tolist() + [q_d],
                        q_f[~q_f['Type'].str.contains('NAV', case=False)]['Amt_R'].tolist() + [float(n_r)]
                    ) * 100
                except:
                    f_i[q_d.strftime('%d-%m-%Y')] = 0
            else:
                f_i[q_d.strftime('%d-%m-%Y')] = None
                f_t[q_d.strftime('%d-%m-%Y')] = None
                f_d[q_d.strftime('%d-%m-%Y')] = tqd / (tqc if tqc > 0 else 1)  # DPI sí se calcula siempre
        irr_ev_l.append(f_i); tvpi_ev_l.append(f_t)
        dpi_ev_l.append(f_d); ret_ev_l.append(f_r)
    return irr_ev_l, tvpi_ev_l, dpi_ev_l, ret_ev_l




@st.cache_data(show_spinner=False)
def _calc_pooled_irr(fund_list, nav_total, report_curr, as_of_date_dt,
                     _df_flows_raw, _df_char, _fx_map, fx_today):
    flows = []
    for fund in fund_list:
        f_meta_rows = _df_char[_df_char['Fund'] == fund]
        if f_meta_rows.empty: continue
        f_meta = f_meta_rows.iloc[0]
        f_curr = f_meta['Currency']
        f_flows = _df_flows_raw[
            (_df_flows_raw['Fund'] == fund) & (_df_flows_raw['Date'] <= as_of_date_dt)
        ].copy()
        f_flows['Amt_Rep'] = [
            convert_amount(r['Amount'], f_curr, report_curr, _fx_map.get(r['Date'].date(), fx_today))
            for _, r in f_flows.iterrows()
        ]
        cf = f_flows[~f_flows['Type'].str.contains('NAV', case=False)][['Date', 'Amt_Rep']].copy()
        flows.append(cf)
    if not flows:
        return 0
    agg = pd.concat(flows, ignore_index=True).groupby('Date')['Amt_Rep'].sum().reset_index()
    try:
        nav_date = pd.Timestamp(as_of_date_dt)
        if nav_date in agg['Date'].values:
            agg.loc[agg['Date'] == nav_date, 'Amt_Rep'] += nav_total
            irr_dates, irr_amounts = agg['Date'].tolist(), agg['Amt_Rep'].tolist()
        else:
            irr_dates   = agg['Date'].tolist() + [nav_date]
            irr_amounts = agg['Amt_Rep'].tolist() + [nav_total]
        irr = xirr(irr_dates, irr_amounts) * 100
        return irr if irr > -99 else 0
    except:
        return 0


try:
    # ─────────────────────────────────────────────────────────────────────────