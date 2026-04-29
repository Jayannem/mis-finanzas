import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="FinanceFlow Pro v2.1", layout="wide")
st.markdown("<style>[data-testid='stSidebar']{display:none;} .main{padding:10px;}</style>", unsafe_allow_html=True)

# --- CONEXIÓN ---
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- FUNCIONES DE CARGA ---
def get_all(table):
    try:
        res = supabase.table(table).select("*").execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

def preparar_tabla(df_tx, df_acc, df_cat):
    if df_tx.empty: return df_tx
    df = df_tx.copy()
    # Mapeo de nombres
    map_acc = dict(zip(df_acc['id'], df_acc['name'])) if not df_acc.empty else {}
    map_cat = dict(zip(df_cat['id'], df_cat['name'])) if not df_cat.empty else {}
    
    df['Banco (H)'] = df['banco_h_id'].map(map_acc)
    df['Subconcepto (E)'] = df['subconcepto_id'].map(map_cat)
    
    cols = ['id', 'fecha', 'fecha_aj', 'concepto', 'Subconcepto (E)', 'importe_f', 'importe_k', 'Banco (H)', 'hacia_i', 'tipo', 'es_compartido']
    return df[[c for c in cols if c in df.columns]]

# --- CARGA INICIAL ---
acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Registro", "🗂️ Tabla Maestra", "📜 Borrado/Historial", "🛠️ Diagnóstico"])

# ----------------- 📝 REGISTRO -----------------
with menu[1]:
    tipo = st.radio("Tipo", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("Gasto Compartido")
    with st.form("form_v21"):
        c1, c2 = st.columns(2)
        f_r = c1.date_input("Fecha Real", datetime.now())
        f_a = c2.date_input("Fecha Ajuste", datetime.now())
        concepto = st.text_input("Concepto")
        monto = st.number_input("Importe F (Total)", min_value=0.0, step=0.01)
        k_monto = st.number_input("Parte Jorge (K)", min_value=0.0, step=0.01) if es_comp else monto
        
        bancos = sorted(acc_df['name'].tolist()) if not acc_df.empty else []
        b_h = st.selectbox("Desde Banco (H)", bancos)
        
        if tipo == "Traspaso":
            b_i = st.selectbox("Hacia Banco (I)", [b for b in bancos if b != b_h])
            sub_id = cat_df[cat_df['name'] == 'Traspaso'].iloc[0]['id']
        else:
            b_i = tipo
            sub_n = st.selectbox("Subconcepto (E)", sorted(cat_df['name'].tolist()))
            sub_id = cat_df[cat_df['name'] == sub_n].iloc[0]['id']

        if st.form_submit_button("GUARDAR"):
            f_f = -abs(monto) if tipo in ["Gasto", "Traspaso"] else abs(monto)
            k_f = -abs(k_monto) if tipo in ["Gasto", "Traspaso"] else abs(k_monto)
            if not es_comp: k_f = f_f
            
            h_id = acc_df[acc_df['name'] == b_h].iloc[0]['id']
            supabase.table("transactions").insert({
                "fecha": str(f_r), "fecha_aj": str(f_a), "concepto": concepto, "subconcepto_id": sub_id,
                "importe_f": f_f, "importe_k": k_f, "banco_h_id": h_id, "hacia_i": b_i, 
                "tipo": tipo, "es_compartido": es_comp
            }).execute()
            
            # Update Saldo Origen
            old_h = float(acc_df.loc[acc_df['name'] == b_h, 'balance'].values[0])
            supabase.table("accounts").update({"balance": old_h + f_f}).eq("id", h_id).execute()
            
            if tipo == "Traspaso":
                i_id = acc_df[acc_df['name'] == b_i].iloc[0]['id']
                old_i = float(acc_df.loc[acc_df['name'] == b_i, 'balance'].values[0])
                supabase.table("accounts").update({"balance": old_i + abs(monto)}).eq("id", i_id).execute()
            st.rerun()

# ----------------- 📜 HISTORIAL & BORRADO (CON RECALIBRACIÓN) -----------------
with menu[3]:
    st.subheader("Gestión de Movimientos")
    if not tx_raw.empty:
        df_vis = preparar_tabla(tx_raw, acc_df, cat_df)
        id_del = st.number_input("ID a eliminar", min_value=0, step=1)
        
        if st.button("🗑️ ELIMINAR Y RECALIBRAR SALDOS"):
            # 1. Obtener datos de la TX antes de borrar
            target = tx_raw[tx_raw['id'] == id_del]
            if not target.empty:
                row = target.iloc[0]
                f_val = float(row['importe_f'])
                b_h_id = row['banco_h_id']
                tipo_tx = row['tipo']
                hacia_i = row['hacia_i']
                
                # 2. Revertir Banco Origen (H)
                cur_h = float(acc_df[acc_df['id'] == b_h_id]['balance'].values[0])
                supabase.table("accounts").update({"balance": cur_h - f_val}).eq("id", b_h_id).execute()
                
                # 3. Revertir Banco Destino (I) si fue traspaso
                if tipo_tx == "Traspaso":
                    i_id = acc_df[acc_df['name'] == hacia_i]['id'].values[0]
                    cur_i = float(acc_df[acc_df['id'] == i_id]['balance'].values[0])
                    supabase.table("accounts").update({"balance": cur_i - abs(f_val)}).eq("id", i_id).execute()
                
                # 4. Borrar el registro
                supabase.table("transactions").delete().eq("id", id_del).execute()
                st.success(f"Registro {id_del} borrado y saldos revertidos.")
                st.rerun()
        
        st.dataframe(df_vis.sort_values('id', ascending=False), use_container_width=True, hide_index=True)

# ----------------- 🗂️ TABLA MAESTRA -----------------
with menu[2]:
    if not tx_raw.empty:
        st.dataframe(preparar_tabla(tx_raw, acc_df, cat_df).sort_values('id', ascending=False), use_container_width=True)

# ----------------- 🛠️ DIAGNÓSTICO (LIMPIO) -----------------
with menu[4]:
    st.header("Auditoría de Sistemas")
    if not tx_raw.empty:
        # Solo bancos que han tenido actividad
        bancos_activos = tx_raw['banco_h_id'].unique().tolist()
        for _, b in acc_df.iterrows():
            if b['id'] in bancos_activos or b['balance'] != 0:
                sal = tx_raw[tx_raw['banco_h_id'] == b['id']]['importe_f'].sum()
                ent = tx_raw[(tx_raw['tipo'] == 'Traspaso') & (tx_raw['hacia_i'] == b['name'])]['importe_f'].abs().sum()
                teorico = sal + ent
                if abs(teorico - b['balance']) > 0.01:
                    st.error(f"❌ {b['name']}: Saldo {b['balance']}€ != Teórico {teorico}€")
                else:
                    st.success(f"✅ {b['name']} cuadrado.")

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    if not acc_df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("PATRIMONIO TOTAL", f"{acc_df['balance'].sum():,.2f} €")
        if not tx_raw.empty:
            g_j = tx_raw[tx_raw['tipo'] == 'Gasto']['importe_k'].sum()
            c2.metric("GASTO JORGE (NETO)", f"{g_j:,.2f} €")
            # Gráfico de tarta de gastos Jorge
            df_g = tx_raw[tx_raw['tipo'] == 'Gasto'].merge(cat_df, left_on='subconcepto_id', right_on='id')
            fig = px.pie(df_g, values=df_g['importe_k'].abs(), names='name', title="Gastos Reales Jorge")
            st.plotly_chart(fig, use_container_width=True)
