import streamlit as st
import psycopg2
import psycopg2.extras
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from PIL import Image
import io
import os
from dotenv import load_dotenv
import socket

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da página
st.set_page_config(
    page_title="BarcodeScan PDV - Sistema de Gestão de Vendas",
    page_icon="🛒",
    layout="wide"
)

# Configuração do banco de dados PostgreSQL no Google Cloud
def get_db_connection():
    # Configurações diretas para o PostgreSQL do Google Cloud
    try:
        conn = psycopg2.connect(
            host="34.95.252.164",  # IP da instância Cloud SQL
            database="pdv",
            user="postgres",
            password="pdv@2025",
            port="5432",
            sslmode="require"  # Para conexão segura
        )
        
        conn.autocommit = True
        return conn
        
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        print(f"Erro de conexão: {str(e)}")
        print(f"Ambiente: {socket.gethostname()}")
        raise e

# Função para decodificar códigos de barras em imagens
def decode_barcode(image):
    if image is not None:
        # Converter imagem para OpenCV
        if isinstance(image, Image.Image):
            image = np.array(image.convert('RGB'))
        
        # Converter para escala de cinza
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Decodificar os códigos de barras
        barcodes = decode(gray)
        
        if barcodes:
            return barcodes[0].data.decode('utf-8')
    
    return None

