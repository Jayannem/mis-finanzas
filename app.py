import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="FinanceFlow Pro v2.2", layout="wide")
st.markdown("""
    <style>
    [data-testid='stSidebar']{display:none;} 
    .main{padding:10px;}
    .bank-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #28a745;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- FUNCIONES CARGA ---
def get_all(table):
    try:
        res = supabase.table(table).select("*").execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

def preparar_tabla_visible(df_tx, df_acc, df_cat):
    if df_tx.empty: return df_tx
    df = df_tx.copy()
    map_acc = dict(zip(df_acc['id'], df_acc['name'])) if not df_acc.empty else {}
    map_cat = dict(zip(df_cat['id'], df_cat['name'])) if not df_cat.empty else {}
    df['Banco (H)'] = df['banco_h_id'].map(map_acc)
    df['Subconcepto (E)'] = df['subconcepto_id'].map(map_cat)
    cols = ['id', 'fecha', 'fecha_aj', 'concepto', 'Subconcepto (E)', 'importe_f', 'importe_k', 'Banco (H)', 'hacia_i', 'tipo']
    return df[[c for c in cols if c in df.columns]]

# --- CARGA DATOS ---
acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Registro", "🗂️ Tabla Maestra", "📜 Borrado", "🛠️ Diagnóstico"])

# ----------------- 📊 DASHBOARD (VISTA MEJORADA) -----------------
with menu[0]:
    if not acc_df.empty:
        # 1. MÉTRICAS CABECERA
        total_cash = acc_df['balance'].sum()
        st.metric("PATRIMONIO TOTAL (CAJA)", f"{total_cash:,.2f} €")
        
        st.write("---")
        
        # 2. DESGLOSE DE LIQUIDEZ (TARJETAS)
        st.subheader("💳 Mis Cuentas (Liquidez)")
        # Mostramos solo cuentas con saldo o que sean 'liquid'
        liquid_df = acc_df[acc_df['type'] == 'liquid'].sort_values('balance', ascending=False)
        
        cols_bancos = st.columns(3)
        for i, (index, row) in enumerate(liquid_df.iterrows()):
            with cols_bancos[i % 3]:
                st.markdown(f"""
                    <div class="bank-card">
                        <div style="font-size: 0.8em; color: gray;">{row['name']}</div>
                        <div style="font-size: 1.2em; font-weight: bold;">{row['balance']:,.2f} €</div>
                    </div>
                """, unsafe_allow_html=True)

        st.write("---")
        
        # 3. ANÁLISIS DE GASTO
        c1, c2 = st.columns([1, 2])
        with c1:
            if not tx_raw.empty:
                g_jorge = tx_raw[tx_raw['tipo'] == 'Gasto']['importe_k'].sum()
                st.metric("TU GASTO REAL (NETO K)", f"{g_jorge:,.2f} €")
                
                g_compartido = tx_raw[tx_raw['tipo'] == 'Gasto']['importe_f'].sum() - g_jorge
                st.metric("COMPARTIDO/OTROS", f"{g_compartido:,.2f} €")
        
        with c2:
            if not tx_raw.empty:
                gastos_only = tx_raw[tx_raw['tipo'] == 'Gasto'].copy()
                if not gastos_only.empty:
                    df_g = gastos_only.merge(cat_df, left_on='subconcepto_id', right_on='id')
                    fig = px.pie(df_g, values=df_g['importe_k'].abs(), names='name', 
                                 title="Distribución Gasto Real Jorge", hole=0.4)
                    st.plotly_chart(fig, use_container_width=True)

# ----------------- 📝 REGISTRO (LÓGICA v2.1) -----------------
with menu[1]:
    tipo = st.radio("Tipo", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("Compartido")
    with st.form("form_v22"):
        c1, c2 = st.columns(2)
        f_r = c1.date_input("Fecha", datetime.now())
        concepto = st.text_input("Concepto")
        monto = st.number_input("Importe F (Caja)", min_value=0.0, step=0.01)
        k_monto = st.number_input("Tu parte K", min_value=0.0, step=0.01) if es_comp else monto
        
        bancos_list = sorted(acc_df['name'].tolist()) if not acc_df.empty else []
        b_h = st.selectbox("Origen (H)", bancos_list)
        
        if tipo == "Traspaso":
            b_i = st.selectbox("Destino (I)", [b for b in bancos_list if b != b_h])
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
            supabase.table("transactions").insert({
                "fecha": str(f_r), "concepto": concepto, "subconcepto_id": sub_id,
                "importe_f": f_f, "importe_k": k_f, "banco_h_id": h_id, "hacia_i": b_i, 
                "tipo": tipo, "es_compartido": es_comp
            }).execute()
            
            # Update Origen
            old_h = float(acc_df.loc[acc_df['name'] == b_h, 'balance'].values[0])
            supabase.table("accounts").update({"balance": old_h + f_f}).eq("id", h_id).execute()
            
            if tipo == "Traspaso":
                i_id = acc_df[acc_df['name'] == b_i].iloc[0]['id']
                old_i = float(acc_df.loc[acc_df['name'] == b_i, 'balance'].values[0])
                supabase.table("accounts").update({"balance": old_i + abs(monto)}).eq("id", i_id).execute()
            st.rerun()

# ----------------- 📜 BORRADO RECALIBRADO -----------------
with menu[3]:
    st.subheader("Borrar y Revertir Saldos")
    if not tx_raw.empty:
        id_del = st.number_input("ID a borrar", min_value=0, step=1)
        if st.button("BORRAR REGISTRO"):
            target = tx_raw[tx_raw['id'] == id_del]
            if not target.empty:
                row = target.iloc[0]
                f_val = float(row['importe_f'])
                # Revertir H
                cur_h = float(acc_df[acc_df['id'] == row['banco_h_id']]['balance'].values[0])
                supabase.table("accounts").update({"balance": cur_h - f_val}).eq("id", row['banco_h_id']).execute()
                # Revertir I si era Traspaso
                if row['tipo'] == 'Traspaso':
                    i_id = acc_df[acc_df['name'] == row['hacia_i']]['id'].values[0]
                    cur_i = float(acc_df[acc_df['id'] == i_id]['balance'].values[0])
                    supabase.table("accounts").update({"balance": cur_i - abs(f_val)}).eq("id", i_id).execute()
                
                supabase.table("transactions").delete().eq("id", id_del).execute()
                st.rerun()

# ----------------- 🗂️ TABLA MAESTRA -----------------
with menu[2]:
    if not tx_raw.empty:
        st.dataframe(preparar_tabla_visible(tx_raw, acc_df, cat_df).sort_values('id', ascending=False), use_container_width=True)

# ----------------- 🛠️ DIAGNÓSTICO -----------------
with menu[4]:
    if not tx_raw.empty:
        for _, b in acc_df.iterrows():
            if b['balance'] != 0:
                # Comprobación simple
                st.write(f"🔍 {b['name']}: Saldo actual {b['balance']}€")
