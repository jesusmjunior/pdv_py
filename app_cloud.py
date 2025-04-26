import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
import datetime
import base64

# Configuração da página
st.set_page_config(
    page_title="BarcodeScan PDV",
    page_icon="🛒",
    layout="wide"
)

# Configuração do banco de dados PostgreSQL - conexão direta
@st.cache_resource
def init_connection():
    try:
        return psycopg2.connect(
            host="34.95.252.164",
            database="pdv",
            user="postgres",
            password="pdv@2025",
            port="5432",
            sslmode="require"
        )
    except Exception as e:
        st.error(f"Erro de conexão com banco de dados: {str(e)}")
        return None

# Função para executar consultas SQL
@st.cache_data(ttl=5)
def run_query(query, params=None):
    conn = init_connection()
    if conn is None:
        return None
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if query.strip().upper().startswith("SELECT"):
                return [dict(row) for row in cur.fetchall()]
            else:
                conn.commit()
                if cur.rowcount > 0:
                    return cur.rowcount
                if hasattr(cur, 'lastrowid'):
                    return cur.lastrowid
                return True
    except Exception as e:
        st.error(f"Erro na consulta: {str(e)}")
        return None

# API para buscar produto pelo código de barras
def get_product_by_barcode(barcode):
    if not barcode:
        return None
        
    query = """
        SELECT p.*, c.nome as categoria_nome 
        FROM produtos p 
        LEFT JOIN categorias c ON p.categoria_id = c.id 
        WHERE (p.codigo_barras = %s OR p.codigo = %s) 
        AND p.ativo = true
        LIMIT 1
    """
    
    products = run_query(query, (barcode, barcode))
    
    if products and len(products) > 0:
        product = products[0]
        # Atualizar timestamp de leitura
        update_query = """
            UPDATE produtos 
            SET ultima_leitura = CURRENT_TIMESTAMP 
            WHERE id = %s
        """
        run_query(update_query, (product['id'],))
        return product
    
    return None

# Obter todos os produtos
def get_all_products():
    query = """
        SELECT p.*, c.nome as categoria_nome 
        FROM produtos p 
        LEFT JOIN categorias c ON p.categoria_id = c.id 
        WHERE p.ativo = true 
        ORDER BY p.nome
    """
    
    return run_query(query) or []

# Criar venda
def create_sale(items, customer_name, payment_method):
    if not items:
        return False, "Carrinho vazio"
    
    # 1. Inserir venda
    total = sum(item['preco_venda'] * item['quantidade'] for item in items)
    
    insert_query = """
        INSERT INTO vendas 
        (cliente_nome, valor_total, forma_pagamento, status) 
        VALUES (%s, %s, %s, 'concluida') 
        RETURNING id
    """
    
    result = run_query(insert_query, (customer_name, total, payment_method))
    
    if not result:
        return False, "Falha ao criar venda"
    
    venda_id = result[0]['id'] if isinstance(result, list) else result
    
    # 2. Inserir itens e atualizar estoque
    for item in items:
        # Inserir item na venda
        item_query = """
            INSERT INTO venda_itens 
            (venda_id, produto_id, quantidade, preco_unitario) 
            VALUES (%s, %s, %s, %s)
        """
        run_query(item_query, (venda_id, item['id'], item['quantidade'], item['preco_venda']))
        
        # Atualizar estoque
        update_query = """
            UPDATE produtos 
            SET estoque = estoque - %s 
            WHERE id = %s
        """
        run_query(update_query, (item['quantidade'], item['id']))
    
    return True, venda_id

