import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, date

# --- CONFIGURACIÓN ESTÉTICA (STITCH THEME) ---
st.set_page_config(page_title="FinanceFlow Pro", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F7F9FC; }
    [data-testid='stSidebar'] { display: none; }
    .main { padding: 10px; }
    .metric-card {
        background: white; border-radius: 16px; padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #EDF2F7;
        height: 100%;
    }
    .metric-label { color: #718096; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { color: #1A202C; font-size: 24px; font-weight: 700; margin-top: 4px; }
    .bank-card {
        background: #3B4CCA; color: white; border-radius: 16px; padding: 15px;
        min-height: 80px; display: flex; flex-direction: column; justify-content: center;
        box-shadow: 0 8px 15px rgba(59, 76, 202, 0.2); margin-bottom: 10px;
    }
    .bank-name { font-size: 12px; opacity: 0.8; text-transform: uppercase; }
    .bank-balance { font-size: 18px; font-weight: 700; }
    .activity-item {
        background: white; border-radius: 12px; padding: 10px;
        margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center;
        border-bottom: 1px solid #F0F4F8;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

def get_all(table):
    res = supabase.table(table).select("*").execute()
    return pd.DataFrame(res.data)

# CARGA DATOS
acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Registro", "🗂️ Tabla Maestra", "⚙️ Ajustes"])

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    st.markdown("<h2 style='margin-bottom:10px;'>Overview</h2>", unsafe_allow_html=True)
    
    # Filtro Temporal
    start_m, end_m = date(2026, 4, 1), date(2026, 4, 30)
    d_range = st.date_input("Periodo seleccionado", [start_m, end_m])
    
    if len(d_range) == 2 and not tx_raw.empty:
        tx_raw['fecha_dt'] = pd.to_datetime(tx_raw['fecha']).dt.date
        df_filt = tx_raw[(tx_raw['fecha_dt'] >= d_range[0]) & (tx_raw['fecha_dt'] <= d_range[1])].copy()
    else:
        df_filt = tx_raw.copy()

    # KPIs (Lógica Jorge)
    gastos = df_filt[df_filt['tipo'] == 'Gasto'] if not df_filt.empty else pd.DataFrame()
    ingresos = df_filt[df_filt['tipo'] == 'Ingreso'] if not df_filt.empty else pd.DataFrame()
    
    g_j = gastos['importe_k'].sum() if not gastos.empty else 0
    g_f = gastos['importe_f'].sum() if not gastos.empty else 0
    i_t = ingresos['importe_f'].sum() if not ingresos.empty else 0
    comp = g_f - g_j
    liq = acc_df['balance'].sum() if not acc_df.empty else 0

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1: st.markdown(f'<div class="metric-card"><div class="metric-label">Jorge K</div><div class="metric-value">{g_j:,.0f}€</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-card"><div class="metric-label">Compartido</div><div class="metric-value">{comp:,.0f}€</div></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-card"><div class="metric-label">Salida Caja</div><div class="metric-value">{g_f:,.0f}€</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="metric-card"><div class="metric-label">Ingresos</div><div class="metric-value" style="color:#10B981;">{i_t:,.0f}€</div></div>', unsafe_allow_html=True)
    with m5: st.markdown(f'<div class="metric-card" style="background:#3B4CCA; border:none;"><div class="metric-label" style="color:white; opacity:0.7;">Liquidez</div><div class="metric-value" style="color:white;">{liq:,.0f}€</div></div>', unsafe_allow_html=True)

    # Gráfico (Financial Flows) - FIX ERROR 105
    st.write("")
    st.markdown("### Financial Flows")
    if not df_filt.empty:
        all_dates = pd.date_range(start=d_range[0], end=d_range[1]).date
        plot_df = pd.DataFrame(index=all_dates)
        
        income_daily = df_filt[df_filt['tipo']=='Ingreso'].groupby('fecha_dt')['importe_f'].sum()
        # Fix abs() error: sumamos primero, luego abs
        jorge_daily = df_filt[df_filt['tipo']=='Gasto'].groupby('fecha_dt')['importe_k'].sum().abs()
        
        plot_df['income'] = income_daily
        plot_df['jorge'] = jorge_daily
        plot_df = plot_df.fillna(0).cumsum()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['income'], name='Ingresos', line=dict(color='#10B981', width=3, shape='spline')))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['jorge'], name='Gasto Jorge', line=dict(color='#3B4CCA', width=3, shape='spline')))
        fig.update_layout(height=250, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

    # Cuentas y Actividad
    c_left, c_right = st.columns([2, 1])
    with c_left:
        st.markdown("### Money Sites")
        sorted_accs = acc_df.sort_values('name')
        cols_b = st.columns(3)
        for i, (_, row) in enumerate(sorted_accs.iterrows()):
            with cols_b[i % 3]:
                st.markdown(f'<div class="bank-card"><div class="bank-name">{row["name"]}</div><div class="bank-balance">{row["balance"]:,.0f} €</div></div>', unsafe_allow_html=True)

    with c_right:
        st.markdown("### Recent Activity")
        if not tx_raw.empty:
            for _, row in tx_raw.sort_values('id', ascending=False).head(6).iterrows():
                color = "#EF4444" if row['importe_f'] < 0 else "#10B981"
                st.markdown(f'<div class="activity-item"><div><div style="font-weight:600; font-size:13px;">{row["concepto"]}</div><div style="font-size:10px; color:gray;">{row["fecha"]}</div></div><div style="font-weight:700; color:{color}; font-size:14px;">{row["importe_f"]:,.0f}€</div></div>', unsafe_allow_html=True)

# ----------------- 📝 REGISTRO -----------------
with menu[1]:
    tipo = st.radio("Acción", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("Compartido")
    with st.form("form_v32"):
        c1, c2 = st.columns(2)
        f_r = c1.date_input("Fecha Real", date.today())
        concepto = st.text_input("Concepto")
        monto = st.number_input("Importe Total (F)", min_value=0.0, step=0.01)
        k_monto = st.number_input("Tu parte (K)", min_value=0.0, step=0.01) if es_comp else monto
        b_h = st.selectbox("Desde Banco", sorted(acc_df['name'].tolist()))
        if tipo == "Traspaso":
            b_i = st.selectbox("Hacia Banco", [b for b in sorted(acc_df['name'].tolist()) if b != b_h])
            sub_id = cat_df[cat_df['name'] == 'Traspaso'].iloc[0]['id']
        else:
            b_i = tipo
            sub_n = st.selectbox("Subconcepto", sorted(cat_df['name'].tolist()))
            sub_id = cat_df[cat_df['name'] == sub_n].iloc[0]['id']

        if st.form_submit_button("GUARDAR"):
            f_f = -abs(monto) if tipo in ["Gasto", "Traspaso"] else abs(monto)
            k_f = -abs(k_monto) if tipo in ["Gasto", "Traspaso"] else abs(k_monto)
            if not es_comp: k_f = f_f
            h_id = acc_df[acc_df['name'] == b_h].iloc[0]['id']
            supabase.table("transactions").insert({"fecha": str(f_r), "fecha_aj": str(f_r), "concepto": concepto, "subconcepto_id": sub_id, "importe_f": f_f, "importe_k": k_f, "banco_h_id": h_id, "hacia_i": b_i, "tipo": tipo, "es_compartido": es_comp}).execute()
            st.rerun() # Recargamos para que el sincronizador haga su magia si lo pulsas

# ----------------- 🗂️ TABLA MAESTRA -----------------
with menu[2]:
    if not tx_raw.empty:
        st.dataframe(tx_raw.sort_values('id', ascending=False), use_container_width=True)

# ----------------- ⚙️ AJUSTES (Sincronización Atómica) -----------------
with menu[3]:
    st.header("Mantenimiento")
    if st.button("🔄 RECONSTRUIR SALDOS (Fix Total)"):
        # 1. Reset
        s_fix = {row['id']: 0.0 for _, row in acc_df.iterrows()}
        # 2. Recalcular
        for _, t in tx_raw.iterrows():
            f = float(t['importe_f'])
            s_fix[t['banco_h_id']] += f
            if t['tipo'] == 'Traspaso':
                try:
                    tid = acc_df[acc_df['name'] == t['hacia_i']]['id'].values[0]
                    s_fix[tid] += abs(f)
                except: pass
        # 3. Subir
        for bid, val in s_fix.items():
            supabase.table("accounts").update({"balance": val}).eq("id", bid).execute()
        st.success("Saldos reconstruidos. ¡BBVA y Liquidez ahora son correctos!")
        st.rerun()
