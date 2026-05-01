import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="FinanceFlow Pro v3.5", layout="wide")

st.markdown("""
    <style>
    [data-testid='stSidebar']{display:none;} 
    .main{padding:10px; background-color: #F7F9FC;}
    .metric-card {
        background: white; border-radius: 12px; padding: 15px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05); border: 1px solid #EDF2F7;
    }
    .metric-label { color: #718096; font-size: 11px; font-weight: 600; text-transform: uppercase; }
    .metric-value { color: #1A202C; font-size: 20px; font-weight: 700; }
    .bank-card-sm {
        background: #3B4CCA; color: white; border-radius: 10px; padding: 10px;
        margin-bottom: 8px; text-align: center;
    }
    .total-card-sm {
        background: #10B981; color: white; border-radius: 10px; padding: 10px;
        margin-bottom: 8px; text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- CARGA DE DATOS ---
def get_all(table):
    res = supabase.table(table).select("*").execute()
    return pd.DataFrame(res.data)

def preparar_tabla_visible(df_tx, df_acc, df_cat):
    if df_tx.empty: return df_tx
    df = df_tx.copy()
    map_acc = dict(zip(df_acc['id'], df_acc['name'])) if not df_acc.empty else {}
    map_cat = dict(zip(df_cat['id'], df_cat['name'])) if not df_cat.empty else {}
    df['Subconcepto (E)'] = df['subconcepto_id'].map(map_cat)
    df['Banco (H)'] = df['banco_h_id'].map(map_acc)
    cols = ['id', 'fecha', 'fecha_aj', 'concepto', 'Subconcepto (E)', 'importe_f', 'importe_k', 'Banco (H)', 'hacia_i', 'tipo']
    return df[[c for c in cols if c in df.columns]]

acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Registro", "🗂️ Tabla Maestra", "⚙️ Ajustes"])

# ----------------- 📊 DASHBOARD (CON GRÁFICO CASCADA) -----------------
with menu[0]:
    # 1. Filtro Temporal Inteligente (Mes Actual por defecto)
    today = date.today()
    start_of_month = today.replace(day=1)
    
    st.markdown("### 📅 Periodo de Análisis")
    d_range = st.date_input("Rango de fechas", [start_of_month, today])
    
    if len(d_range) == 2 and not tx_raw.empty:
        tx_raw['fecha_dt'] = pd.to_datetime(tx_raw['fecha']).dt.date
        df_filt = tx_raw[(tx_raw['fecha_dt'] >= d_range[0]) & (tx_raw['fecha_dt'] <= d_range[1])].copy()
    else:
        df_filt = tx_raw.copy()

    # 2. Cálculos KPIs
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

    st.write("---")

    # 3. GRÁFICO DE CASCADA (WATERFALL)
    st.markdown("#### 📉 Flujo de Caja y Ahorro (Jorge K)")
    if not df_filt.empty:
        # Traducir categorías para el gráfico
        map_cat = dict(zip(cat_df['id'], cat_df['name']))
        df_filt['cat_name'] = df_filt['subconcepto_id'].map(map_cat)
        
        # Agrupar ingresos y gastos Jorge
        inc_data = df_filt[df_filt['tipo'] == 'Ingreso'].groupby('cat_name')['importe_f'].sum()
        exp_data = df_filt[df_filt['tipo'] == 'Gasto'].groupby('cat_name')['importe_k'].sum()
        
        # Preparar listas para Plotly
        labels = list(inc_data.index) + list(exp_data.index) + ["AHORRO NETO"]
        values = list(inc_data.values) + list(exp_data.values) + [0] # 0 es placeholder para el total
        measures = ["relative"] * (len(inc_data) + len(exp_data)) + ["total"]
        
        fig = go.Figure(go.Waterfall(
            name = "Flujo", orientation = "v",
            measure = measures,
            x = labels,
            textposition = "outside",
            text = [f"{v:,.0f}€" for v in values[:-1]] + [f"{i_t + g_j:,.0f}€"],
            y = values,
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
            increasing = {"marker":{"color":"#10B981"}}, # Verde
            decreasing = {"marker":{"color":"#EF4444"}}, # Rojo
            totals = {"marker":{"color":"#3B4CCA"}}     # Azul
        ))

        fig.update_layout(height=400, margin=dict(l=10,r=10,t=20,b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos en este periodo.")

    st.write("---")

    # 4. TARJETAS DE BANCOS COMPACTAS
    st.markdown("#### 💳 Liquidez Actual")
    c_accs = st.columns(6)
    with c_accs[0]:
        st.markdown(f'<div class="total-card-sm"><div style="font-size:10px; opacity:0.8;">PATRIMONIO</div><div style="font-size:14px; font-weight:700;">{liq_real:,.0f}€</div></div>', unsafe_allow_html=True)
    
    sorted_accs = acc_df.sort_values('name')
    for i, (_, row) in enumerate(sorted_accs.iterrows()):
        with c_accs[(i + 1) % 6]:
            st.markdown(f'<div class="bank-card-sm"><div style="font-size:10px; opacity:0.8;">{row["name"]}</div><div style="font-size:14px; font-weight:700;">{row["balance"]:,.0f}€</div></div>', unsafe_allow_html=True)

# ----------------- REGISTRO, TABLA Y AJUSTES (ESTABLES) -----------------
with menu[1]:
    tipo = st.radio("Acción", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("¿Es compartido?")
    with st.form("form_v35"):
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
    if not tx_raw.empty:
        df_vis = preparar_tabla_visible(tx_raw, acc_df, cat_df)
        ids_del = st.multiselect("Borrado y Recalibración múltiple:", df_vis['id'].tolist())
        if st.button("🗑️ EJECUTAR"):
            for id_del in ids_del:
                row = tx_raw[tx_raw['id'] == id_del].iloc[0]
                cur_h = float(get_all("accounts").loc[acc_df['id'] == row['banco_h_id'], 'balance'].values[0])
                supabase.table("accounts").update({"balance": cur_h - float(row['importe_f'])}).eq("id", row['banco_h_id']).execute()
                if row['tipo'] == 'Traspaso':
                    i_id = acc_df[acc_df['name'] == row['hacia_i']]['id'].values[0]
                    cur_i = float(get_all("accounts").loc[acc_df['id'] == i_id, 'balance'].values[0])
                    supabase.table("accounts").update({"balance": cur_i - abs(float(row['importe_f']))}).eq("id", i_id).execute()
                supabase.table("transactions").delete().eq("id", id_del).execute()
            st.rerun()
        st.dataframe(df_vis.sort_values('id', ascending=False), use_container_width=True, hide_index=True)

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
