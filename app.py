import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="FinanceFlow Pro - Test", layout="wide")
st.markdown("<style>[data-testid='stSidebar']{display:none;} .main{padding:10px;}</style>", unsafe_allow_html=True)

# --- CONEXIÓN ---
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- CARGA DE DATOS ---
def get_all(table):
    res = supabase.table(table).select("*").execute()
    return pd.DataFrame(res.data)

acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Nuevo Registro", "📜 Historial (Excel)", "⚙️ Ajustes"])

# ----------------- 📝 NUEVO REGISTRO -----------------
with menu[1]:
    st.subheader("Entrada de Datos")
    
    tipo = st.radio("¿Qué vas a registrar?", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    
    with st.form("main_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha real del movimiento", datetime.now())
        fecha_aj = c2.date_input("Fecha contable (Ajuste)", datetime.now())
        
        # Sugeridor de conceptos
        if not tx_raw.empty:
            sugerencias = tx_raw['concepto'].unique().tolist()
            concepto = st.selectbox("Concepto (Busca o escribe)", [""] + sugerencias)
            if concepto == "":
                concepto = st.text_input("Nuevo Concepto")
        else:
            concepto = st.text_input("Concepto (Ej: Mercadona)")
            
        f_val = st.number_input("Importe TOTAL (F)", value=0.0, step=0.01)
        
        # Lógica de Neto Jorge (K)
        es_comp = st.checkbox("¿Es compartido?")
        if es_comp:
            k_val = st.number_input("Tu parte neta (K)", value=f_val, step=0.01)
        else:
            k_val = f_val
            
        bancos = acc_df['name'].tolist()
        banco_h = st.selectbox("Desde Banco (H)", bancos)
        
        if tipo == "Traspaso":
            hacia_i = st.selectbox("Hacia Banco (I)", [b for b in bancos if b != banco_h])
            sub_id = cat_df[cat_df['name'] == 'Traspaso'].iloc[0]['id']
        else:
            hacia_i = tipo # 'Gasto' o 'Ingreso'
            sub_nombre = st.selectbox("Categoría (Subconcepto E)", cat_df['name'].tolist())
            sub_id = cat_df[cat_df['name'] == sub_nombre].iloc[0]['id']

        if st.form_submit_button("GUARDAR REGISTRO"):
            h_id = acc_df[acc_df['name'] == banco_h].iloc[0]['id']
            
            data = {
                "fecha": str(fecha), "fecha_aj": str(fecha_aj),
                "concepto": concepto, "subconcepto_id": sub_id,
                "importe_f": f_val, "importe_k": k_val,
                "banco_h_id": h_id, "hacia_i": hacia_i,
                "tipo": tipo, "es_compartido": es_comp
            }
            supabase.table("transactions").insert(data).execute()
            
            # Actualizar Saldo Banco H
            old_h = acc_df[acc_df['name'] == banco_h].iloc[0]['balance']
            supabase.table("accounts").update({"balance": float(old_h) + f_val}).eq("id", h_id).execute()
            
            # Si es traspaso, actualizar Saldo Banco I
            if tipo == "Traspaso":
                i_id = acc_df[acc_df['name'] == hacia_i].iloc[0]['id']
                old_i = acc_df[acc_df['name'] == hacia_i].iloc[0]['balance']
                supabase.table("accounts").update({"balance": float(old_i) - f_val}).eq("id", i_id).execute()
            
            st.success("Guardado y saldos actualizados.")
            st.rerun()

# ----------------- 📜 HISTORIAL -----------------
with menu[2]:
    st.subheader("Log de Transacciones (Vista Excel)")
    if not tx_raw.empty:
        # Añadir opción de borrar
        selected_id = st.selectbox("Selecciona ID para borrar o editar", tx_raw['id'].sort_values(ascending=False))
        if st.button("❌ BORRAR REGISTRO SELECCIONADO"):
            supabase.table("transactions").delete().eq("id", selected_id).execute()
            st.warning(f"Registro {selected_id} borrado. (Nota: Los saldos bancarios no se revierten automáticamente al borrar, haz un ajuste si es necesario)")
            st.rerun()
            
        st.dataframe(tx_raw.sort_values('id', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No hay datos.")

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    st.title("Análisis")
    if not tx_raw.empty:
        # Filtro de fecha
        c1, c2 = st.columns(2)
        f_inicio = c1.date_input("Desde", datetime(2026, 1, 1))
        f_fin = c2.date_input("Hasta", datetime.now())
        
        df_filt = tx_raw[(tx_raw['fecha_aj'] >= str(f_inicio)) & (tx_raw['fecha_aj'] <= str(f_fin))]
        
        # Gráfico apilado
        df_filt['Gasto Jorge (K)'] = df_filt['importe_k'].abs()
        df_filt['Otros (F-K)'] = (df_filt['importe_f'].abs() - df_filt['importe_k'].abs())
        
        gastos = df_filt[df_filt['tipo'] == 'Gasto']
        resumen = gastos.groupby('concepto')[['Gasto Jorge (K)', 'Otros (F-K)']].sum().reset_index()
        
        fig = px.bar(resumen, x='concepto', y=['Gasto Jorge (K)', 'Otros (F-K)'], 
                     title="Salidas de Caja por Concepto", barmode='stack')
        st.plotly_chart(fig, use_container_width=True)
