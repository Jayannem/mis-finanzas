import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import os

# --- Configuration ---
st.set_page_config(page_title="FinanceFlow", page_icon="💸", layout="wide")

# --- Database Connection ---
@st.cache_resource
def init_connection():
    # Load from Streamlit secrets (local .streamlit/secrets.toml or Streamlit Cloud)
    url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    key = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))
    if not url or not key:
        st.warning("⚠️ Credentials for Supabase are missing. Configure them in st.secrets.")
        return None
    return create_client(url, key)

supabase = init_connection()

# --- Helper Functions ---
def fetch_data(table):
    if supabase:
        response = supabase.table(table).select("*").execute()
        return pd.DataFrame(response.data)
    return pd.DataFrame()

def execute_query(table, data):
    if supabase:
        supabase.table(table).insert(data).execute()

# --- Shared Data ---
accounts_df = fetch_data("accounts")
categories_df = fetch_data("categories")

# --- UI & Sidebar Navigation ---
st.sidebar.title("💸 FinanceFlow")
page = st.sidebar.radio("Navegación", [
    "Dashboard (Net Worth)", 
    "Líquido & Split", 
    "Inversiones", 
    "Planner Mensual", 
    "Ajustes"
])

# ----------------- ROUTING -----------------

if page == "Dashboard (Net Worth)":
    st.title("Vista General (Dinámica de Patrimonio)")
    
    if not accounts_df.empty:
        liquid = accounts_df[accounts_df['type'] == 'liquid']['balance'].sum()
        invested = accounts_df[accounts_df['type'] == 'investment']['balance'].sum()
        pending = accounts_df[accounts_df['type'] == 'pending']['balance'].sum()
        total = liquid + invested + pending
        
        # Upper Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Patrimonio Total", f"{total:,.2f} €")
        col2.metric("Líquido", f"{liquid:,.2f} €")
        col3.metric("Inversiones", f"{invested:,.2f} €")
        col4.metric("Pendiente de Cobro", f"{pending:,.2f} €")
        
        # Portfolio Drill-Down
        st.write("---")
        c1, c2 = st.columns([1, 1])
        with c1:
            fig = px.pie(
                names=['Líquido', 'Inversiones', 'Pendiente de Cobro'],
                values=[liquid, invested, pending],
                title="Composición del Patrimonio",
                hole=0.4
            )
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.subheader("Desglose Rápido")
            tab1, tab2, tab3 = st.tabs(["Líquido", "Inversiones", "Presupuesto"])
            with tab1:
                st.dataframe(accounts_df[accounts_df['type'] == 'liquid'][['name', 'balance']], hide_index=True)
            with tab2:
                st.dataframe(accounts_df[accounts_df['type'] == 'investment'][['name', 'balance']], hide_index=True)
            with tab3:
                # Placeholder for monthly spending per category
                st.info("Para ver tus gastos vs límites mensuales, ve a la pestaña de Planner Mensual.")


elif page == "Líquido & Split":
    st.title("Registro de Gastos & Provisión (Split)")
    
    # 1. Show Liquid Balances
    st.subheader("Tus saldos disponibles")
    if not accounts_df.empty:
        liquid_accs = accounts_df[accounts_df['type'] == 'liquid']
        cols = st.columns(len(liquid_accs) if len(liquid_accs) > 0 else 1)
        for i, row in enumerate(liquid_accs.itertuples()):
            cols[i % len(cols)].metric(row.name, f"{row.balance:.2f} €")
            
    st.write("---")
    
    # 2. Transaction Form
    st.subheader("Añadir nueva transacción")
    with st.form("new_transaction"):
        desc = st.text_input("Descripción del gasto/ingreso")
        amount = st.number_input("Pago Total (€)", min_value=0.0, step=1.0)
        
        acc_list = liquid_accs['name'].tolist() if not accounts_df.empty else []
        account_name = st.selectbox("Cuenta de Origen (-)", acc_list)
        
        cat_list = categories_df['name'].tolist() if not categories_df.empty else []
        category_name = st.selectbox("Categoría de Presupuesto", cat_list)
        
        # THE SPLIT TOGGLE
        st.markdown("##### Opciones de Cobro Compartido")
        is_provision = st.checkbox("Provisión (Alguien me debe parte de esto)")
        provision_amount = st.number_input("Parte que NO es tuya (€)", min_value=0.0, step=1.0, help="Esta cantidad se restará del banco, pero sumará a 'Pendiente de cobro'") if is_provision else 0.0
        
        submitted = st.form_submit_button("Registrar Transacción")
        
        if submitted and supabase:
            # Gather IDs
            acc_id = liquid_accs[liquid_accs['name'] == account_name].iloc[0]['id']
            cat_id = categories_df[categories_df['name'] == category_name].iloc[0]['id']
            
            # --- DOUBLE ENTRY LOGIC ---
            
            # 1. Deduct full amount from origin account
            current_balance = liquid_accs[liquid_accs['id'] == acc_id].iloc[0]['balance']
            supabase.table('accounts').update({'balance': float(current_balance) - amount}).eq('id', acc_id).execute()
            
            # 2. If provision, create debt asset in "Pendiente de cobro"
            if is_provision and provision_amount > 0:
                pending_acc = accounts_df[accounts_df['type'] == 'pending'].iloc[0]
                new_pending_bal = float(pending_acc['balance']) + provision_amount
                supabase.table('accounts').update({'balance': new_pending_bal}).eq('id', pending_acc['id']).execute()
            
            # 3. Save Ledger Transaction (only the portion that is YOURS counts towards your budget conceptually)
            execute_query("transactions", {
                "description": desc,
                "amount": amount,
                "account_id": acc_id,
                "category_id": cat_id,
                "is_provision": is_provision,
                "provision_amount": provision_amount
            })
            
            st.success(f"Transacción registrada. Tu cuenta bajó en {amount}€.")
            if is_provision: st.info(f"Has marcado {provision_amount}€ como deuda a tu favor.")
            st.rerun()

