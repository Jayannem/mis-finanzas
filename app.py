import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from supabase import create_client
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="FinanceFlow Pro v3.6", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F7F9FC; }
    [data-testid='stSidebar'] { display: none; }
    .main { padding: 10px; }
    
    /* Métricas principales */
    .metric-card {
        background: white; border-radius: 16px; padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #EDF2F7;
        text-align: center;
    }
    .metric-label { color: #718096; font-size: 13px; font-weight: 600; text-transform: uppercase; }
    .metric-value { color: #1A202C; font-size: 28px; font-weight: 800; margin-top: 5px; }
    
    /* Tarjetas de Bancos Rediseñadas */
    .premium-bank-card {
        background: white; border-radius: 14px; padding: 20px;
        border-bottom: 4px solid #3B4CCA;
        box-shadow: 0 4px 10px rgba(0,0,0,0.03);
        margin-bottom: 15px; text-align: center;
    }
    .bank-title { font-size: 14px; color: #4A5568; font-weight: 600; margin-bottom: 10px; }
    .bank-amount { font-size: 24px; color: #1A202C; font-weight: 700; }
    
    /* Títulos de sección */
    .section-title { font-size: 22px; font-weight: 700; color: #2D3748; margin: 20px 0; }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

def get_all(table):
    res = supabase.table(table).select("*").execute()
    return pd.DataFrame(res.data)

# CARGA DE DATOS
acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Registro", "🗂️ Tabla Maestra", "⚙️ Ajustes"])

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    # 1. Filtro Temporal (Current Month)
    today = date.today()
    start_of_month = today.replace(day=1)
    
    st.markdown("<div class='section-title'>Análisis de Periodo</div>", unsafe_allow_html=True)
    d_range = st.date_input("Rango de fechas", [start_of_month, today], label_visibility="collapsed")
    
    if len(d_range) == 2 and not tx_raw.empty:
        tx_raw['fecha_dt'] = pd.to_datetime(tx_raw['fecha']).dt.date
        df_filt = tx_raw[(tx_raw['fecha_dt'] >= d_range[0]) & (tx_raw['fecha_dt'] <= d_range[1])].copy()
    else:
        df_filt = tx_raw.copy()

    # 2. KPIs Superiores
    gastos = df_filt[df_filt['tipo'] == 'Gasto'] if not df_filt.empty else pd.DataFrame()
    ingresos = df_filt[df_filt['tipo'] == 'Ingreso'] if not df_filt.empty else pd.DataFrame()
    
    g_j = gastos['importe_k'].sum() if not gastos.empty else 0
    g_f = gastos['importe_f'].sum() if not gastos.empty else 0
    comp = g_f - g_j
    i_t = ingresos['importe_f'].sum() if not ingresos.empty else 0
    liq_real = acc_df['balance'].sum() if not acc_df.empty else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: st.markdown(f'<div class="metric-card"><div class="metric-label">Gasto Jorge (K)</div><div class="metric-value">{g_j:,.0f}€</div></div>', unsafe_allow_html=True)
    with k2: st.markdown(f'<div class="metric-card"><div class="metric-label">Compartido</div><div class="metric-value">{comp:,.0f}€</div></div>', unsafe_allow_html=True)
    with k3: st.markdown(f'<div class="metric-card"><div class="metric-label">Salida Caja (F)</div><div class="metric-value">{g_f:,.0f}€</div></div>', unsafe_allow_html=True)
    with k4: st.markdown(f'<div class="metric-card"><div class="metric-label">Ingresos</div><div class="metric-value" style="color:#10B981;">{i_t:,.0f}€</div></div>', unsafe_allow_html=True)
    with k5: st.markdown(f'<div class="metric-card" style="background:#3B4CCA;"><div class="metric-label" style="color:white; opacity:0.8;">Liquidez Real</div><div class="metric-value" style="color:white;">{liq_real:,.0f}€</div></div>', unsafe_allow_html=True)

    # 3. GRÁFICO DE CASCADA CON NETEO POR CATEGORÍA
    st.markdown("<div class='section-title'>Flujo de Caja Neto por Categoría</div>", unsafe_allow_html=True)
    if not df_filt.empty:
        map_cat = dict(zip(cat_df['id'], cat_df['name']))
        df_filt['cat_name'] = df_filt['subconcepto_id'].map(map_cat)
        
        # LOGICA DE NETEO: Sumamos todos los importes K de la misma categoría
        net_data = df_filt.groupby('cat_name')['importe_k'].sum()
        
        labels = list(net_data.index) + ["RESULTADO NETO"]
        values = list(net_data.values) + [0]
        measures = ["relative"] * len(net_data) + ["total"]
        
        fig_w = go.Figure(go.Waterfall(
            orientation = "v",
            measure = measures,
            x = labels,
            y = values,
            textposition = "outside",
            text = [f"{v:,.0f}€" for v in values[:-1]] + [f"{net_data.sum():,.0f}€"],
            increasing = {"marker":{"color":"#10B981"}},
            decreasing = {"marker":{"color":"#EF4444"}},
            totals = {"marker":{"color":"#3B4CCA"}}
        ))
        fig_w.update_layout(height=450, margin=dict(l=0,r=0,t=20,b=0))
        st.plotly_chart(fig_w, use_container_width=True)

    # 4. SECCIÓN DE LIQUIDEZ PREMIUM
    st.markdown("<div class='section-title'>Patrimonio y Money Sites</div>", unsafe_allow_html=True)
    
    c_donut, c_cards = st.columns([1, 2])
    
    with c_donut:
        # Gráfico circular de composición
        fig_p = px.pie(acc_df[acc_df['balance'] != 0], values='balance', names='name', 
                       hole=0.6, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_p.update_layout(showlegend=True, height=350, margin=dict(l=0,r=0,t=0,b=0),
                            legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_p, use_container_width=True)

    with c_cards:
        hide_zero = st.toggle("Ocultar cuentas a 0€", value=False)
        display_accs = acc_df if not hide_zero else acc_df[acc_df['balance'] != 0]
        
        cols_b = st.columns(3)
        for i, (_, row) in enumerate(display_accs.sort_values('balance', ascending=False).iterrows()):
            with cols_b[i % 3]:
                st.markdown(f"""
                    <div class="premium-bank-card">
                        <div class="bank-title">{row['name']}</div>
                        <div class="bank-amount">{row['balance']:,.0f}€</div>
                    </div>
                """, unsafe_allow_html=True)

# ----------------- REGISTRO Y TABLA (MANTENIENDO v3.5) -----------------
with menu[1]:
    tipo = st.radio("Acción", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("¿Es compartido?")
    with st.form("form_v36"):
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
            st.rerun()

with menu[2]:
    st.dataframe(tx_raw.sort_values('id', ascending=False), use_container_width=True)

with menu[3]:
    if st.button("🔄 RECONSTRUIR SALDOS"):
        s_fix = {row['id']: 0.0 for _, row in acc_df.iterrows()}
        for _, t in tx_raw.iterrows():
            s_fix[t['banco_h_id']] += float(t['importe_f'])
            if t['tipo'] == 'Traspaso':
                tid = acc_df[acc_df['name'] == t['hacia_i']]['id'].values[0]
                s_fix[tid] += abs(float(t['importe_f']))
        for bid, val in s_fix.items():
            supabase.table("accounts").update({"balance": val}).eq("id", bid).execute()
        st.rerun()
