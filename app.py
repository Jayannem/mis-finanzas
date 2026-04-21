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

# Cargamos datos base
acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- TRADUCCIÓN DE TABLA (Mapeo por Diccionario - Más seguro) ---
def preparar_tabla_visible(df_tx, df_acc, df_cat):
    if df_tx.empty: return df_tx
    df = df_tx.copy()
    
    # Crear diccionarios de traducción {id: nombre}
    dict_bancos = dict(zip(df_acc['id'], df_acc['name'])) if not df_acc.empty else {}
    dict_cats = dict(zip(df_cat['id'], df_cat['name'])) if not df_cat.empty else {}
    
    # Aplicar traducción
    df['Banco (H)'] = df['banco_h_id'].map(dict_bancos).fillna("Desconocido")
    df['Subconcepto (E)'] = df['subconcepto_id'].map(dict_cats).fillna("General")
    
    # Seleccionar y ordenar columnas finales
    cols = ['id', 'fecha', 'fecha_aj', 'concepto', 'Subconcepto (E)', 'importe_f', 'importe_k', 'Banco (H)', 'hacia_i', 'tipo', 'es_compartido']
    return df[[c for c in cols if c in df.columns]]

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Nuevo Registro", "🗂️ Tabla Maestra", "📜 Historial", "⚙️ Ajustes"])

# ----------------- 📝 NUEVO REGISTRO -----------------
with menu[1]:
    st.subheader("Entrada de Datos")
    
    # Selector de tipo (Fuera del form para ser reactivo)
    tipo = st.radio("Acción", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("¿Es compartido?")

    # INICIO DEL FORMULARIO
    with st.form("main_form_v16"):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha Real", datetime.now())
        fecha_aj = c2.date_input("Fecha Ajuste (Contable)", datetime.now())
        
        concepto = st.text_input("Concepto (Ej: Mercadona)")
        user_monto = st.number_input("Importe Total (€)", min_value=0.0, step=0.01)
        
        # Lógica de parte neta
        if es_comp:
            user_k = st.number_input("Tu parte Neta (K)", min_value=0.0, step=0.01)
        else:
            user_k = user_monto
            
        # Selectores de Banco y Categoría
        list_bancos = acc_df['name'].tolist() if not acc_df.empty else []
        banco_h = st.selectbox("Banco Origen (Desde H)", list_bancos)
        
        if tipo == "Traspaso":
            hacia_i = st.selectbox("Banco Destino (Hacia I)", [b for b in list_bancos if b != banco_h])
            traspaso_row = cat_df[cat_df['name'] == 'Traspaso']
            sub_id = traspaso_row.iloc[0]['id'] if not traspaso_row.empty else None
        else:
            hacia_i = tipo 
            list_cats = cat_df['name'].tolist() if not cat_df.empty else []
            sub_nombre = st.selectbox("Subconcepto (E)", list_cats)
            sub_row = cat_df[cat_df['name'] == sub_nombre]
            sub_id = sub_row.iloc[0]['id'] if not sub_row.empty else None

        # EL BOTÓN (DEBE ESTAR DENTRO DEL FORM)
        submitted = st.form_submit_button("GUARDAR REGISTRO")

        if submitted:
            # Lógica de signos
            f_final = -abs(user_monto) if tipo in ["Gasto", "Traspaso"] else abs(user_monto)
            k_final = -abs(user_k) if tipo in ["Gasto", "Traspaso"] else abs(user_k)
            
            # Obtener ID del banco H
            h_id = acc_df[acc_df['name'] == banco_h].iloc[0]['id']
            
            # Guardar transacción
            data = {
                "fecha": str(fecha), "fecha_aj": str(fecha_aj),
                "concepto": concepto, "subconcepto_id": sub_id,
                "importe_f": f_final, "importe_k": k_final,
                "banco_h_id": h_id, "hacia_i": hacia_i,
                "tipo": tipo, "es_compartido": es_comp
            }
            supabase.table("transactions").insert(data).execute()
            
            # Actualizar Saldo Banco Origen
            old_h = float(acc_df.loc[acc_df['name'] == banco_h, 'balance'].values[0])
            supabase.table("accounts").update({"balance": old_h + f_final}).eq("id", h_id).execute()
            
            # Si es traspaso, actualizar destino
            if tipo == "Traspaso":
                i_id = acc_df[acc_df['name'] == hacia_i].iloc[0]['id']
                old_i = float(acc_df.loc[acc_df['name'] == hacia_i, 'balance'].values[0])
                supabase.table("accounts").update({"balance": old_i + abs(user_monto)}).eq("id", i_id).execute()
            
            st.success("Registro guardado correctamente.")
            st.rerun()

# ----------------- 🗂️ TABLA MAESTRA -----------------
with menu[2]:
    st.subheader("Vista Excel")
    if not tx_raw.empty:
        tabla_final = preparar_tabla_visible(tx_raw, acc_df, cat_df)
        st.dataframe(tabla_final.sort_values('id', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No hay datos en la tabla.")

# ----------------- 📜 HISTORIAL -----------------
with menu[3]:
    st.subheader("Borrar Registros")
    id_borrar = st.number_input("ID a eliminar", min_value=0, step=1)
    if st.button("Confirmar Borrado"):
        supabase.table("transactions").delete().eq("id", id_borrar).execute()
        st.rerun()

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    st.title("Vista General")
    if not acc_df.empty:
        total_bancos = acc_df['balance'].sum()
        st.metric("Saldo Total en Bancos (Caja)", f"{total_bancos:,.2f} €")
        
        st.write("---")
        c1, c2 = st.columns(2)
        if not tx_raw.empty:
            gasto_jorge = tx_raw[tx_raw['tipo'] == 'Gasto']['importe_k'].sum()
            c1.metric("Gasto Neto Jorge (Acumulado)", f"{gasto_jorge:,.2f} €")
            
            gasto_total_caja = tx_raw[tx_raw['tipo'] == 'Gasto']['importe_f'].sum()
            c2.metric("Gasto Total Caja (F)", f"{gasto_total_caja:,.2f} €")

    st.subheader("Saldos Individuales")
    st.table(acc_df[['name', 'balance']])
