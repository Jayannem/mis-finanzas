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
    
    /* Tarjetas de Métricas */
    .metric-card {
        background: white; border-radius: 16px; padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #EDF2F7;
    }
    .metric-label { color: #718096; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { color: #1A202C; font-size: 24px; font-weight: 700; margin-top: 4px; }
    
    /* Tarjetas de Bancos */
    .bank-card {
        background: #3B4CCA; color: white; border-radius: 16px; padding: 15px;
        min-height: 100px; display: flex; flex-direction: column; justify-content: space-between;
        box-shadow: 0 8px 15px rgba(59, 76, 202, 0.2);
    }
    .bank-name { font-size: 14px; opacity: 0.8; }
    .bank-balance { font-size: 20px; font-weight: 700; }

    /* Feed de Actividad */
    .activity-item {
        background: white; border-radius: 12px; padding: 12px;
        margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;
        border-bottom: 1px solid #F0F4F8;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN & DATOS ---
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

def get_all(table):
    res = supabase.table(table).select("*").execute()
    return pd.DataFrame(res.data)

# CARGA GLOBAL
acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Registro", "🗂️ Tabla Maestra", "⚙️ Ajustes"])

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    # Header
    st.markdown("<h2 style='margin-bottom:0;'>Overview</h2>", unsafe_allow_html=True)
    
    # Filtro Temporal
    start_m = date(2026, 4, 1)
    end_m = date(2026, 4, 30)
    d_range = st.date_input("Periodo", [start_m, end_m], label_visibility="collapsed")
    
    if len(d_range) == 2 and not tx_raw.empty:
        tx_raw['fecha_dt'] = pd.to_datetime(tx_raw['fecha']).dt.date
        df_filt = tx_raw[(tx_raw['fecha_dt'] >= d_range[0]) & (tx_raw['fecha_dt'] <= d_range[1])].copy()
    else:
        df_filt = tx_raw.copy()

    # KPIs Superiores
    gastos = df_filt[df_filt['tipo'] == 'Gasto']
    ingresos = df_filt[df_filt['tipo'] == 'Ingreso']
    
    g_j = gastos['importe_k'].sum()
    g_f = gastos['importe_f'].sum()
    i_t = ingresos['importe_f'].sum()
    comp = g_f - g_j
    liq = acc_df['balance'].sum()

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1: st.markdown(f'<div class="metric-card"><div class="metric-label">Jorge K</div><div class="metric-value">{g_j:,.0f}€</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-card"><div class="metric-label">Compartido</div><div class="metric-value">{comp:,.0f}€</div></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-card"><div class="metric-label">Salida Caja</div><div class="metric-value">{g_f:,.0f}€</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="metric-card"><div class="metric-label">Ingresos</div><div class="metric-value" style="color:#10B981;">{i_t:,.0f}€</div></div>', unsafe_allow_html=True)
    with m5: st.markdown(f'<div class="metric-card" style="background:#3B4CCA; border:none;"><div class="metric-label" style="color:white; opacity:0.7;">Liquidez</div><div class="metric-value" style="color:white;">{liq:,.0f}€</div></div>', unsafe_allow_html=True)

    # Gráfico de Flujos (Spline Chart)
    st.write("")
    st.markdown("### Financial Flows")
    if not df_filt.empty:
        df_filt = df_filt.sort_values('fecha_dt')
        # Acumulados para el gráfico
        df_filt['cum_income'] = df_filt[df_filt['tipo']=='Ingreso']['importe_f'].cumsum().fillna(method='ffill')
        df_filt['cum_jorge'] = df_filt[df_filt['tipo']=='Gasto']['importe_k'].abs().cumsum().fillna(method='ffill')
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_filt['fecha'], y=df_filt['cum_income'], name='Income', line=dict(color='#10B981', width=3, shape='spline')))
        fig.add_trace(go.Scatter(x=df_filt['fecha'], y=df_filt['cum_jorge'], name='Neto Jorge', line=dict(color='#3B4CCA', width=3, shape='spline')))
        fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

    # Bancos y Actividad
    c_left, c_right = st.columns([2, 1])
    
    with c_left:
        st.markdown("### Money Sites")
        sorted_accs = acc_df.sort_values('name')
        cols_b = st.columns(3)
        for i, (_, row) in enumerate(sorted_accs.iterrows()):
            with cols_b[i % 3]:
                st.markdown(f'<div class="bank-card"><div class="bank-name">{row["name"]}</div><div class="bank-balance">{row["balance"]:,.2f} €</div></div>', unsafe_allow_html=True)

    with c_right:
        st.markdown("### Recent Activity")
        if not df_filt.empty:
            for _, row in df_filt.sort_values('id', ascending=False).head(5).iterrows():
                color = "#EF4444" if row['importe_f'] < 0 else "#10B981"
                st.markdown(f"""
                    <div class="activity-item">
                        <div>
                            <div style="font-weight:600; font-size:14px;">{row['concepto']}</div>
                            <div style="font-size:11px; color:gray;">{row['fecha']}</div>
                        </div>
                        <div style="font-weight:700; color:{color};">{row['importe_f']:,.2f}€</div>
                    </div>
                """, unsafe_allow_html=True)

# ----------------- 📝 REGISTRO (SIN CAMBIOS EN LÓGICA) -----------------
with menu[1]:
    tipo = st.radio("Acción", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("¿Es compartido?")
    with st.form("form_v3"):
        c1, c2 = st.columns(2)
        f_r = c1.date_input("Fecha", date.today())
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
            # Update directo
            old_h = float(acc_df.loc[acc_df['name'] == b_h, 'balance'].values[0])
            supabase.table("accounts").update({"balance": old_h + f_f}).eq("id", h_id).execute()
            if tipo == "Traspaso":
                i_id = acc_df[acc_df['name'] == b_i].iloc[0]['id']
                old_i = float(acc_df.loc[acc_df['name'] == b_i, 'balance'].values[0])
                supabase.table("accounts").update({"balance": old_i + abs(monto)}).eq("id", i_id).execute()
            st.rerun()

# ----------------- 🗂️ TABLA & AJUSTES (MANTENIENDO v2.8) -----------------
with menu[2]:
    st.dataframe(df_filt.sort_values('id', ascending=False), use_container_width=True)

with menu[3]:
    if st.button("🔄 SINCRONIZAR SALDOS"):
        s_fix = {row['id']: 0.0 for _, row in acc_df.iterrows()}
        for _, t in tx_raw.iterrows():
            s_fix[t['banco_h_id']] += float(t['importe_f'])
            if t['tipo'] == 'Traspaso':
                tid = acc_df[acc_df['name'] == t['hacia_i']]['id'].values[0]
                s_fix[tid] += abs(float(t['importe_f']))
        for bid, val in s_fix.items():
            supabase.table("accounts").update({"balance": val}).eq("id", bid).execute()
        st.rerun()
