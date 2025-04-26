import streamlit as st
import sqlite3
import pandas as pd
import json
import datetime
import base64
import os
from urllib.parse import quote

# Configuração da página
st.set_page_config(
    page_title="BarcodeScan PDV",
    page_icon="🛒",
    layout="wide"
)

# Usar SQLite em vez de PostgreSQL (biblioteca nativa)
# Armazenamento local para simulação sem banco externo
DB_PATH = "pdv_local.db"

# Inicializar banco de dados SQLite (nativo do Python)
@st.cache_resource
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    # Criar tabelas se não existirem
    c.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            codigo TEXT,
            codigo_barras TEXT,
            descricao TEXT,
            preco_custo REAL DEFAULT 0,
            preco_venda REAL NOT NULL,
            estoque INTEGER DEFAULT 0,
            estoque_minimo INTEGER DEFAULT 5,
            categoria_id INTEGER,
            unidade TEXT DEFAULT 'un',
            ativo INTEGER DEFAULT 1
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY,
            cliente_nome TEXT,
            valor_total REAL NOT NULL,
            forma_pagamento TEXT,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'concluida'
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS venda_itens (
            id INTEGER PRIMARY KEY,
            venda_id INTEGER,
            produto_id INTEGER,
            quantidade INTEGER NOT NULL,
            preco_unitario REAL NOT NULL,
            FOREIGN KEY (venda_id) REFERENCES vendas (id),
            FOREIGN KEY (produto_id) REFERENCES produtos (id)
        )
    ''')
    
    # Inserir dados de exemplo se tabela estiver vazia
    c.execute("SELECT COUNT(*) FROM produtos")
    if c.fetchone()[0] == 0:
        # Inserir algumas categorias
        categorias = [
            (1, "Alimentos"),
            (2, "Bebidas"),
            (3, "Limpeza"),
            (4, "Higiene Pessoal")
        ]
        c.executemany("INSERT INTO categorias (id, nome) VALUES (?, ?)", categorias)
        
        # Inserir alguns produtos de exemplo
        produtos = [
            (1, "Arroz 5kg", "P001", "7896254301245", "Arroz tipo 1", 15.50, 21.90, 50, 10, 1, "pct"),
            (2, "Feijão 1kg", "P002", "7896254302245", "Feijão carioca", 6.50, 9.90, 40, 8, 1, "pct"),
            (3, "Óleo de Soja", "P003", "7896254303245", "Óleo de soja 900ml", 5.20, 8.50, 45, 10, 1, "un"),
            (4, "Água Mineral 500ml", "P004", "7896254304245", "Água sem gás", 0.75, 2.50, 100, 20, 2, "un"),
            (5, "Refrigerante Cola 2L", "P005", "7896254305245", "Refrigerante sabor cola", 5.50, 8.90, 30, 8, 2, "un"),
            (6, "Detergente 500ml", "P006", "7896254306245", "Detergente líquido", 1.80, 3.50, 25, 5, 3, "un"),
            (7, "Sabão em Pó 1kg", "P007", "7896254307245", "Sabão em pó", 8.75, 15.90, 20, 5, 3, "un"),
            (8, "Papel Higiênico 4un", "P008", "7896254308245", "Pacote com 4 rolos", 5.25, 9.50, 40, 8, 4, "pct"),
            (9, "Sabonete", "P009", "7896254309245", "Sabonete 90g", 1.20, 2.75, 60, 12, 4, "un"),
            (10, "Shampoo 350ml", "P010", "7896254310245", "Shampoo para todos os tipos de cabelo", 7.90, 15.90, 18, 5, 4, "un")
        ]
        c.executemany('''
            INSERT INTO produtos 
            (id, nome, codigo, codigo_barras, descricao, preco_custo, preco_venda, 
            estoque, estoque_minimo, categoria_id, unidade) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', produtos)
    
    conn.commit()
    return conn

# Executar consultas SQL
def run_query(query, params=(), fetch=True):
    conn = init_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute(query, params)
        
        if fetch:
            columns = [desc[0] for desc in cursor.description]
            results = cursor.fetchall()
            
            # Converter para lista de dicionários
            return [dict(zip(columns, row)) for row in results]
        else:
            conn.commit()
            if cursor.lastrowid:
                return cursor.lastrowid
            return cursor.rowcount
    except Exception as e:
        st.error(f"Erro na consulta: {str(e)}")
        return None

# API para buscar produto pelo código de barras
@st.cache_data(ttl=5)
def get_product_by_barcode(barcode):
    if not barcode:
        return None
        
    query = """
        SELECT p.*, c.nome as categoria_nome 
        FROM produtos p 
        LEFT JOIN categorias c ON p.categoria_id = c.id 
        WHERE (p.codigo_barras = ? OR p.codigo = ?) 
        AND p.ativo = 1
        LIMIT 1
    """
    
    products = run_query(query, (barcode, barcode))
    
    if products and len(products) > 0:
        return products[0]
    
    return None

# Obter todos os produtos
@st.cache_data(ttl=5)
def get_all_products():
    query = """
        SELECT p.*, c.nome as categoria_nome 
        FROM produtos p 
        LEFT JOIN categorias c ON p.categoria_id = c.id 
        WHERE p.ativo = 1
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
        VALUES (?, ?, ?, 'concluida')
    """
    
    sale_id = run_query(insert_query, (customer_name, total, payment_method), fetch=False)
    
    if not sale_id:
        return False, "Falha ao criar venda"
    
    # 2. Inserir itens e atualizar estoque
    for item in items:
        # Inserir item na venda
        item_query = """
            INSERT INTO venda_itens 
            (venda_id, produto_id, quantidade, preco_unitario) 
            VALUES (?, ?, ?, ?)
        """
        run_query(item_query, (sale_id, item['id'], item['quantidade'], item['preco_venda']), fetch=False)
        
        # Atualizar estoque
        update_query = """
            UPDATE produtos 
            SET estoque = estoque - ? 
            WHERE id = ?
        """
        run_query(update_query, (item['quantidade'], item['id']), fetch=False)
    
    # Limpar cache para refletir as alterações
    get_all_products.clear()
    
    return True, sale_id

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
        
        if st.button("Buscar Produto", type="primary") or barcode_input:
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