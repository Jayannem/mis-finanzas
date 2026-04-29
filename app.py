import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="FinanceFlow Pro - STRESS TEST", layout="wide")
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
menu = st.tabs(["📊 Dashboard", "📝 Registro", "🗂️ Tabla", "🛠️ Diagnóstico", "⚙️ Ajustes"])

# ----------------- 📝 REGISTRO (CON VALIDACIÓN PREVIA) -----------------
with menu[1]:
    tipo = st.radio("Tipo", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("Compartido")

    with st.form("form_v19"):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha", datetime.now())
        concepto = st.text_input("Concepto")
        monto = st.number_input("Importe F (Caja)", min_value=0.0, step=0.01)
        k_monto = st.number_input("Importe K (Tuyo)", min_value=0.0, step=0.01) if es_comp else monto
        
        bancos = acc_df['name'].tolist() if not acc_df.empty else []
        b_h = st.selectbox("Origen (H)", bancos)
        
        if tipo == "Traspaso":
            b_i = st.selectbox("Destino (I)", [b for b in bancos if b != b_h])
            sub_id = cat_df[cat_df['name'] == 'Traspaso'].iloc[0]['id'] if not cat_df.empty else None
        else:
            b_i = tipo
            cats = cat_df['name'].tolist() if not cat_df.empty else []
            sub_n = st.selectbox("Subconcepto", cats)
            sub_id = cat_df[cat_df['name'] == sub_n].iloc[0]['id'] if not cat_df.empty else None

        if st.form_submit_button("GUARDAR"):
            f_final = -abs(monto) if tipo in ["Gasto", "Traspaso"] else abs(monto)
            k_final = -abs(k_monto) if tipo in ["Gasto", "Traspaso"] else abs(k_monto)
            if not es_comp: k_final = f_final
            
            h_id = acc_df[acc_df['name'] == b_h].iloc[0]['id']
            # Guardar
            supabase.table("transactions").insert({
                "fecha": str(fecha), "concepto": concepto, "subconcepto_id": sub_id,
                "importe_f": f_final, "importe_k": k_final, "banco_h_id": h_id,
                "hacia_i": b_i, "tipo": tipo, "es_compartido": es_comp
            }).execute()
            
            # Update Saldo H
            old_h = float(acc_df.loc[acc_df['name'] == b_h, 'balance'].values[0])
            supabase.table("accounts").update({"balance": old_h + f_final}).eq("id", h_id).execute()
            
            if tipo == "Traspaso":
                i_id = acc_df[acc_df['name'] == b_i].iloc[0]['id']
                old_i = float(acc_df.loc[acc_df['name'] == b_i, 'balance'].values[0])
                supabase.table("accounts").update({"balance": old_i + abs(monto)}).eq("id", i_id).execute()
            st.rerun()

# ----------------- 🛠️ DIAGNÓSTICO (ESTO ACELERA TODO) -----------------
with menu[3]:
    st.header("Chequeo Automático de Errores")
    if not tx_raw.empty:
        errores = []
        # 1. Check de signos
        gastos_positivos = tx_raw[(tx_raw['tipo'] == 'Gasto') & (tx_raw['importe_f'] > 0)]
        if not gastos_positivos.empty: errores.append(f"🔴 Hay {len(gastos_positivos)} gastos con importe positivo (error de signo).")
        
        # 2. Check de coherencia F vs K
        k_mayor_f = tx_raw[tx_raw['importe_k'].abs() > tx_raw['importe_f'].abs()]
        if not k_mayor_f.empty: errores.append(f"🟠 Hay {len(k_mayor_f)} filas donde tu parte (K) es mayor que el total (F).")
        
        # 3. Check de Descuadre Bancario
        st.subheader("Cuadre de Bancos (Teórico vs Real)")
        for _, b in acc_df.iterrows():
            # Suma de transacciones donde este banco es H (resta F) o I (suma F si es traspaso)
            salidas = tx_raw[tx_raw['banco_h_id'] == b['id']]['importe_f'].sum()
            # (Simplificado para el test)
            if abs(salidas - b['balance']) > 0.01:
                st.warning(f"⚠️ {b['name']}: El saldo ({b['balance']}) no coincide con la suma de movimientos ({salidas}).")

        if not errores:
            st.success("✅ No se detectan errores lógicos en la base de datos.")
        else:
            for e in errores: st.error(e)
    else:
        st.info("No hay datos para diagnosticar.")

# ----------------- 📊 DASHBOARD (RESUMEN) -----------------
with menu[0]:
    if not acc_df.empty:
        st.metric("PATRIMONIO NETO", f"{acc_df['balance'].sum():,.2f} €")
        st.dataframe(acc_df[['name', 'balance']], hide_index=True)
