import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="FinanceFlow Pro v2.3", layout="wide")
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

# --- CARGA DE DATOS ---
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
    # Orden parecido a tu Excel
    cols = ['id', 'fecha', 'fecha_aj', 'concepto', 'Subconcepto (E)', 'importe_f', 'importe_k', 'Banco (H)', 'hacia_i', 'tipo', 'es_compartido']
    return df[[c for c in cols if c in df.columns]]

# --- CARGA INICIAL ---
acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Registro", "🗂️ Tabla Maestra", "🛠️ Diagnóstico", "⚙️ Ajustes"])

# ----------------- 📊 DASHBOARD (MÉTRICAS COMPLETAS) -----------------
with menu[0]:
    if not acc_df.empty:
        total_cash = acc_df['balance'].sum()
        st.metric("PATRIMONIO TOTAL (CAJA)", f"{total_cash:,.2f} €")
        
        if not tx_raw.empty:
            st.write("---")
            # 4 MÉTRICAS CLAVE
            c1, c2, c3, c4 = st.columns(4)
            
            gastos = tx_raw[tx_raw['tipo'] == 'Gasto']
            ingresos = tx_raw[tx_raw['tipo'] == 'Ingreso']
            
            g_jorge = gastos['importe_k'].sum()
            g_caja_total = gastos['importe_f'].sum()
            g_otros = g_caja_total - g_jorge
            i_totales = ingresos['importe_f'].sum()
            
            c1.metric("Gasto Real Jorge (K)", f"{g_jorge:,.2f} €")
            c2.metric("Compartido/Otros", f"{g_otros:,.2f} €")
            c3.metric("Salida Total Caja", f"{g_caja_total:,.2f} €")
            c4.metric("Ingresos Totales", f"{i_totales:,.2f} €")
            
            st.write("---")
            # Gráfico comparativo Jorge vs Caja
            fig = px.bar(gastos, x='concepto', y=['importe_k', 'importe_f'], 
                         title="Comparativa: Gasto Jorge (K) vs Caja (F)", barmode='group')
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("💳 Cuentas")
        liquid_df = acc_df[acc_df['type'] == 'liquid'].sort_values('balance', ascending=False)
        cols_bancos = st.columns(3)
        for i, (index, row) in enumerate(liquid_df.iterrows()):
            with cols_bancos[i % 3]:
                st.markdown(f'<div class="bank-card"><div style="font-size:0.8em;">{row["name"]}</div><div style="font-size:1.2em; font-weight:bold;">{row["balance"]:,.2f} €</div></div>', unsafe_allow_html=True)

# ----------------- 📝 REGISTRO (LÓGICA v2.2) -----------------
with menu[1]:
    tipo = st.radio("Acción", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("Compartido")
    with st.form("form_v23"):
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
            supabase.table("transactions").insert({"fecha": str(f_r), "concepto": concepto, "subconcepto_id": sub_id, "importe_f": f_f, "importe_k": k_f, "banco_h_id": h_id, "hacia_i": b_i, "tipo": tipo, "es_compartido": es_comp}).execute()
            
            # Update Saldo
            old_h = float(acc_df.loc[acc_df['name'] == b_h, 'balance'].values[0])
            supabase.table("accounts").update({"balance": old_h + f_f}).eq("id", h_id).execute()
            if tipo == "Traspaso":
                i_id = acc_df[acc_df['name'] == b_i].iloc[0]['id']
                old_i = float(acc_df.loc[acc_df['name'] == b_i, 'balance'].values[0])
                supabase.table("accounts").update({"balance": old_i + abs(monto)}).eq("id", i_id).execute()
            st.rerun()

# ----------------- 🗂️ TABLA MAESTRA (CON BORRADO INTEGRADO) -----------------
with menu[2]:
    st.subheader("Historial de Movimientos")
    if not tx_raw.empty:
        # SELECTOR MÚLTIPLE DE IDS PARA BORRAR
        ids_a_borrar = st.multiselect("Selecciona uno o varios IDs para eliminar y recalibrar:", tx_raw['id'].sort_values(ascending=False).tolist())
        
        if st.button("🗑️ ELIMINAR SELECCIONADOS"):
            for id_del in ids_a_borrar:
                row = tx_raw[tx_raw['id'] == id_del].iloc[0]
                f_val = float(row['importe_f'])
                b_h_id = row['banco_h_id']
                # Revertir H
                cur_h = float(acc_df[acc_df['id'] == b_h_id]['balance'].values[0])
                supabase.table("accounts").update({"balance": cur_h - f_val}).eq("id", b_h_id).execute()
                # Revertir I si era Traspaso
                if row['tipo'] == 'Traspaso':
                    i_name = row['hacia_i']
                    i_id = acc_df[acc_df['name'] == i_name]['id'].values[0]
                    cur_i = float(acc_df[acc_df['id'] == i_id]['balance'].values[0])
                    supabase.table("accounts").update({"balance": cur_i - abs(f_val)}).eq("id", i_id).execute()
                # Borrar
                supabase.table("transactions").delete().eq("id", id_del).execute()
            st.success(f"Se han eliminado {len(ids_a_borrar)} registros y ajustado los bancos.")
            st.rerun()
            
        # MOSTRAR TABLA
        df_vis = preparar_tabla_visible(tx_raw, acc_df, cat_df)
        st.dataframe(df_vis.sort_values('id', ascending=False), use_container_width=True, hide_index=True)

# ----------------- 🛠️ DIAGNÓSTICO -----------------
with menu[3]:
    if not tx_raw.empty:
        st.subheader("Auditoría de Cuentas")
        for _, b in acc_df.iterrows():
            if b['balance'] != 0 or b['id'] in tx_raw['banco_h_id'].tolist():
                salidas = tx_raw[tx_raw['banco_h_id'] == b['id']]['importe_f'].sum()
                entradas = tx_raw[(tx_raw['tipo'] == 'Traspaso') & (tx_raw['hacia_i'] == b['name'])]['importe_f'].abs().sum()
                teorico = salidas + entradas
                if abs(teorico - b['balance']) > 0.01:
                    st.error(f"❌ {b['name']}: Saldo {b['balance']}€ != Teórico {teorico}€")
                else:
                    st.success(f"✅ {b['name']} cuadrado.")

# ----------------- ⚙️ AJUSTES -----------------
with menu[4]:
    st.subheader("Reset de Sistema")
    if st.button("LIMPIAR TODOS LOS SALDOS (Poner a 0)"):
        for _, b in acc_df.iterrows():
            supabase.table("accounts").update({"balance": 0}).eq("id", b['id']).execute()
        st.rerun()
