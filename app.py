import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="FinanceFlow Pro v3.4", layout="wide")

# Estilo Stitch sutil
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
    df['Banco (H)'] = df['banco_h_id'].map(map_acc)
    df['Subconcepto (E)'] = df['subconcepto_id'].map(map_cat)
    cols = ['id', 'fecha', 'fecha_aj', 'concepto', 'Subconcepto (E)', 'importe_f', 'importe_k', 'Banco (H)', 'hacia_i', 'tipo']
    return df[[c for c in cols if c in df.columns]]

# CARGA INICIAL
acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Registro", "🗂️ Tabla Maestra", "⚙️ Ajustes"])

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    # 1. Filtro Temporal (Current Month por defecto)
    today = date.today()
    start_m = date(today.year, today.month, 1)
    d_range = st.date_input("Periodo (Mes Actual)", [start_m, today])
    
    if len(d_range) == 2 and not tx_raw.empty:
        tx_raw['fecha_dt'] = pd.to_datetime(tx_raw['fecha']).dt.date
        df_filt = tx_raw[(tx_raw['fecha_dt'] >= d_range[0]) & (tx_raw['fecha_dt'] <= d_range[1])].copy()
    else:
        df_filt = tx_raw.copy()

    # 2. KPIs (Tu orden exacto)
    gastos = df_filt[df_filt['tipo'] == 'Gasto'] if not df_filt.empty else pd.DataFrame()
    ingresos = df_filt[df_filt['tipo'] == 'Ingreso'] if not df_filt.empty else pd.DataFrame()
    
    g_j = gastos['importe_k'].sum() if not gastos.empty else 0
    g_f = gastos['importe_f'].sum() if not gastos.empty else 0
    comp = g_f - g_j
    i_t = ingresos['importe_f'].sum() if not ingresos.empty else 0
    liq_real = acc_df['balance'].sum() if not acc_df.empty else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: st.markdown(f'<div class="metric-card"><div class="metric-label">Gasto Jorge</div><div class="metric-value">{g_j:,.0f}€</div></div>', unsafe_allow_html=True)
    with k2: st.markdown(f'<div class="metric-card"><div class="metric-label">Compartido</div><div class="metric-value">{comp:,.0f}€</div></div>', unsafe_allow_html=True)
    with k3: st.markdown(f'<div class="metric-card"><div class="metric-label">Salida Caja</div><div class="metric-value">{g_f:,.0f}€</div></div>', unsafe_allow_html=True)
    with k4: st.markdown(f'<div class="metric-card"><div class="metric-label">Ingresos</div><div class="metric-value" style="color:#10B981;">{i_t:,.0f}€</div></div>', unsafe_allow_html=True)
    with k5: st.markdown(f'<div class="metric-card" style="background:#3B4CCA;"><div class="metric-label" style="color:white; opacity:0.8;">Liquidez Real</div><div class="metric-value" style="color:white;">{liq_real:,.0f}€</div></div>', unsafe_allow_html=True)

    st.write("---")

    # 3. Gráficos Comparativos
    cg, ci = st.columns(2)
    with cg:
        st.markdown("#### 💸 Gastos Jorge K por Categoría")
        if not gastos.empty:
            df_g_plot = gastos.merge(cat_df, left_on='subconcepto_id', right_on='id')
            res_g = df_g_plot.groupby('name')['importe_k'].sum().abs().reset_index()
            fig_g = px.bar(res_g, x='name', y='importe_k', color_discrete_sequence=['#EF4444'])
            fig_g.update_layout(height=250, margin=dict(l=0,r=0,t=0,b=0), xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig_g, use_container_width=True)

    with ci:
        st.markdown("#### 💰 Ingresos por Categoría")
        if not ingresos.empty:
            df_i_plot = ingresos.merge(cat_df, left_on='subconcepto_id', right_on='id')
            res_i = df_i_plot.groupby('name')['importe_f'].sum().reset_index()
            fig_i = px.bar(res_i, x='name', y='importe_f', color_discrete_sequence=['#10B981'])
            fig_i.update_layout(height=250, margin=dict(l=0,r=0,t=0,b=0), xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig_i, use_container_width=True)

    st.write("---")

    # 4. Tarjetas de Bancos
    st.markdown("#### 💳 Liquidez por Cuenta")
    c_accs = st.columns(6)
    with c_accs[0]:
        st.markdown(f'<div class="total-card-sm"><div style="font-size:10px; opacity:0.8;">TOTAL</div><div style="font-size:14px; font-weight:700;">{liq_real:,.0f}€</div></div>', unsafe_allow_html=True)
    
    sorted_accs = acc_df.sort_values('name')
    for i, (_, row) in enumerate(sorted_accs.iterrows()):
        with c_accs[(i + 1) % 6]:
            st.markdown(f'<div class="bank-card-sm"><div style="font-size:10px; opacity:0.8;">{row["name"]}</div><div style="font-size:14px; font-weight:700;">{row["balance"]:,.0f}€</div></div>', unsafe_allow_html=True)