# Gerar recibo HTML
def generate_receipt_html(sale_id, items, customer_name, payment_method, total):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Recibo #{sale_id}</title>
        <style>
            body {{ font-family: Arial; margin: 0; padding: 20px; }}
            .receipt {{ max-width: 800px; margin: 0 auto; border: 1px solid #ddd; padding: 20px; }}
            .header {{ text-align: center; margin-bottom: 20px; border-bottom: 2px solid #333; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            .total {{ text-align: right; font-weight: bold; margin-top: 20px; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #777; }}
        </style>
    </head>
    <body>
        <div class="receipt">
            <div class="header">
                <h1>BarcodeScan PDV</h1>
                <h2>Recibo de Venda #{sale_id}</h2>
                <p>Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                <p>Cliente: {customer_name or 'Cliente não identificado'}</p>
                <p>Forma de Pagamento: {payment_method}</p>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Produto</th>
                        <th>Código</th>
                        <th>Qtde</th>
                        <th>Preço Unit.</th>
                        <th>Subtotal</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for item in items:
        html += f"""
                    <tr>
                        <td>{item['nome']}</td>
                        <td>{item.get('codigo_barras', 'N/A')}</td>
                        <td>{item['quantidade']}</td>
                        <td>R$ {item['preco_venda']:.2f}</td>
                        <td>R$ {item['preco_venda'] * item['quantidade']:.2f}</td>
                    </tr>
        """
    
    html += f"""
                </tbody>
            </table>
            
            <div class="total">
                <p>Total: R$ {total:.2f}</p>
            </div>
            
            <div class="footer">
                <p>Obrigado por sua compra!</p>
                <p>BarcodeScan PDV - Sistema de Gestão com Leitura de Código de Barras</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

# Link para download de recibo
def get_receipt_download_link(html, filename="recibo.html"):
    b64 = base64.b64encode(html.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="{filename}">Baixar Recibo</a>'
    return href

# Interface principal
def main():
    # Sidebar
    st.sidebar.title("BarcodeScan PDV")
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/1051/1051264.png", width=100)
    
    menu = st.sidebar.radio(
        "Menu", 
        ["Dashboard", "Escanear", "Produtos", "Vendas"]
    )
    
    # Dashboard simples
    if menu == "Dashboard":
        st.title("Dashboard")
        
        # Estatísticas básicas
        products = get_all_products()
        
        # Contagem de produtos
        total_products = len(products)
        
        # Produtos com estoque baixo
        low_stock = [p for p in products if p.get('estoque', 0) <= p.get('estoque_minimo', 0)]
        
        # Valor total em estoque
        total_value = sum(p.get('preco_venda', 0) * p.get('estoque', 0) for p in products)
        
        # Exibir métricas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total de Produtos", f"{total_products}")
        
        with col2:
            st.metric("Produtos com Estoque Baixo", f"{len(low_stock)}")
        
        with col3:
            st.metric("Valor em Estoque", f"R$ {total_value:.2f}")
            
        # Lista de produtos com estoque baixo
        if low_stock:
            st.subheader("Produtos com Estoque Baixo")
            
            low_stock_data = []
            for p in low_stock:
                low_stock_data.append({
                    "Nome": p['nome'],
                    "Estoque": p.get('estoque', 0),
                    "Mínimo": p.get('estoque_minimo', 0),
                    "Preço": f"R$ {float(p.get('preco_venda', 0)):.2f}"
                })
            
            st.table(pd.DataFrame(low_stock_data))
    
    # Página de Escaneamento
    elif menu == "Escanear":
        st.title("Leitura de Código de Barras")
        
        barcode_input = st.text_input("Digite o código de barras", 
                                     placeholder="EAN, código interno, etc.")
        
        if st.button("Buscar Produto") or barcode_input:
            if barcode_input:
                product = get_product_by_barcode(barcode_input)
                
                if product:
                    st.success(f"✅ Produto encontrado: {product['nome']}")
                    
                    # Exibir informações do produto
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("Dados do Produto")
                        st.write(f"**Nome:** {product['nome']}")
                        st.write(f"**Código:** {product.get('codigo', 'N/A')}")
                        st.write(f"**Código de Barras:** {product.get('codigo_barras', 'N/A')}")
                        st.write(f"**Categoria:** {product.get('categoria_nome', 'N/A')}")
                    
                    with col2:
                        st.subheader("Informações de Venda")
                        st.write(f"**Preço:** R$ {product['preco_venda']:.2f}")
                        st.write(f"**Estoque:** {product.get('estoque', 0)} {product.get('unidade', 'un')}")
                        
                        # Adicionar ao carrinho
                        quantidade = st.number_input("Quantidade", min_value=1, value=1)
                        
                        if st.button("Adicionar à Venda"):
                            if 'cart' not in st.session_state:
                                st.session_state.cart = []
                            
                            for i, item in enumerate(st.session_state.cart):
                                if item['id'] == product['id']:
                                    st.session_state.cart[i]['quantidade'] += quantidade
                                    break
                            else:
                                st.session_state.cart.append({
                                    'id': product['id'],
                                    'nome': product['nome'],
                                    'codigo_barras': product.get('codigo_barras', ''),
                                    'preco_venda': product['preco_venda'],
                                    'quantidade': quantidade
                                })
                            
                            st.success(f"{quantidade} unidade(s) de {product['nome']} adicionado ao carrinho!")
                else:
                    st.error("Produto não encontrado")
    
    # Listagem de Produtos
    elif menu == "Produtos":
        st.title("Catálogo de Produtos")
        
        # Busca simples
        search = st.text_input("Buscar produtos", placeholder="Nome ou código")
        
        # Listar produtos
        products = get_all_products()
        
        # Filtrar resultados
        if search:
            search = search.lower()
            products = [p for p in products if 
                       search in str(p.get('nome', '')).lower() or 
                       (p.get('codigo') and search in str(p['codigo']).lower()) or
                       (p.get('codigo_barras') and search in str(p['codigo_barras']).lower())]
        
        # Exibir produtos
        if not products:
            st.info("Nenhum produto encontrado")
        else:
            # Converter para DataFrame
            df_data = []
            for p in products:
                df_data.append({
                    "ID": p['id'],
                    "Nome": p.get('nome', ''),
                    "Código": p.get('codigo', ''),
                    "Código de Barras": p.get('codigo_barras', ''),
                    "Preço": f"R$ {float(p.get('preco_venda', 0)):.2f}",
                    "Estoque": p.get('estoque', 0)
                })
            
            # Exibir tabela
            st.dataframe(pd.DataFrame(df_data), use_container_width=True)
            
            # Adicionar à venda
            col1, col2 = st.columns(2)
            
            with col1:
                product_id = st.selectbox(
                    "Selecionar produto", 
                    options=[p['id'] for p in products],
                    format_func=lambda x: next((p.get('nome', '') for p in products if p['id'] == x), str(x))
                )
            
            with col2:
                quantidade = st.number_input("Quantidade", min_value=1, value=1)
            
            if st.button("Adicionar ao Carrinho"):
                product = next((p for p in products if p['id'] == product_id), None)
                
                if product:
                    if 'cart' not in st.session_state:
                        st.session_state.cart = []
                    
                    for i, item in enumerate(st.session_state.cart):
                        if item['id'] == product['id']:
                            st.session_state.cart[i]['quantidade'] += quantidade
                            break
                    else:
                        st.session_state.cart.append({
                            'id': product['id'],
                            'nome': product.get('nome', ''),
                            'codigo_barras': product.get('codigo_barras', ''),
                            'preco_venda': product.get('preco_venda', 0),
                            'quantidade': quantidade
                        })
                    
                    st.success(f"{quantidade} unidade(s) de {product.get('nome', '')} adicionado ao carrinho!")
    
    # Página de Vendas
    elif menu == "Vendas":
        st.title("Carrinho de Venda")
        
        # Inicializar carrinho
        if 'cart' not in st.session_state:
            st.session_state.cart = []
        
        # Exibir carrinho
        if not st.session_state.cart:
            st.info("Carrinho vazio. Adicione produtos nas páginas Escanear ou Produtos.")
        else:
            # Criar DataFrame do carrinho
            cart_data = []
            for item in st.session_state.cart:
                cart_data.append({
                    "Produto": item['nome'],
                    "Código": item.get('codigo_barras', ''),
                    "Preço": f"R$ {item['preco_venda']:.2f}",
                    "Quantidade": item['quantidade'],
                    "Subtotal": f"R$ {item['preco_venda'] * item['quantidade']:.2f}"
                })
            
            # Exibir tabela
            st.table(pd.DataFrame(cart_data))
            
            # Opções para alterar quantidades
            st.subheader("Ajustar Quantidades")
            
            for i, item in enumerate(st.session_state.cart):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.text(f"{item['nome']}")
                
                with col2:
                    new_qty = st.number_input(f"Qtd", 
                                           min_value=1, 
                                           value=item['quantidade'], 
                                           key=f"qty_{i}")
                    
                    if new_qty != item['quantidade']:
                        st.session_state.cart[i]['quantidade'] = new_qty
                
                with col3:
                    if st.button("Remover", key=f"rem_{i}"):
                        st.session_state.cart.pop(i)
                        st.experimental_rerun()
            
            # Total
            total = sum(item['preco_venda'] * item['quantidade'] for item in st.session_state.cart)
            st.subheader(f"Total: R$ {total:.2f}")
            
            # Finalizar venda
            st.subheader("Finalizar Venda")
            col1, col2 = st.columns(2)
            
            with col1:
                customer_name = st.text_input("Nome do Cliente (opcional)")
            
            with col2:
                payment_method = st.selectbox(
                    "Forma de Pagamento",
                    ["Dinheiro", "Cartão de Crédito", "Cartão de Débito", "PIX"]
                )
            
            if st.button("Concluir Venda", type="primary"):
                success, result = create_sale(
                    st.session_state.cart,
                    customer_name,
                    payment_method
                )
                
                if success:
                    st.success("Venda realizada com sucesso!")
                    st.balloons()
                    
                    # Recibo
                    receipt_html = generate_receipt_html(
                        result,
                        st.session_state.cart,
                        customer_name,
                        payment_method,
                        total
                    )
                    
                    st.markdown(
                        get_receipt_download_link(
                            receipt_html, 
                            f"recibo_{result}.html"
                        ),
                        unsafe_allow_html=True
                    )
                    
                    # Limpar carrinho
                    st.session_state.cart = []
                else:
                    st.error(f"Erro ao processar venda: {result}")
            
            if st.button("Limpar Carrinho"):
                st.session_state.cart = []
                st.experimental_rerun()

# Executar o app
if __name__ == "__main__":
    main()