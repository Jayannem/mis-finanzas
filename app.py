import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="FinanceFlow Pro v2.6", layout="wide")
st.markdown("""
    <style>
    [data-testid='stSidebar']{display:none;} 
    .main{padding:10px;}
    .bank-card-mini {
        background-color: #ffffff; border-radius: 6px; padding: 6px 10px;
        border-left: 3px solid #28a745; box-shadow: 1px 1px 2px rgba(0,0,0,0.05);
        margin-bottom: 4px;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- CARGA DE DATOS ---
def get_all(table):
    res = supabase.table(table).select("*").execute()
    return pd.DataFrame(res.data)

def preparar_tabla_visible(df_tx, df_acc, df_cat):
    if df_tx.empty: return df_tx
    df = df_tx.copy()
    map_acc = dict(zip(df_acc['id'], df_acc['name'])) if not df_acc.empty else {}
    map_cat = dict(zip(df_cat['id'], df_cat['name'])) if not df_cat.empty else {}
    df['Banco (H)'] = df['banco_h_id'].map(map_acc)
    df['Subconcepto (E)'] = df['subconcepto_id'].map(map_cat)
    cols = ['id', 'fecha', 'fecha_aj', 'concepto', 'Subconcepto (E)', 'importe_f', 'importe_k', 'Banco (H)', 'hacia_i', 'tipo']
    return df[[c for c in cols if c in df.columns]]

# CARGA INICIAL
acc_df = get_all("accounts")
cat_df = get_all("categories")
tx_raw = get_all("transactions")

# --- NAVEGACIÓN ---
menu = st.tabs(["📊 Dashboard", "📝 Registro", "🗂️ Tabla Maestra", "🛠️ Diagnóstico", "⚙️ Ajustes"])

# ----------------- 📊 DASHBOARD -----------------
with menu[0]:
    # 1. Filtro de Fechas (Abril 2026 por defecto según tus capturas)
    today = date.today()
    start_m = date(2026, 4, 1)
    end_m = date(2026, 4, 30)
    
    d_range = st.date_input("Filtro temporal:", [start_m, end_m])
    
    if len(d_range) == 2:
        df_filt = tx_raw[(tx_raw['fecha_aj'] >= str(d_range[0])) & (tx_raw['fecha_aj'] <= str(d_range[1]))]
    else:
        df_filt = tx_raw

    # 2. KPIs (Tu orden exacto)
    k1, k2, k3, k4, k5 = st.columns(5)
    
    gastos = df_filt[df_filt['tipo'] == 'Gasto']
    ingresos = df_filt[df_filt['tipo'] == 'Ingreso']
    
    g_jorge = gastos['importe_k'].sum()
    g_total_f = gastos['importe_f'].sum()
    g_compartido = g_total_f - g_jorge
    i_totales = ingresos['importe_f'].sum()
    liquidez_total = acc_df['balance'].sum()

    k1.metric("Gasto Real Jorge", f"{g_jorge:,.2f} €")
    k2.metric("Compartido", f"{g_compartido:,.2f} €")
    k3.metric("Salida Total Caja", f"{g_total_f:,.2f} €")
    k4.metric("Ingresos Totales", f"{i_totales:,.2f} €")
    k5.metric("Liquidez Real", f"{liquidez_total:,.2f} €")

    st.write("---")
    
    # 3. Cuentas Compactas (Todas)
    st.subheader("💳 Estado de las Cuentas")
    sorted_accs = acc_df.sort_values('name')
    cols_b = st.columns(5) # Más columnas para que sean más pequeñas
    for i, (_, row) in enumerate(sorted_accs.iterrows()):
        with cols_b[i % 5]:
            st.markdown(f"""
                <div class="bank-card-mini">
                    <div style="font-size: 0.7em; color: gray; text-transform: uppercase;">{row['name']}</div>
                    <div style="font-size: 1.0em; font-weight: bold;">{row['balance']:,.2f} €</div>
                </div>
            """, unsafe_allow_html=True)

# ----------------- 📝 REGISTRO -----------------
with menu[1]:
    tipo = st.radio("Acción", ["Gasto", "Ingreso", "Traspaso"], horizontal=True)
    es_comp = st.checkbox("¿Es compartido?")
    with st.form("form_v26"):
        c1, c2 = st.columns(2)
        f_r = c1.date_input("Fecha Real", datetime.now())
        f_a = c2.date_input("Fecha Ajuste", datetime.now())
        concepto = st.text_input("Concepto")
        monto = st.number_input("Importe Total (F)", min_value=0.0, step=0.01)
        k_monto = st.number_input("Tu parte (K)", min_value=0.0, step=0.01) if es_comp else monto
        
        b_h = st.selectbox("Desde Banco (H)", sorted(acc_df['name'].tolist()))
        if tipo == "Traspaso":
            b_i = st.selectbox("Hacia Banco (I)", [b for b in sorted(acc_df['name'].tolist()) if b != b_h])
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
            supabase.table("transactions").insert({"fecha": str(f_r), "fecha_aj": str(f_a), "concepto": concepto, "subconcepto_id": sub_id, "importe_f": f_f, "importe_k": k_f, "banco_h_id": h_id, "hacia_i": b_i, "tipo": tipo, "es_compartido": es_comp}).execute()
            
            # Update Saldo Banco H
            old_h = float(acc_df.loc[acc_df['name'] == b_h, 'balance'].values[0])
            supabase.table("accounts").update({"balance": old_h + f_f}).eq("id", h_id).execute()
            if tipo == "Traspaso":
                i_id = acc_df[acc_df['name'] == b_i].iloc[0]['id']
                old_i = float(acc_df.loc[acc_df['name'] == b_i, 'balance'].values[0])
                supabase.table("accounts").update({"balance": old_i + abs(monto)}).eq("id", i_id).execute()
            st.rerun()

# ----------------- 🗂️ TABLA MAESTRA (BORRADO) -----------------
with menu[2]:
    if not tx_raw.empty:
        ids_del = st.multiselect("Seleccionar IDs para borrar:", tx_raw['id'].sort_values(ascending=False).tolist())
        if st.button("🗑️ BORRAR Y RECALIBRAR"):
            for id_del in ids_del:
                row = tx_raw[tx_raw['id'] == id_del].iloc[0]
                cur_h = float(get_all("accounts").loc[acc_df['id'] == row['banco_h_id'], 'balance'].values[0])
                supabase.table("accounts").update({"balance": cur_h - float(row['importe_f'])}).eq("id", row['banco_h_id']).execute()
                if row['tipo'] == 'Traspaso':
                    i_id = acc_df[acc_df['name'] == row['hacia_i']]['id'].values[0]
                    cur_i = float(get_all("accounts").loc[acc_df['id'] == i_id, 'balance'].values[0])
                    supabase.table("accounts").update({"balance": cur_i - abs(float(row['importe_f']))}).eq("id", i_id).execute()
                supabase.table("transactions").delete().eq("id", id_del).execute()
            st.rerun()
        st.dataframe(preparar_tabla_visible(tx_raw, acc_df, cat_df).sort_values('id', ascending=False), use_container_width=True, hide_index=True)

# ----------------- ⚙️ AJUSTES (LIMPIEZA DE ERRORES) -----------------
with menu[4]:
    st.header("Mantenimiento")
    if st.button("🔄 RECONSTRUIR TODO (Fix BBVA y Liquidez)"):
        # 1. Resetear localmente
        saldos_fix = {row['id']: 0.0 for _, row in acc_df.iterrows()}
        # 2. Calcular basándose en historial
        for _, t in tx_raw.iterrows():
            f = float(t['importe_f'])
            saldos_fix[t['banco_h_id']] += f
            if t['tipo'] == 'Traspaso':
                target_id = acc_df[acc_df['name'] == t['hacia_i']]['id'].values[0]
                saldos_fix[target_id] += abs(f)
        # 3. Aplicar a Supabase
        for b_id, val in saldos_fix.items():
            supabase.table("accounts").update({"balance": val}).eq("id", b_id).execute()
        st.success("Saldos reconstruidos con éxito.")
        st.rerun()