elif page == "Inversiones":
    st.title("Módulo de Inversiones y Market Snapshots")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Tomar un 'Snapshot'")
        st.caption("Actualiza el valor actual de un broker o fondo.")
        with st.form("snapshot"):
            inv_accs = accounts_df[accounts_df['type'] == 'investment']
            if inv_accs.empty:
                st.warning("No hay cuentas de inversión creadas. Ve a Ajustes.")
            else:
                acc_name = st.selectbox("Activo / Cuenta", inv_accs['name'].tolist())
                new_value = st.number_input("Nuevo Valor Total de la cartera (€)", min_value=0.0)
                
                if st.form_submit_button("Guardar Snapshot") and supabase:
                    acc_id = inv_accs[inv_accs['name'] == acc_name].iloc[0]['id']
                    # Log history & update active balance
                    execute_query("investment_snapshots", {"account_id": acc_id, "total_value": new_value})
                    supabase.table('accounts').update({'balance': new_value}).eq('id', acc_id).execute()
                    st.success("Snapshot registrado correctamente")
                    st.rerun()
            
    with col2:
        st.subheader("Composición & Rendimiento")
        snapshots = fetch_data("investment_snapshots")
        if not snapshots.empty and not inv_accs.empty:
            merged = pd.merge(snapshots, accounts_df, left_on='account_id', right_on='id')
            fig = px.line(merged, x='snapshot_date', y='total_value', color='name_y', title="Histórico de Carteras", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Registra un snapshot para ver los gráficos de evolución.")

elif page == "Planner Mensual":
    st.title("Planificador de Categorías")
    st.markdown("Día 1 del mes: Evalúa tus límites mensuales.")
    
    transactions_df = fetch_data("transactions")
    if not categories_df.empty:
        for idx, row in categories_df.iterrows():
            c1, c2, c3 = st.columns([3, 1, 2])
            limit_val = float(row['monthly_limit'])
            
            c1.markdown(f"**{row['name']}**")
            c2.write(f"Límite: {limit_val} €")
            
            # Substract spent (discounting provisions to show real personal spend)
            spent = 0.0
            if not transactions_df.empty:
                cat_txs = transactions_df[transactions_df['category_id'] == row['id']]
                # Amount - Provision (if applied) = Real Spend
                # Assuming all are expenses for simplicity
                real_spend = (cat_txs['amount'] - cat_txs['provision_amount']).sum()
                spent = real_spend
                
            progress = min(spent / limit_val, 1.0) if limit_val > 0 else 0.0
            color = "normal" if progress < 0.8 else "inverse"
            
            c3.progress(progress)
            
        st.write("---")
        st.caption("Nota: El progreso descuenta tus 'splits' para que la deuda ajena no afecte tu límite de presupuesto personal.")

elif page == "Ajustes":
    st.title("Configuración Global")
    
    st.markdown("Añade dinámicamente nuevas cuentas, activos de inversión o categorías.")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Nueva Cuenta de Dinero")
        with st.form("new_acc"):
            n = st.text_input("Nombre de cuenta (o Banco)")
            t = st.selectbox("Tipo de liquidez", ["liquid", "investment"])
            if st.form_submit_button("Crear Cuenta") and supabase:
                execute_query("accounts", {"name": n, "type": t})
                st.success(f"{t.capitalize()} creada.")
                st.rerun()
                
    with c2:
        st.subheader("Nueva Categoría")
        with st.form("new_cat"):
            n = st.text_input("Nombre (Ej. Ropa, Mascotas)")
            limit = st.number_input("Límite Mensual Estimado (€)", min_value=0.0)
            if st.form_submit_button("Añadir Categoría") and supabase:
                execute_query("categories", {"name": n, "monthly_limit": limit})
                st.success("Categoría añadida.")
                st.rerun()
