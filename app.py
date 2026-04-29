import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="FinanceFlow Pro v2.0", layout="wide")
st.markdown("<style>[data-testid='stSidebar']{display:none;} .main{padding:10px;}</style>", unsafe_allow_html=True)

# --- CONEXIÓN ---
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- CARGA DE DATOS ---
def get_all(table):
    try:
        res = supabase.table(table).select("*").execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Nuevo Registro", "🗂️ Tabla Maestra", "📜 Historial", "🛠️ Diagnóstico", "⚙️ Ajustes"])

# ----------------- 📝 NUEVO REGISTRO -----------------
with menu[1]:
    st.subheader("Entrada de Datos")
    tipo = st.radio("Tipo de Movimiento", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("¿Es gasto compartido?")

    with st.form("form_final"):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha Real", datetime.now())
        f_aj = c2.date_input("Fecha Ajuste (Excel)", datetime.now())
        
        conceptos_v = tx_raw['concepto'].unique().tolist() if not tx_raw.empty else []
        concepto = st.selectbox("Sugerencia", [""] + conceptos_v)
        if concepto == "":
            concepto = st.text_input("Concepto Manual")
            
        monto = st.number_input("Importe TOTAL (F)", min_value=0.0, step=0.01)
        k_monto = st.number_input("Tu parte neta (K)", min_value=0.0, step=0.01) if es_comp else monto
        
        bancos = sorted(acc_df['name'].tolist()) if not acc_df.empty else []
        b_h = st.selectbox("Desde Banco (H)", bancos)
        
        if tipo == "Traspaso":
            b_i = st.selectbox("Hacia Banco (I)", [b for b in bancos if b != b_h])
            sub_id = cat_df[cat_df['name'] == 'Traspaso'].iloc[0]['id'] if not cat_df.empty else None
        else:
            b_i = tipo
            cats = sorted(cat_df['name'].tolist()) if not cat_df.empty else []
            sub_n = st.selectbox("Subconcepto (E)", cats)
            sub_id = cat_df[cat_df['name'] == sub_n].iloc[0]['id'] if not cat_df.empty else None

        if st.form_submit_button("GUARDAR EN NUBE"):
            f_f = -abs(monto) if tipo in ["Gasto", "Traspaso"] else abs(monto)
            k_f = -abs(k_monto) if tipo in ["Gasto", "Traspaso"] else abs(k_monto)
            if not es_comp: k_f = f_f
            
            h_id = acc_df[acc_df['name'] == b_h].iloc[0]['id']
            supabase.table("transactions").insert({
                "fecha": str(fecha), "fecha_aj": str(f_aj), "concepto": concepto, "subconcepto_id": sub_id,
                "importe_f": f_f, "importe_k": k_f, "banco_h_id": h_id,
                "hacia_i": b_i, "tipo": tipo, "es_compartido": es_comp
            }).execute()
            
            # Update Saldo H
            old_h = float(acc_df.loc[acc_df['name'] == b_h, 'balance'].values[0])
            supabase.table("accounts").update({"balance": old_h + f_f}).eq("id", h_id).execute()
            
            if tipo == "Traspaso":
                i_id = acc_df[acc_df['name'] == b_i].iloc[0]['id']
                old_i = float(acc_df.loc[acc_df['name'] == b_i, 'balance'].values[0])
                supabase.table("accounts").update({"balance": old_i + abs(monto)}).eq("id", i_id).execute()
            st.rerun()

# ----------------- 🛠️ DIAGNÓSTICO MEJORADO -----------------
with menu[4]:
    st.header("Auditoría de Datos")
    if not tx_raw.empty:
        # Cálculo teórico banco por banco incluyendo entradas y salidas
        for _, b in acc_df.iterrows():
            salidas = tx_raw[tx_raw['banco_h_id'] == b['id']]['importe_f'].sum()
            entradas = tx_raw[(tx_raw['tipo'] == 'Traspaso') & (tx_raw['hacia_i'] == b['name'])]['importe_f'].abs().sum()
            teorico = salidas + entradas
            
            if abs(teorico - b['balance']) > 0.01:
                st.warning(f"⚠️ {b['name']}: Saldo real {b['balance']:.2f}€ vs Teórico {teorico:.2f}€.")
            else:
                st.success(f"✅ {b['name']} cuadrado.")
    else:
        st.info("Introduce datos para auditar.")

# ----------------- ⚙️ AJUSTES (LIMPIEZA PARA IMPORTAR) -----------------
with menu[5]:
    st.subheader("Preparación para Importación 2026")
    st.warning("Esta acción pondrá todos tus bancos a 0.00€ para empezar el volcado limpio.")
    if st.button("RESET DE SALDOS A CERO"):
        for _, b in acc_df.iterrows():
            supabase.table("accounts").update({"balance": 0}).eq("id", b['id']).execute()
        st.success("Saldos reseteados. Borra el historial antes de empezar el volcado de 2026.")

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    if not acc_df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("PATRIMONIO TOTAL", f"{acc_df['balance'].sum():,.2f} €")
        if not tx_raw.empty:
            g_j = tx_raw[tx_raw['tipo'] == 'Gasto']['importe_k'].sum()
            c2.metric("GASTO JORGE (NETO)", f"{g_j:,.2f} €")
            g_o = tx_raw[tx_raw['tipo'] == 'Gasto']['importe_f'].sum() - g_j
            c3.metric("COMPARTIDO/OTROS", f"{g_o:,.2f} €")
        
        st.write("---")
        st.subheader("Balances por Banco")
        st.table(acc_df[acc_df['balance'] != 0][['name', 'balance']])
