import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from supabase import create_client
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="FinanceFlow Pro v3.7", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F7F9FC; }
    [data-testid='stSidebar'] { display: none; }
    .main { padding: 10px; }
    .metric-card {
        background: white; border-radius: 16px; padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #EDF2F7;
        text-align: center; height: 100%;
    }
    .metric-label { color: #718096; font-size: 12px; font-weight: 600; text-transform: uppercase; }
    .metric-value { color: #1A202C; font-size: 26px; font-weight: 800; margin-top: 5px; }
    .premium-bank-card {
        background: white; border-radius: 12px; padding: 15px;
        border-bottom: 3px solid #3B4CCA; box-shadow: 0 2px 8px rgba(0,0,0,0.03);
        margin-bottom: 10px; text-align: center;
    }
    .bank-title { font-size: 12px; color: #4A5568; font-weight: 600; text-transform: uppercase; }
    .bank-amount { font-size: 20px; color: #1A202C; font-weight: 700; }
    .section-title { font-size: 20px; font-weight: 700; color: #2D3748; margin: 20px 0 10px 0; }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

def get_all(table):
    res = supabase.table(table).select("*").execute()
    return pd.DataFrame(res.data)

# --- CARGA Y RECALCULO DE LIQUIDEZ EN TIEMPO REAL ---
acc_df_raw = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# Lógica para que la liquidez siempre sea real sumando transacciones
def calcular_saldos_reales(df_acc, df_tx):
    saldos = {row['id']: 0.0 for _, row in df_acc.iterrows()}
    name_to_id = {row['name']: row['id'] for _, row in df_acc.iterrows()}
    
    for _, t in df_tx.iterrows():
        # Afectar origen (H)
        if t['banco_h_id'] in saldos:
            saldos[t['banco_h_id']] += float(t['importe_f'])
        # Afectar destino (I) si es traspaso
        if t['tipo'] == 'Traspaso' and t['hacia_i'] in name_to_id:
            dest_id = name_to_id[t['hacia_i']]
            saldos[dest_id] += abs(float(t['importe_f']))
            
    df_acc['balance'] = df_acc['id'].map(saldos)
    return df_acc

acc_df = calcular_saldos_reales(acc_df_raw, tx_raw)

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Registro", "🗂️ Tabla Maestra", "⚙️ Ajustes"])

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    # 1. Filtro Temporal
    today = date.today()
    start_m = today.replace(day=1)
    st.markdown("<div class='section-title'>Análisis de Periodo</div>", unsafe_allow_html=True)
    d_range = st.date_input("Rango", [start_m, today], label_visibility="collapsed")
    
    if len(d_range) == 2 and not tx_raw.empty:
        tx_raw['fecha_dt'] = pd.to_datetime(tx_raw['fecha']).dt.date
        df_filt = tx_raw[(tx_raw['fecha_dt'] >= d_range[0]) & (tx_raw['fecha_dt'] <= d_range[1])].copy()
    else:
        df_filt = tx_raw.copy()

    # 2. KPIs
    gastos = df_filt[df_filt['tipo'] == 'Gasto'] if not df_filt.empty else pd.DataFrame()
    ingresos = df_filt[df_filt['tipo'] == 'Ingreso'] if not df_filt.empty else pd.DataFrame()
    
    g_j = gastos['importe_k'].sum() if not gastos.empty else 0
    g_f = gastos['importe_f'].sum() if not gastos.empty else 0
    i_t = ingresos['importe_f'].sum() if not ingresos.empty else 0
    comp = g_f - g_j
    liq_total = acc_df['balance'].sum()

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: st.markdown(f'<div class="metric-card"><div class="metric-label">Gasto Jorge (K)</div><div class="metric-value">{g_j:,.0f}€</div></div>', unsafe_allow_html=True)
    with k2: st.markdown(f'<div class="metric-card"><div class="metric-label">Compartido</div><div class="metric-value">{comp:,.0f}€</div></div>', unsafe_allow_html=True)
    with k3: st.markdown(f'<div class="metric-card"><div class="metric-label">Salida Caja (F)</div><div class="metric-value">{g_f:,.0f}€</div></div>', unsafe_allow_html=True)
    with k4: st.markdown(f'<div class="metric-card"><div class="metric-label">Ingresos</div><div class="metric-value" style="color:#10B981;">{i_t:,.0f}€</div></div>', unsafe_allow_html=True)
    with k5: st.markdown(f'<div class="metric-card" style="background:#3B4CCA;"><div class="metric-label" style="color:white; opacity:0.8;">Liquidez Real</div><div class="metric-value" style="color:white;">{liq_total:,.0f}€</div></div>', unsafe_allow_html=True)

    # 3. GRÁFICO CASCADA (INGRESOS IZQ -> GASTOS -> AHORRO)
    st.markdown("<div class='section-title'>Flujo de Caja Detallado (Jorge K)</div>", unsafe_allow_html=True)
    if not df_filt.empty:
        map_cat = dict(zip(cat_df['id'], cat_df['name']))
        df_filt['cat_name'] = df_filt['subconcepto_id'].map(map_cat)
        
        # Separar ingresos y gastos por categoría para trazabilidad
        df_filt['label'] = df_filt.apply(lambda x: f"{x['cat_name']} (+)" if x['importe_k'] > 0 else f"{x['cat_name']} (-)", axis=1)
        resumen = df_filt[df_filt['tipo'] != 'Traspaso'].groupby('label')['importe_k'].sum()
        
        # Ordenar: Positivos primero (Ingresos), luego negativos (Gastos)
        pos = resumen[resumen >= 0].sort_values(ascending=False)
        neg = resumen[resumen < 0].sort_values(ascending=False)
        final_res = pd.concat([pos, neg])
        
        fig_w = go.Figure(go.Waterfall(
            orientation = "v",
            measure = ["relative"] * len(final_res) + ["total"],
            x = list(final_res.index) + ["RESULTADO NETO"],
            y = list(final_res.values) + [0],
            textposition = "outside",
            text = [f"{v:,.0f}€" for v in final_res.values] + [f"{final_res.sum():,.0f}€"],
            increasing = {"marker":{"color":"#10B981"}},
            decreasing = {"marker":{"color":"#EF4444"}},
            totals = {"marker":{"color":"#3B4CCA"}}
        ))
        fig_w.update_layout(height=450, margin=dict(l=0,r=0,t=20,b=0))
        st.plotly_chart(fig_w, use_container_width=True)

    # 4. PATRIMONIO Y MONEY SITES
    st.markdown("<div class='section-title'>Composición del Patrimonio</div>", unsafe_allow_html=True)
    c_donut, c_cards = st.columns([1, 2])
    
    with c_donut:
        acc_with_money = acc_df[acc_df['balance'] != 0]
        if not acc_with_money.empty:
            fig_p = px.pie(acc_with_money, values='balance', names='name', hole=0.7, 
                           color_discrete_sequence=px.colors.qualitative.Prism)
            fig_p.update_layout(showlegend=True, height=350, margin=dict(l=0,r=0,t=0,b=0), legend=dict(orientation="h", y=-0.1))
            st.plotly_chart(fig_p, use_container_width=True)
        else: st.info("No hay saldos activos.")

    with c_cards:
        hide_zero = st.toggle("Ocultar cuentas vacías", value=False)
        disp_accs = acc_df if not hide_zero else acc_df[acc_df['balance'] != 0]
        cols_b = st.columns(3)
        for i, (_, row) in enumerate(disp_accs.sort_values('balance', ascending=False).iterrows()):
            with cols_b[i % 3]:
                st.markdown(f"""
                    <div class="premium-bank-card">
                        <div class="bank-title">{row['name']}</div>
                        <div class="bank-amount">{row['balance']:,.0f}€</div>
                    </div>
                """, unsafe_allow_html=True)

# ----------------- REGISTRO Y TABLA (ESTABLES) -----------------
with menu[1]:
    tipo = st.radio("Acción", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("¿Gasto compartido?")
    with st.form("form_v37"):
        c1, c2 = st.columns(2)
        f_r = c1.date_input("Fecha Real", date.today())
        concepto = st.text_input("Concepto")
        monto = st.number_input("Importe Total (F)", min_value=0.0, step=0.01)
        k_monto = st.number_input("Tu parte (K)", min_value=0.0, step=0.01) if es_comp else monto
        b_h = st.selectbox("Banco Origen", sorted(acc_df['name'].tolist()))
        if tipo == "Traspaso":
            b_i = st.selectbox("Banco Destino", [b for b in sorted(acc_df['name'].tolist()) if b != b_h])
            sub_id = cat_df[cat_df['name'] == 'Traspaso'].iloc[0]['id']
        else:
            b_i = tipo
            sub_n = st.selectbox("Categoría", sorted(cat_df['name'].tolist()))
            sub_id = cat_df[cat_df['name'] == sub_n].iloc[0]['id']
        if st.form_submit_button("GUARDAR"):
            f_f = -abs(monto) if tipo in ["Gasto", "Traspaso"] else abs(monto)
            k_f = -abs(k_monto) if tipo in ["Gasto", "Traspaso"] else abs(k_monto)
            if not es_comp: k_f = f_f
            supabase.table("transactions").insert({"fecha": str(f_r), "fecha_aj": str(f_r), "concepto": concepto, "subconcepto_id": sub_id, "importe_f": f_f, "importe_k": k_f, "banco_h_id": acc_df[acc_df['name']==b_h].iloc[0]['id'], "hacia_i": b_i, "tipo": tipo, "es_compartido": es_comp}).execute()
            st.rerun()

with menu[2]:
    if not tx_raw.empty:
        st.dataframe(tx_raw.sort_values('id', ascending=False), use_container_width=True)

with menu[3]:
    st.write("La liquidez ahora se calcula automáticamente al cargar la app.")
    if st.button("Limpiar Caché de la App"):
        st.cache_resource.clear()
        st.rerun()