# ----------------- 📝 REGISTRO -----------------
with menu[1]:
    tipo = st.radio("Acción", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("¿Es compartido?")
    with st.form("form_v34"):
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

        if st.form_submit_button("GUARDAR REGISTRO"):
            f_f = -abs(monto) if tipo in ["Gasto", "Traspaso"] else abs(monto)
            k_f = -abs(k_monto) if tipo in ["Gasto", "Traspaso"] else abs(k_monto)
            if not es_comp: k_f = f_f
            h_id = acc_df[acc_df['name'] == b_h].iloc[0]['id']
            supabase.table("transactions").insert({"fecha": str(f_r), "fecha_aj": str(f_r), "concepto": concepto, "subconcepto_id": sub_id, "importe_f": f_f, "importe_k": k_f, "banco_h_id": h_id, "hacia_i": b_i, "tipo": tipo, "es_compartido": es_comp}).execute()
            st.rerun()

# ----------------- 🗂️ TABLA MAESTRA (BORRADO RESTAURADO) -----------------
with menu[2]:
    if not tx_raw.empty:
        ids_del = st.multiselect("Seleccionar IDs para borrar y recalibrar:", tx_raw['id'].sort_values(ascending=False).tolist())
        if st.button("🗑️ EJECUTAR BORRADO SELECCIONADOS"):
            for id_del in ids_del:
                row = tx_raw[tx_raw['id'] == id_del].iloc[0]
                # Lógica de recalibración revertida
                cur_h = float(get_all("accounts").loc[acc_df['id'] == row['banco_h_id'], 'balance'].values[0])
                supabase.table("accounts").update({"balance": cur_h - float(row['importe_f'])}).eq("id", row['banco_h_id']).execute()
                if row['tipo'] == 'Traspaso':
                    i_id = acc_df[acc_df['name'] == row['hacia_i']]['id'].values[0]
                    cur_i = float(get_all("accounts").loc[acc_df['id'] == i_id, 'balance'].values[0])
                    supabase.table("accounts").update({"balance": cur_i - abs(float(row['importe_f']))}).eq("id", i_id).execute()
                supabase.table("transactions").delete().eq("id", id_del).execute()
            st.rerun()
        st.dataframe(preparar_tabla_visible(tx_raw, acc_df, cat_df).sort_values('id', ascending=False), use_container_width=True, hide_index=True)

# ----------------- ⚙️ AJUSTES -----------------
with menu[3]:
    if st.button("🔄 SINCRONIZAR SALDOS (Fix BBVA/Liquidez)"):
        s_fix = {row['id']: 0.0 for _, row in acc_df.iterrows()}
        for _, t in tx_raw.iterrows():
            s_fix[t['banco_h_id']] += float(t['importe_f'])
            if t['tipo'] == 'Traspaso':
                tid = acc_df[acc_df['name'] == t['hacia_i']]['id'].values[0]
                s_fix[tid] += abs(float(t['importe_f']))
        for bid, val in s_fix.items():
            supabase.table("accounts").update({"balance": val}).eq("id", bid).execute()
        st.success("Sincronización completada.")
        st.rerun()
