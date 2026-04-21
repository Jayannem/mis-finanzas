import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="FinanceFlow Pro", layout="wide")
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

# Cargamos todo
acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- FUNCIÓN PARA "TRADUCIR" IDS A NOMBRES ---
def preparar_tabla_visible(df_tx, df_acc, df_cat):
    if df_tx.empty: return df_tx
    df = df_tx.copy()
    # Unir con cuentas para sacar el nombre del banco
    if not df_acc.empty:
        df = df.merge(df_acc[['id', 'name']], left_on='banco_h_id', right_on='id', how='left')
        df = df.rename(columns={'name': 'Banco (H)'}).drop(columns=['id_y', 'banco_h_id'], errors='ignore')
    # Unir con categorías para sacar el nombre del subconcepto
    if not df_cat.empty:
        df = df.merge(df_cat[['id', 'name']], left_on='subconcepto_id', right_on='id', how='left')
        df = df.rename(columns={'name': 'Subconcepto (E)'}).drop(columns=['id', 'subconcepto_id'], errors='ignore')
    
    # Reordenar columnas para que sea igual a tu Excel
    columnas_orden = ['id_x', 'fecha', 'fecha_aj', 'concepto', 'Subconcepto (E)', 'importe_f', 'importe_k', 'Banco (H)', 'hacia_i', 'tipo', 'es_compartido']
    return df[[c for c in columnas_orden if c in df.columns]]

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Nuevo Registro", "🗂️ Tabla Maestra", "📜 Historial", "⚙️ Ajustes"])

# ----------------- 📝 NUEVO REGISTRO -----------------
with menu[1]:
    st.subheader("Entrada de Datos")
    tipo = st.radio("¿Qué vas a registrar?", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("¿Es un gasto compartido?")

    with st.form("main_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha real", datetime.now())
        fecha_aj = c2.date_input("Fecha contable (Ajuste)", datetime.now())
        concepto = st.text_input("Concepto")
        
        # Corregido: Quitamos restricciones de max_value para evitar bloqueos
        user_monto = st.number_input("Importe Total (€)", min_value=0.0, step=0.01)
        
        if es_comp:
            user_k = st.number_input("Importe Neto Jorge (Tu parte)", min_value=0.0, step=0.01)
        else:
            user_k = user_monto
            
        list_bancos = acc_df['name'].tolist() if not acc_df.empty else []
        banco_h = st.selectbox("Desde Banco (H)", list_bancos)
        
        if tipo == "Traspaso":
            hacia_i = st.selectbox("Hacia Banco (I)", [b for b in list_bancos if b != banco_h])
            sub_id = cat_df[cat_df['name'] == 'Traspaso'].iloc[0]['id'] if not cat_df.empty else None
        else:
            hacia_i = tipo 
            list_cats = cat_df['name'].tolist() if not cat_df.empty else []
            sub_nombre = st.selectbox("Subconcepto (E)", list_cats)
            sub_id = cat_df[cat_df['name'] == sub_nombre].iloc[0]['id'] if not cat_df.empty else None

        if st.form_submit_button("GUARDAR REGISTRO"):
            f_final = -abs(user_monto) if tipo in ["Gasto", "Traspaso"] else abs(user_monto)
            k_final = -abs(user_k) if tipo in ["Gasto", "Traspaso"] else abs(user_k)
            
            h_id = acc_df[acc_df['name'] == banco_h].iloc[0]['id']
            data = {
                "fecha": str(fecha), "fecha_aj": str(fecha_aj),
                "concepto": concepto, "subconcepto_id": sub_id,
                "importe_f": f_final, "importe_k": k_final,
                "banco_h_id": h_id, "hacia_i": hacia_i,
                "tipo": tipo, "es_compartido": es_comp
            }
            supabase.table("transactions").insert(data).execute()
            
            # Actualizar Saldo Banco H
            old_h = acc_df[acc_df['name'] == banco_h].iloc[0]['balance']
            supabase.table("accounts").update({"balance": float(old_h) + f_final}).eq("id", h_id).execute()
            
            if tipo == "Traspaso":
                i_id = acc_df[acc_df['name'] == hacia_i].iloc[0]['id']
                old_i = acc_df[acc_df['name'] == hacia_i].iloc[0]['balance']
                supabase.table("accounts").update({"balance": float(old_i) + abs(user_monto)}).eq("id", i_id).execute()
            
            st.success("Guardado correctamente")
            st.rerun()

# ----------------- 🗂️ TABLA MAESTRA -----------------
with menu[2]:
    st.subheader("Visualización tipo Excel")
    if not tx_raw.empty:
        tabla_bonita = preparar_tabla_visible(tx_raw, acc_df, cat_df)
        st.dataframe(tabla_bonita.sort_values('id_x', ascending=False), use_container_width=True, hide_index=True)

# ----------------- 📜 HISTORIAL (BORRADO) -----------------
with menu[3]:
    st.subheader("Gestión de IDs")
    if not tx_raw.empty:
        id_borrar = st.number_input("Escribe el ID para eliminar", min_value=0, step=1)
        if st.button("Eliminar Registro"):
            supabase.table("transactions").delete().eq("id", id_borrar).execute()
            st.rerun()
        st.dataframe(tx_raw[['id', 'fecha', 'concepto', 'importe_f']], use_container_width=True)

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    st.title("Vista General")
    if not acc_df.empty:
        # Sumamos el saldo de todas las cuentas para el patrimonio total
        patrimonio_total = acc_df['balance'].sum()
        st.metric("Saldo Total en Bancos (Caja)", f"{patrimonio_total:,.2f} €")
        
        c1, c2 = st.columns(2)
        # Gasto real de Jorge (K) este mes
        if not tx_raw.empty:
            gasto_jorge = tx_raw[tx_raw['tipo'] == 'Gasto']['importe_k'].sum()
            c1.metric("Gasto Neto Jorge (Acumulado)", f"{gasto_jorge:,.2f} €")
            
            # Gráfico
            fig = px.pie(tx_raw[tx_raw['tipo'] == 'Gasto'], values=tx_raw[tx_raw['tipo'] == 'Gasto']['importe_k'].abs(), names='concepto')
            st.plotly_chart(fig)

    st.subheader("Desglose por Bancos")
    st.dataframe(acc_df[['name', 'balance']], use_container_width=True, hide_index=True)
