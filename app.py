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

# --- CARGA DE DATOS ROBUSTA ---
def get_all(table, expected_columns):
    try:
        res = supabase.table(table).select("*").execute()
        df = pd.DataFrame(res.data)
        if df.empty:
            return pd.DataFrame(columns=expected_columns)
        return df
    except:
        return pd.DataFrame(columns=expected_columns)

# Cargamos datos definiendo las columnas para evitar el KeyError
acc_df = get_all("accounts", ["id", "name", "type", "balance"])
cat_df = get_all("categories", ["id", "name", "monthly_limit"])
tx_raw = get_all("transactions", ["id", "fecha", "concepto", "importe_f", "importe_k", "tipo"])

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
        conceptos_previos = tx_raw['concepto'].unique().tolist() if not tx_raw.empty else []
        concepto = st.selectbox("Concepto (Sugerencias)", [""] + conceptos_previos)
        if concepto == "":
            concepto = st.text_input("Concepto manual (Ej: Mercadona)")
            
        f_val = st.number_input("Importe TOTAL (F)", value=0.0, step=0.01)
        
        # Lógica de Neto Jorge (K)
        es_comp = st.checkbox("¿Es compartido?")
        k_val = st.number_input("Tu parte neta (K)", value=f_val, step=0.01) if es_comp else f_val
        
        # Listado de bancos
        bancos = acc_df['name'].tolist() if not acc_df.empty else ["Efectivo"]
        banco_h = st.selectbox("Desde Banco (H)", bancos)
        
        if tipo == "Traspaso":
            hacia_i = st.selectbox("Hacia Banco (I)", [b for b in bancos if b != banco_h])
            # Buscamos el ID de la categoría Traspaso de forma segura
            traspaso_cat = cat_df[cat_df['name'] == 'Traspaso']
            sub_id = traspaso_cat.iloc[0]['id'] if not traspaso_cat.empty else None
        else:
            hacia_i = tipo 
            sub_list = cat_df['name'].tolist() if not cat_df.empty else ["General"]
            sub_nombre = st.selectbox("Categoría (Subconcepto E)", sub_list)
            sub_row = cat_df[cat_df['name'] == sub_nombre]
            sub_id = sub_row.iloc[0]['id'] if not sub_row.empty else None

        if st.form_submit_button("GUARDAR REGISTRO"):
            if not acc_df.empty:
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
                
                st.success("Guardado con éxito.")
                st.rerun()
            else:
                st.error("Error: No se han encontrado cuentas en la base de datos.")

# ----------------- 📜 HISTORIAL -----------------
with menu[2]:
    st.subheader("Log de Transacciones (Vista Excel)")
    if not tx_raw.empty:
        selected_id = st.selectbox("Selecciona ID para borrar", tx_raw['id'].sort_values(ascending=False))
        if st.button("❌ BORRAR REGISTRO"):
            supabase.table("transactions").delete().eq("id", selected_id).execute()
            st.warning(f"Registro {selected_id} borrado.")
            st.rerun()
        st.dataframe(tx_raw.sort_values('id', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No hay transacciones registradas.")

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    st.title("Análisis")
    if not tx_raw.empty and len(tx_raw) > 0:
        c1, c2 = st.columns(2)
        f_inicio = c1.date_input("Desde", datetime(2026, 1, 1))
        f_fin = c2.date_input("Hasta", datetime.now())
        
        df_filt = tx_raw[(tx_raw['fecha_aj'] >= str(f_inicio)) & (tx_raw['fecha_aj'] <= str(f_fin))].copy()
        
        if not df_filt.empty:
            df_filt['Gasto Jorge (K)'] = df_filt['importe_k'].abs()
            df_filt['Otros (F-K)'] = (df_filt['importe_f'].abs() - df_filt['importe_k'].abs())
            
            gastos = df_filt[df_filt['tipo'] == 'Gasto']
            if not gastos.empty:
                resumen = gastos.groupby('concepto')[['Gasto Jorge (K)', 'Otros (F-K)']].sum().reset_index()
                fig = px.bar(resumen, x='concepto', y=['Gasto Jorge (K)', 'Otros (F-K)'], 
                             title="Salidas de Caja por Concepto", barmode='stack')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay gastos en este rango de fechas.")
    else:
        st.info("Añade tu primera transacción en la pestaña 'Nuevo Registro'.")
