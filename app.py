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

acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- TRADUCCIÓN DE TABLA ---
def preparar_tabla_visible(df_tx, df_acc, df_cat):
    if df_tx.empty: return df_tx
    df = df_tx.copy()
    if not df_acc.empty:
        df = df.merge(df_acc[['id', 'name']], left_on='banco_h_id', right_on='id', how='left')
        df = df.rename(columns={'name': 'Banco (H)'}).drop(columns=['id_y', 'banco_h_id'], errors='ignore')
    if not df_cat.empty:
        df = df.merge(df_cat[['id', 'name']], left_on='subconcepto_id', right_on='id', how='left')
        df = df.rename(columns={'name': 'Subconcepto (E)'}).drop(columns=['id', 'subconcepto_id'], errors='ignore')
    
    col_order = ['id_x', 'fecha', 'fecha_aj', 'concepto', 'Subconcepto (E)', 'importe_f', 'importe_k', 'Banco (H)', 'hacia_i', 'tipo', 'es_compartido']
    return df[[c for c in col_order if c in df.columns]]

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Nuevo Registro", "🗂️ Tabla Maestra", "📜 Historial", "⚙️ Ajustes"])

# ----------------- 📝 NUEVO REGISTRO -----------------
with menu[1]:
    st.subheader("Entrada de Datos")
    tipo = st.radio("Acción", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("¿Es compartido?")

    with st.form("main_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha Real", datetime.now())
        fecha_aj = c2.date_input("Fecha Ajuste (Contable)", datetime.now())
        concepto = st.text_input("Concepto")
        user_monto = st.number_input("Importe Total (€)", min_value=0.0, step=0.01)
        
        user_k = st.number_input("Tu parte Neta (K)", min_value=0.0, step=0.01) if es_comp else user_monto
            
        list_bancos = acc_df['name'].tolist() if not acc_df.empty else []