# Função para buscar produto por código de barras
def get_product_by_barcode(barcode):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Busca otimizada com correspondência parcial
        cursor.execute("""
            SELECT p.*, c.nome as categoria_nome 
            FROM produtos p 
            LEFT JOIN categorias c ON p.categoria_id = c.id 
            WHERE (
                p.codigo_barras = %s 
                OR p.codigo = %s 
                OR p.codigo_barras LIKE %s
                OR replace(p.codigo_barras, '-', '') = replace(%s, '-', '')
            ) AND p.ativo = true
            LIMIT 1
        """, (barcode, barcode, f"%{barcode}%", barcode))
        
        product = cursor.fetchone()
        
        if product:
            # Registrar timestamp da última leitura
            cursor.execute("""
                UPDATE produtos 
                SET ultima_leitura = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (product['id'],))
            
            return dict(product)
        
        return None
    
    finally:
        cursor.close()
        conn.close()

# Função para obter todos os produtos
def get_all_products():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cursor.execute("""
            SELECT p.*, c.nome as categoria_nome 
            FROM produtos p 
            LEFT JOIN categorias c ON p.categoria_id = c.id 
            WHERE p.ativo = true 
            ORDER BY p.nome
        """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    finally:
        cursor.close()
        conn.close()

# Função para criar um produto
def create_product(produto):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Verificar se código já existe
        if produto.get('codigo'):
            cursor.execute("SELECT id FROM produtos WHERE codigo = %s", (produto['codigo'],))
            if cursor.fetchone():
                return False, "Código já está em uso"
        
        # Verificar se código de barras já existe
        if produto.get('codigo_barras'):
            cursor.execute("SELECT id FROM produtos WHERE codigo_barras = %s", (produto['codigo_barras'],))
            if cursor.fetchone():
                return False, "Código de barras já está em uso"
        
        # Inserir novo produto
        cursor.execute("""
            INSERT INTO produtos 
            (codigo, codigo_barras, nome, descricao, preco_custo, preco_venda, 
            estoque, estoque_minimo, categoria_id, unidade) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
            RETURNING *
        """, (
            produto.get('codigo'),
            produto.get('codigo_barras'),
            produto['nome'],
            produto.get('descricao'),
            produto.get('preco_custo', 0),
            produto['preco_venda'],
            produto.get('estoque', 0),
            produto.get('estoque_minimo', 5),
            produto.get('categoria_id'),
            produto.get('unidade', 'un')
        ))
        
        return True, dict(cursor.fetchone())
    
    except Exception as e:
        return False, str(e)
    
    finally:
        cursor.close()
        conn.close()

# Função para atualizar um produto
def update_product(id, produto):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Verificar se produto existe
        cursor.execute("SELECT id FROM produtos WHERE id = %s", (id,))
        if not cursor.fetchone():
            return False, "Produto não encontrado"
        
        # Verificar se código já existe em outro produto
        if produto.get('codigo'):
            cursor.execute("SELECT id FROM produtos WHERE codigo = %s AND id != %s", 
                           (produto['codigo'], id))
            if cursor.fetchone():
                return False, "Código já está em uso por outro produto"
        
        # Verificar se código de barras já existe em outro produto
        if produto.get('codigo_barras'):
            cursor.execute("SELECT id FROM produtos WHERE codigo_barras = %s AND id != %s", 
                           (produto['codigo_barras'], id))
            if cursor.fetchone():
                return False, "Código de barras já está em uso por outro produto"
        
        # Atualizar produto
        cursor.execute("""
            UPDATE produtos SET 
                codigo = %s,
                codigo_barras = %s,
                nome = %s,
                descricao = %s,
                preco_custo = %s,
                preco_venda = %s,
                estoque = %s,
                estoque_minimo = %s,
                categoria_id = %s,
                ativo = %s,
                unidade = %s,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
        """, (
            produto.get('codigo'),
            produto.get('codigo_barras'),
            produto['nome'],
            produto.get('descricao'),
            produto.get('preco_custo', 0),
            produto['preco_venda'],
            produto.get('estoque', 0),
            produto.get('estoque_minimo', 5),
            produto.get('categoria_id'),
            produto.get('ativo', True),
            produto.get('unidade', 'un'),
            id
        ))
        
        return True, dict(cursor.fetchone())
    
    except Exception as e:
        return False, str(e)
    
    finally:
        cursor.close()
        conn.close()

# Função para obter categorias
def get_categories():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cursor.execute("SELECT id, nome FROM categorias WHERE ativo = true ORDER BY nome")
        return [dict(row) for row in cursor.fetchall()]
    
    finally:
        cursor.close()
        conn.close()

# Interface principal do aplicativo
def main():
    # Menu lateral
    st.sidebar.title("BarcodeScan PDV")
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/1051/1051264.png", width=100)
    menu = st.sidebar.selectbox(
        "Menu", 
        ["Início", "Escanear Produto", "Listar Produtos", "Cadastrar Produto", "Realizar Venda"]
    )
    
    # Página Inicial
    if menu == "Início":
        st.title("Bem-vindo ao BarcodeScan PDV")
        st.markdown("""
        ### Sistema Integrado de Gestão com Leitura de Código de Barras
        
        Este aplicativo permite:
        - Escanear e identificar produtos via código de barras
        - Gerenciar catálogo de produtos e controlar estoque
        - Realizar vendas com interface amigável
        - Integração com banco de dados na nuvem
        
        Selecione uma opção no menu lateral para começar.
        """)
        
        # Estatísticas na página inicial
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Produtos cadastrados
            cursor.execute("SELECT COUNT(*) FROM produtos WHERE ativo = true")
            produtos_count = cursor.fetchone()[0]
            
            # Produtos com estoque baixo
            cursor.execute("SELECT COUNT(*) FROM produtos WHERE ativo = true AND estoque <= estoque_minimo")
            estoque_baixo_count = cursor.fetchone()[0]
            
            # Valor total em estoque
            cursor.execute("SELECT SUM(estoque * preco_venda) FROM produtos WHERE ativo = true")
            valor_total = cursor.fetchone()[0] or 0
            
            cursor.close()
            conn.close()
            
            # Mostrar estatísticas
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Produtos Cadastrados", f"{produtos_count}")
            
            with col2:
                st.metric("Produtos com Estoque Baixo", f"{estoque_baixo_count}")
            
            with col3:
                st.metric("Valor Total em Estoque", f"R$ {valor_total:.2f}")
                
        except Exception as e:
            st.error(f"Erro ao carregar estatísticas: {str(e)}")
    
    # Página de Escaneamento de Produto
    elif menu == "Escanear Produto":
        st.title("Escanear Código de Barras")
        
        # Opção de entrada manual
        manual_input = st.text_input("Código de Barras", 
                                    placeholder="Insira o código manualmente ou escaneie")
        
        # Opção de upload de imagem
        uploaded_file = st.file_uploader("Ou faça upload de uma imagem com código de barras", 
                                         type=["jpg", "jpeg", "png"])
        
        # Opção de usar câmera
        camera_option = st.checkbox("Ativar câmera")
        
        barcode = None
        
        if manual_input:
            barcode = manual_input
        
        elif uploaded_file:
            image = Image.open(uploaded_file)
            st.image(image, caption="Imagem enviada", width=400)
            barcode = decode_barcode(image)
            
            if barcode:
                st.success(f"Código detectado: {barcode}")
            else:
                st.warning("Nenhum código de barras detectado na imagem.")
        
        elif camera_option:
            st.markdown("### Câmera")
            picture = st.camera_input("Capture o código de barras")
            
            if picture:
                image = Image.open(picture)
                barcode = decode_barcode(image)
                
                if barcode:
                    st.success(f"Código detectado: {barcode}")
                else:
                    st.warning("Nenhum código de barras detectado. Tente novamente.")
        
        # Buscar e exibir produto se houver código de barras
        if barcode:
            product = get_product_by_barcode(barcode)
            
            if product:
                st.subheader("Produto Encontrado")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**Nome:** {product['nome']}")
                    st.markdown(f"**Código:** {product['codigo']}")
                    st.markdown(f"**Código de Barras:** {product['codigo_barras']}")
                    if product.get('categoria_nome'):
                        st.markdown(f"**Categoria:** {product['categoria_nome']}")
                
                with col2:
                    st.markdown(f"**Preço:** R$ {product['preco_venda']:.2f}")
                    st.markdown(f"**Estoque:** {product['estoque']} {product.get('unidade', 'un')}")
                    if product.get('descricao'):
                        st.markdown(f"**Descrição:** {product['descricao']}")
                
                # Adicionar à venda
                if st.button("Adicionar à Venda"):
                    # Inicializar carrinho na sessão se não existir
                    if 'cart' not in st.session_state:
                        st.session_state.cart = []
                    
                    # Adicionar produto ao carrinho
                    item = {
                        'id': product['id'],
                        'nome': product['nome'],
                        'codigo_barras': product['codigo_barras'],
                        'preco_venda': product['preco_venda'],
                        'quantidade': 1
                    }
                    
                    # Verificar se o produto já está no carrinho
                    for i, cart_item in enumerate(st.session_state.cart):
                        if cart_item['id'] == product['id']:
                            st.session_state.cart[i]['quantidade'] += 1
                            break
                    else:
                        st.session_state.cart.append(item)
                    
                    st.success(f"'{product['nome']}' adicionado à venda!")
                    st.info("Vá para a página 'Realizar Venda' para finalizar a compra.")
            else:
                st.error("Produto não encontrado para o código informado.")
                
                # Opção para cadastrar novo produto
                if st.button("Cadastrar Novo Produto"):
                    st.session_state.menu = "Cadastrar Produto"
                    st.session_state.new_barcode = barcode
                    st.experimental_rerun()
    
    # Página de Listagem de Produtos
    elif menu == "Listar Produtos":
        st.title("Produtos Cadastrados")
        
        # Opções de filtro
        col1, col2 = st.columns([3, 1])
        
        with col1:
            search_term = st.text_input("Buscar por nome ou código", placeholder="Digite aqui...")
        
        with col2:
            category_filter = st.selectbox(
                "Filtrar por categoria",
                ["Todas"] + [cat["nome"] for cat in get_categories()],
                index=0
            )
        
        # Buscar produtos
        products = get_all_products()
        
        # Aplicar filtros
        if search_term:
            search_term = search_term.lower()
            products = [p for p in products if search_term in p["nome"].lower() or 
                        (p.get("codigo") and search_term in p["codigo"].lower()) or
                        (p.get("codigo_barras") and search_term in p["codigo_barras"].lower())]
        
        if category_filter != "Todas":
            products = [p for p in products if p.get("categoria_nome") == category_filter]
        
        # Exibir produtos
        if not products:
            st.info("Nenhum produto encontrado.")
        else:
            for i, product in enumerate(products):
                with st.expander(f"{product['nome']} - R$ {product['preco_venda']:.2f}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**Código:** {product.get('codigo', 'N/A')}")
                        st.markdown(f"**Código de Barras:** {product.get('codigo_barras', 'N/A')}")
                        st.markdown(f"**Categoria:** {product.get('categoria_nome', 'N/A')}")
                        st.markdown(f"**Descrição:** {product.get('descricao', 'N/A')}")
                    
                    with col2:
                        st.markdown(f"**Preço de Custo:** R$ {product.get('preco_custo', 0):.2f}")
                        st.markdown(f"**Preço de Venda:** R$ {product['preco_venda']:.2f}")
                        st.markdown(f"**Estoque:** {product.get('estoque', 0)} {product.get('unidade', 'un')}")
                        st.markdown(f"**Estoque Mínimo:** {product.get('estoque_minimo', 0)} {product.get('unidade', 'un')}")
                    
                    # Botões de ação
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("Editar", key=f"edit_{i}"):
                            st.session_state.edit_product = product
                            st.session_state.menu = "Cadastrar Produto"
                            st.experimental_rerun()
                    
                    with col2:
                        if st.button("Adicionar à Venda", key=f"add_{i}"):
                            if 'cart' not in st.session_state:
                                st.session_state.cart = []
                            
                            # Verificar se o produto já está no carrinho
                            for j, cart_item in enumerate(st.session_state.cart):
                                if cart_item['id'] == product['id']:
                                    st.session_state.cart[j]['quantidade'] += 1
                                    break
                            else:
                                st.session_state.cart.append({
                                    'id': product['id'],
                                    'nome': product['nome'],
                                    'codigo_barras': product.get('codigo_barras', 'N/A'),
                                    'preco_venda': product['preco_venda'],
                                    'quantidade': 1
                                })
                            
                            st.success(f"'{product['nome']}' adicionado à venda!")
    
    # Página de Cadastro/Edição de Produto
    elif menu == "Cadastrar Produto":
        # Verificar se é edição ou novo cadastro
        editing = 'edit_product' in st.session_state
        
        if editing:
            st.title("Editar Produto")
            product = st.session_state.edit_product
        else:
            st.title("Cadastrar Novo Produto")
            product = {}
            
            # Verificar se tem código de barras da página de scanner
            if 'new_barcode' in st.session_state:
                product['codigo_barras'] = st.session_state.new_barcode
                st.success(f"Código de barras detectado: {product['codigo_barras']}")
        
        # Formulário de cadastro
        with st.form("product_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome *", 
                                    value=product.get('nome', ''),
                                    placeholder="Nome do produto")
                
                codigo = st.text_input("Código",
                                      value=product.get('codigo', ''),
                                      placeholder="Código interno (opcional)")
                
                codigo_barras = st.text_input("Código de Barras",
                                            value=product.get('codigo_barras', ''),
                                            placeholder="EAN, UPC, etc. (opcional)")
                
                categoria_id = st.selectbox(
                    "Categoria",
                    options=[cat["id"] for cat in get_categories()],
                    format_func=lambda x: next((cat["nome"] for cat in get_categories() if cat["id"] == x), ""),
                    index=[i for i, cat in enumerate(get_categories()) if cat["id"] == product.get('categoria_id', 0)][0] if product.get('categoria_id') else 0
                )
                
                descricao = st.text_area("Descrição",
                                       value=product.get('descricao', ''),
                                       placeholder="Descrição do produto (opcional)")
            
            with col2:
                preco_custo = st.number_input("Preço de Custo (R$)",
                                            value=float(product.get('preco_custo', 0)),
                                            min_value=0.0, step=0.01)
                
                preco_venda = st.number_input("Preço de Venda (R$) *",
                                            value=float(product.get('preco_venda', 0)),
                                            min_value=0.0, step=0.01)
                
                estoque = st.number_input("Estoque",
                                        value=int(product.get('estoque', 0)),
                                        min_value=0, step=1)
                
                estoque_minimo = st.number_input("Estoque Mínimo",
                                               value=int(product.get('estoque_minimo', 5)),
                                               min_value=0, step=1)
                
                unidade = st.text_input("Unidade",
                                      value=product.get('unidade', 'un'),
                                      placeholder="un, kg, lt, etc.")
            
            submitted = st.form_submit_button("Salvar")
            
            if submitted:
                if not nome:
                    st.error("Nome do produto é obrigatório.")
                elif preco_venda <= 0:
                    st.error("Preço de venda deve ser maior que zero.")
                else:
                    # Preparar dados do produto
                    produto_data = {
                        'nome': nome,
                        'codigo': codigo,
                        'codigo_barras': codigo_barras,
                        'descricao': descricao,
                        'preco_custo': preco_custo,
                        'preco_venda': preco_venda,
                        'estoque': estoque,
                        'estoque_minimo': estoque_minimo,
                        'categoria_id': categoria_id,
                        'unidade': unidade
                    }
                    
                    if editing:
                        # Atualizar produto existente
                        success, result = update_product(product['id'], produto_data)
                    else:
                        # Criar novo produto
                        success, result = create_product(produto_data)
                    
                    if success:
                        st.success("Produto salvo com sucesso!")
                        
                        # Limpar estado
                        if 'edit_product' in st.session_state:
                            del st.session_state.edit_product
                        
                        if 'new_barcode' in st.session_state:
                            del st.session_state.new_barcode
                        
                        # Redirecionar para listagem após salvar
                        st.session_state.menu = "Listar Produtos"
                        st.experimental_rerun()
                    else:
                        st.error(f"Erro ao salvar produto: {result}")
        
        # Botão para cancelar edição/cadastro
        if st.button("Cancelar"):
            if 'edit_product' in st.session_state:
                del st.session_state.edit_product
            
            if 'new_barcode' in st.session_state:
                del st.session_state.new_barcode
            
            st.session_state.menu = "Listar Produtos"
            st.experimental_rerun()
    
    # Página de Realização de Venda
    elif menu == "Realizar Venda":
        st.title("Realizar Venda")
        
        # Inicializar carrinho se não existir
        if 'cart' not in st.session_state:
            st.session_state.cart = []
        
        # Exibir produtos no carrinho
        if not st.session_state.cart:
            st.info("Nenhum produto adicionado à venda ainda.")
            st.markdown("Vá para a página 'Escanear Produto' para adicionar produtos.")
        else:
            st.subheader("Produtos na Venda")
            
            for i, item in enumerate(st.session_state.cart):
                col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                
                with col1:
                    st.write(f"{item['nome']}")
                
                with col2:
                    st.write(f"R$ {item['preco_venda']:.2f}")
                
                with col3:
                    # Controle de quantidade
                    new_qt = st.number_input(
                        "Qtd",
                        min_value=1,
                        value=item['quantidade'],
                        key=f"qt_{i}"
                    )
                    
                    if new_qt != item['quantidade']:
                        st.session_state.cart[i]['quantidade'] = new_qt
                        st.experimental_rerun()
                
                with col4:
                    st.write(f"R$ {item['preco_venda'] * item['quantidade']:.2f}")
                
                with col5:
                    if st.button("🗑️", key=f"del_{i}"):
                        st.session_state.cart.pop(i)
                        st.experimental_rerun()
            
            # Calcular total
            total = sum(item['preco_venda'] * item['quantidade'] for item in st.session_state.cart)
            
            st.markdown("---")
            st.markdown(f"### Total: R$ {total:.2f}")
            
            # Opções de pagamento
            payment_method = st.selectbox(
                "Forma de Pagamento",
                ["Dinheiro", "Cartão de Crédito", "Cartão de Débito", "PIX"]
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                if payment_method == "Dinheiro":
                    payment_value = st.number_input("Valor Recebido (R$)", 
                                                  min_value=float(total), 
                                                  value=float(total),
                                                  step=1.0)
                    
                    if payment_value > total:
                        st.info(f"Troco: R$ {payment_value - total:.2f}")
            
            with col2:
                customer_name = st.text_input("Nome do Cliente (opcional)", placeholder="Cliente")
            
            # Botão de finalizar venda
            if st.button("Finalizar Venda", type="primary"):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    # Inserir venda
                    cursor.execute("""
                        INSERT INTO vendas 
                        (cliente_nome, valor_total, forma_pagamento, status) 
                        VALUES (%s, %s, %s, 'concluida') 
                        RETURNING id
                    """, (customer_name, total, payment_method))
                    
                    venda_id = cursor.fetchone()[0]
                    
                    # Inserir itens
                    for item in st.session_state.cart:
                        cursor.execute("""
                            INSERT INTO venda_itens 
                            (venda_id, produto_id, quantidade, preco_unitario) 
                            VALUES (%s, %s, %s, %s)
                        """, (venda_id, item['id'], item['quantidade'], item['preco_venda']))
                        
                        # Atualizar estoque
                        cursor.execute("""
                            UPDATE produtos 
                            SET estoque = estoque - %s 
                            WHERE id = %s
                        """, (item['quantidade'], item['id']))
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    # Limpar carrinho
                    st.session_state.cart = []
                    
                    st.success("Venda realizada com sucesso!")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"Erro ao finalizar venda: {str(e)}")
                    
            # Botão de cancelar venda
            if st.button("Cancelar Venda"):
                st.session_state.cart = []
                st.experimental_rerun()

# Executar aplicativo
if __name__ == "__main__":
    main()
