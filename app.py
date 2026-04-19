import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import os

# --- CONFIGURACIÓN MÓVIL & ESTILO ---
st.set_page_config(page_title="FinanceFlow", page_icon="💰", layout="wide")

# Inyección de CSS para que parezca una App Nativa
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .stApp { background-color: #f8f9fa; }
    .main { padding-top: 1rem; }
    .card {
        background-color: white; padding: 1.5rem; border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 1rem;
        border-left: 5px solid #007bff;
    }
    .metric-value { font-size: 24px; font-weight: bold; color: #1f1f1f; }
    .metric-label { font-size: 14px; color: #6c757d; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3rem; }
    .category-btn { font-size: 20px !important; }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- FUNCIONES DE DATOS ---
def fetch(table):
    res = supabase.table(table).select("*").execute()
    return pd.DataFrame(res.data)

def update_balance(acc_id, new_bal):
    supabase.table('accounts').update({'balance': float(new_bal)}).eq('id', acc_id).execute()

# --- NAVEGACIÓN TIPO APP ---
menu = st.tabs(["🏠 Inicio", "💳 Cartera", "📈 Inversión", "➕ Añadir", "⚙️ Ajustes"])

# --- DATOS GLOBALES ---
acc_df = fetch("accounts")
cat_df = fetch("categories")

# ----------------- 🏠 HOME (DASHBOARD) -----------------
with menu[0]:
    if not acc_df.empty:
        total_net = acc_df['balance'].sum()
        liquid = acc_df[acc_df['type'] == 'liquid']['balance'].sum()
        invested = acc_df[acc_df['type'] == 'investment']['balance'].sum()
        
        st.markdown(f"""
            <div class='card' style='border-left: 5px solid #28a745; text-align: center;'>
                <div class='metric-label'>Patrimonio Neto Total</div>
                <div class='metric-value' style='font-size: 35px;'>{total_net:,.2f} €</div>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        col1.metric("Efectivo/Banco", f"{liquid:,.2f} €")
        col2.metric("Invertido", f"{invested:,.2f} €")
        
        st.subheader("Presupuesto del mes")
        tx_df = fetch("transactions")
        if not tx_df.empty and not cat_df.empty:
            # Lógica de progreso por categoría
            for _, cat in cat_df.iterrows():
                spent = tx_df[tx_df['category_id'] == cat['id']]['amount'].sum()
                limit = float(cat['monthly_limit'])
                if limit > 0:
                    prog = min(spent/limit, 1.0)
                    st.write(f"**{cat['name']}** ({spent:,.0f}€ / {limit:,.0f}€)")
                    st.progress(prog)

# ----------------- 💳 CARTERA (CUENTAS) -----------------
with menu[1]:
    st.subheader("Mis Cuentas")
    liquid_accs = acc_df[acc_df['type'] == 'liquid']
    for _, row in liquid_accs.iterrows():
        color = "#004481" if row['name'] == 'BBVA' else "#ff5900" if row['name'] == 'Bankinter' else "#007bff"
        st.markdown(f"""
            <div class='card' style='border-left: 10px solid {color};'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <span style='font-weight: bold;'>{row['name']}</span>
                    <span class='metric-value'>{row['balance']:,.2f} €</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

# ----------------- 📈 INVERSIONES (DETALLADO) -----------------
with menu[2]:
    st.subheader("Inversiones por Broker")
    inv_accs = acc_df[acc_df['type'] == 'investment']
    assets_df = fetch("assets")
    
    for _, broker in inv_accs.iterrows():
        with st.expander(f"🏦 {broker['name']} - Total: {broker['balance']:,.2f} €"):
            if not assets_df.empty:
                broker_assets = assets_df[assets_df['broker_id'] == broker['id']]
                for _, asset in broker_assets.iterrows():
                    c1, c2 = st.columns([2,1])
                    c1.write(asset['name'])
                    c2.write(f"**{asset['current_value']:,.2f} €**")
            
            # Botón para actualizar valor del broker total
            new_val = st.number_input(f"Actualizar Total {broker['name']}", key=f"up_{broker['id']}")
            if st.button("Guardar Valor", key=f"btn_{broker['id']}"):
                update_balance(broker['id'], new_val)
                st.rerun()

# ----------------- ➕ AÑADIR (CALCULADORA) -----------------
with menu[3]:
    st.subheader("Registrar Movimiento")
    
    with st.form("calc_form", clear_on_submit=True):
        monto = st.number_input("Cantidad (€)", min_value=0.0, step=1.0, format="%.2f")
        
        st.write("Selecciona Categoría:")
        # Rejilla de iconos
        cat_icons = {
            "Supermercado": "🛒", "Cervezas": "🍻", "Restaurantes": "🍴",
            "Regalos": "🎁", "Transporte": "🚗", "Suscripciones": "📱",
            "Seguros": "🛡️", "Alquiler": "🏠", "Salud": "🏥", "Deporte": "💪",
            "Préstamos/Amigos": "🤝"
        }
        
        # Grid 3x4
        category_name = st.selectbox("Categoría", cat_df['name'].tolist() if not cat_df.empty else ["Sin categorías"])
        
        cuenta_nombre = st.selectbox("¿Con qué pagaste?", acc_df[acc_df['type'] == 'liquid']['name'].tolist())
        
        es_provision = st.checkbox("Provisión (Compartido)")
        cuanto_amigo = st.number_input("Parte de amigo (€)", min_value=0.0) if es_provision else 0
        
        if st.form_submit_button("REGISTRAR GASTO"):
            acc_id = acc_df[acc_df['name'] == cuenta_nombre].iloc[0]['id']
            old_bal = acc_df[acc_df['name'] == cuenta_nombre].iloc[0]['balance']
            cat_id = cat_df[cat_df['name'] == category_name].iloc[0]['id']
            
            # 1. Restar del banco
            update_balance(acc_id, float(old_bal) - monto)
            
            # 2. Registrar transacción
            supabase.table('transactions').insert({
                "description": category_name,
                "amount": monto,
                "account_id": acc_id,
                "category_id": cat_id,
                "is_provision": es_provision,
                "provision_amount": cuanto_amigo
            }).execute()
            
            st.success("¡Registrado!")
            st.rerun()

# ----------------- ⚙️ AJUSTES -----------------
with menu[4]:
    st.subheader("Configuración")
    # Botón para cambiar a oscuro (Simulado)
    if st.toggle("Modo Oscuro"):
        st.info("El modo oscuro se aplicará en la próxima actualización de estilos.")
    
    if st.button("Añadir Activo de Inversión"):
        with st.form("new_asset"):
            name = st.text_input("Nombre (ej: Apple)")
            broker = st.selectbox("Broker", inv_accs['name'].tolist())
            val = st.number_input("Valor inicial")
            if st.form_submit_button("Crear"):
                b_id = inv_accs[inv_accs['name'] == broker].iloc[0]['id']
                supabase.table('assets').insert({"name": name, "broker_id": b_id, "current_value": val}).execute()
                st.rerun()
