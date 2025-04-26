"""
ORION PDV - Sistema de Ponto de Venda Modular
Versão com estrutura modular e organizada para PostgreSQL
"""

import streamlit as st
from database import init_database
from config import APP_CONFIG
from views import mostrar_pdv, mostrar_produtos, mostrar_categorias, mostrar_relatorios

# Configurações de página
st.set_page_config(
    page_title=APP_CONFIG["title"],
    page_icon=APP_CONFIG["icon"],
    layout=APP_CONFIG["layout"],
    initial_sidebar_state=APP_CONFIG["sidebar_state"]
)

# Inicializar o banco de dados
init_database()

# Interface do usuário com Streamlit
def main():
    # Inicialização de variáveis de sessão
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'
    if 'cart' not in st.session_state:
        st.session_state.cart = []
    if 'last_barcode' not in st.session_state:
        st.session_state.last_barcode = None
    if 'barcode_detected' not in st.session_state:
        st.session_state.barcode_detected = False
    
    # Barra lateral para navegação
    with st.sidebar:
        st.title(f"{APP_CONFIG['icon']} {APP_CONFIG['title']}")
        st.markdown("---")
        
        if st.button("📋 PDV", use_container_width=True):
            st.session_state.current_page = 'pdv'
        
        if st.button("📦 Produtos", use_container_width=True):
            st.session_state.current_page = 'produtos'
        
        if st.button("🏷️ Categorias", use_container_width=True):
            st.session_state.current_page = 'categorias'
        
        if st.button("📊 Relatórios", use_container_width=True):
            st.session_state.current_page = 'relatorios'
        
        st.markdown("---")
        st.caption(f"© {APP_CONFIG['year']} {APP_CONFIG['company']}")
        st.caption(f"Versão {APP_CONFIG['version']}")
    
    # Exibir páginas de acordo com a navegação
    if st.session_state.current_page == 'home':
        mostrar_pdv()  # Mostrar PDV como página inicial
    elif st.session_state.current_page == 'pdv':
        mostrar_pdv()
    elif st.session_state.current_page == 'produtos':
        mostrar_produtos()
    elif st.session_state.current_page == 'categorias':
        mostrar_categorias()
    elif st.session_state.current_page == 'relatorios':
        mostrar_relatorios()

if __name__ == "__main__":
    main()
