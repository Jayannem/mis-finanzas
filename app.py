import streamlit as st
import pandas as pd
from supabase import create_client
import os

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="FinanceFlow", page_icon="💰", layout="wide")

# Estilos CSS para parecer una App Móvil
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .main { background-color: #f0f2f5; padding-top: 0rem; }
    .stTabs [data-baseweb="tab-list"] {
        position: fixed; bottom: 0; left: 0; right: 0; background: white;
        z-index: 1000; border-top: 1px solid #ddd; padding: 10px 0;
        display: flex; justify-content: space-around;
    }
    .card {
        background: white; padding: 20px; border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 15px;
    }
    .total-card {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        color: white; padding: 30px; border-radius: 20px; text-align: center;
        margin-bottom: 20px;
    }
    .btn-cat {
        background: white; border: 1px solid #ddd; border-radius: 10px;
        padding: 15px; text-align: center; cursor: pointer; height: 80px;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        st.error("Error de conexión. Revisa los Secrets.")
        return None

supabase = init_connection()

# --- CARGA DE DATOS SEGURA ---
def load_data(table, default_cols):
    try:
        res = supabase.table(table).select("*").execute()
        df = pd.DataFrame(res.data)
        if df.empty:
            return pd.DataFrame(columns=default_cols)
        return df
    except:
        return pd.DataFrame(columns=default_cols)

# Cargar datos con columnas por defecto para evitar el KeyError
acc_df = load_data("accounts", ["id", "name", "type", "balance"])
cat_df = load_data("categories", ["id", "name", "monthly_limit"])
tx_df = load_data("transactions", ["amount", "category_id"])

# --- NAVEGACIÓN SUPERIOR (Para móvil) ---
menu = st.tabs(["🏠 Inicio", "💳 Cartera", "📈 Inversión", "➕ Añadir", "⚙️ Ajustes"])

# ----------------- 🏠 INICIO -----------------
with menu[0]:
    st.markdown("<br>", unsafe_allow_html=True)
    total_net = acc_df["balance"].astype(float).sum() if not acc_df.empty else 0.0
    
    st.markdown(f"""
        <div class="total-card">
            <p style="margin:0; font-size:14px; opacity:0.8;">Patrimonio Neto</p>
            <h1 style="margin:0; font-size:40px;">{total_net:,.2f} €</h1>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        liq = acc_df[acc_df["type"]=="liquid"]["balance"].sum() if not acc_df.empty else 0
        st.metric("Líquido", f"{liq:,.0f} €")
    with col2:
        inv = acc_df[acc_df["type"]=="investment"]["balance"].sum() if not acc_df.empty else 0
        st.metric("Invertido", f"{inv:,.0f} €")

    st.subheader("Tu Presupuesto")
    if not cat_df.empty:
        for _, cat in cat_df.iterrows():
            spent = tx_df[tx_df["category_id"] == cat["id"]]["amount"].sum() if not tx_df.empty else 0
            limit = float(cat["monthly_limit"])
            if limit > 0:
                perc = min(spent/limit, 1.0)
                st.write(f"**{cat['name']}**")
                color = "green" if perc < 0.8 else "orange" if perc < 1 else "red"
                st.progress(perc)
                st.caption(f"{spent:,.0f}€ de {limit:,.0f}€")

# ----------------- 💳 CARTERA -----------------
with menu[1]:
    st.subheader("Cuentas y Bancos")
    if not acc_df.empty:
        for _, row in acc_df[acc_df["type"]=="liquid"].iterrows():
            st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between;">
                        <b>{row['name']}</b>
                        <span style="color:#28a745; font-weight:bold;">{row['balance']:,.2f} €</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No hay cuentas. Ve a Ajustes.")

# ----------------- 📈 INVERSIÓN -----------------
with menu[2]:
    st.subheader("Inversiones Detalladas")
    brokers = acc_df[acc_df["type"]=="investment"] if not acc_df.empty else pd.DataFrame()
    
    if not brokers.empty:
        for _, broker in brokers.iterrows():
            with st.expander(f"🏦 {broker['name']}: {broker['balance']:,.2f} €"):
                # Aquí irían los activos de la tabla 'assets'
                st.caption("Actualizar valor de este broker:")
                val = st.number_input("Nuevo valor", key=f"inv_{broker['id']}", value=float(broker['balance']))
                if st.button("Actualizar", key=f"btn_{broker['id']}"):
                    supabase.table("accounts").update({"balance": val}).eq("id", broker["id"]).execute()
                    st.rerun()
    else:
        st.info("Añade brokers en Ajustes.")

# ----------------- ➕ AÑADIR (CALCULADORA) -----------------
with menu[3]:
    st.subheader("Nuevo Gasto")
    
    with st.form("form_gasto", clear_on_submit=True):
        monto = st.number_input("¿Cuánto has gastado? (€)", min_value=0.0, step=1.0)
        
        # Grid de categorías (Simulado con select para rapidez móvil)
        cat_options = cat_df["name"].tolist() if not cat_df.empty else ["General"]
        categoria = st.selectbox("Categoría", cat_options)
        
        acc_options = acc_df[acc_df["type"]=="liquid"]["name"].tolist() if not acc_df.empty else ["Efectivo"]
        cuenta = st.selectbox("¿De dónde sale el dinero?", acc_options)
        
        # Split logic
        st.write("---")
        es_split = st.toggle("¿Es compartido / Me deben algo?")
        monto_amigo = st.number_input("Monto que me deben", min_value=0.0) if es_split else 0
        
        if st.form_submit_button("REGISTRAR GASTO", use_container_width=True):
            if not acc_df.empty and not cat_df.empty:
                # Lógica de actualización
                acc = acc_df[acc_df["name"]==cuenta].iloc[0]
                cat = cat_df[cat_df["name"]==categoria].iloc[0]
                
                # Restar saldo
                nuevo_saldo = float(acc["balance"]) - monto
                supabase.table("accounts").update({"balance": nuevo_saldo}).eq("id", acc["id"]).execute()
                
                # Guardar transacción
                supabase.table("transactions").insert({
                    "amount": monto, "account_id": acc["id"], "category_id": cat["id"],
                    "description": categoria, "is_provision": es_split, "provision_amount": monto_amigo
                }).execute()
                
                st.success("¡Guardado!")
                st.rerun()

# ----------------- ⚙️ AJUSTES -----------------
with menu[4]:
    st.subheader("Configuración")
    
    with st.expander("➕ Añadir Nueva Cuenta/Banco"):
        nombre = st.text_input("Nombre de la cuenta")
        tipo = st.selectbox("Tipo", ["liquid", "investment"])
        if st.button("Crear Cuenta"):
            supabase.table("accounts").insert({"name": nombre, "type": tipo, "balance": 0}).execute()
            st.rerun()
            
    with st.expander("🎨 Añadir Nueva Categoría"):
        n_cat = st.text_input("Nombre de categoría")
        limite = st.number_input("Presupuesto mensual", min_value=0)
        if st.button("Crear Categoría"):
            supabase.table("categories").insert({"name": n_cat, "monthly_limit": limite}).execute()
            st.rerun()

    st.write("---")
    if st.button("Cerrar Sesión (Simulado)"):
        st.info("Para salir simplemente cierra la pestaña.")
