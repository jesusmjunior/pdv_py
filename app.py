import streamlit as st
import psycopg2
import pandas as pd
import time
import cv2
from PIL import Image
import io
import datetime
import uuid
import numpy as np
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase
import av
from pyzbar import pyzbar

# Configurações de página
st.set_page_config(
    page_title="ORION PDV",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuração do banco de dados PostgreSQL
def get_db_connection():
    conn = psycopg2.connect(
        host="34.95.252.164",
        database="pdv",
        user="postgres",
        password="pdv@2025",
        port=5432,
        sslmode='require'
    )
    return conn

# Função para inicializar o banco de dados
def init_database():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Criar tabela de categorias
    cur.execute('''
    CREATE TABLE IF NOT EXISTS categorias (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        descricao TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Criar tabela de produtos
    cur.execute('''
    CREATE TABLE IF NOT EXISTS produtos (
        id SERIAL PRIMARY KEY,
        codigo VARCHAR(50) UNIQUE,
        barcode VARCHAR(100),
        nome VARCHAR(200) NOT NULL,
        descricao TEXT,
        preco DECIMAL(10, 2) NOT NULL,
        estoque INT DEFAULT 0,
        categoria_id INT REFERENCES categorias(id),
        imagem_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Criar tabela de vendas
    cur.execute('''
    CREATE TABLE IF NOT EXISTS vendas (
        id SERIAL PRIMARY KEY,
        venda_id VARCHAR(50) UNIQUE,
        data_venda TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total DECIMAL(10, 2) NOT NULL,
        forma_pagamento VARCHAR(50),
        status VARCHAR(20) DEFAULT 'concluida',
        observacoes TEXT
    )
    ''')
    
    # Criar tabela de itens de venda
    cur.execute('''
    CREATE TABLE IF NOT EXISTS venda_itens (
        id SERIAL PRIMARY KEY,
        venda_id VARCHAR(50) REFERENCES vendas(venda_id),
        produto_id INT REFERENCES produtos(id),
        quantidade INT NOT NULL,
        preco_unitario DECIMAL(10, 2) NOT NULL,
        subtotal DECIMAL(10, 2) NOT NULL
    )
    ''')
    
    # Verificar se já existem categorias, se não, inserir algumas categorias padrão
    cur.execute("SELECT COUNT(*) FROM categorias")
    if cur.fetchone()[0] == 0:
        categorias = [
            ("Alimentos", "Produtos alimentícios"),
            ("Bebidas", "Bebidas diversas"),
            ("Limpeza", "Produtos de limpeza"),
            ("Higiene", "Produtos de higiene pessoal"),
            ("Outros", "Produtos diversos")
        ]
        for cat in categorias:
            cur.execute("INSERT INTO categorias (nome, descricao) VALUES (%s, %s)", cat)
    
    conn.commit()
    cur.close()
    conn.close()

# Inicializar o banco de dados
init_database()

# Classe para processamento de vídeo e leitura de código de barras
class BarcodeVideoProcessor(VideoProcessorBase):
    def __init__(self):
        self.barcode_data = None
        self.barcode_type = None
        self.last_detection_time = 0
        self.detection_interval = 1.0  # segundos
        
    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        
        # Verificar se já passou o intervalo de detecção
        current_time = time.time()
        if current_time - self.last_detection_time >= self.detection_interval:
            # Decodificar barcodes
            barcodes = pyzbar.decode(img)
            
            for barcode in barcodes:
                # Extrair e formatar os dados do barcode
                barcode_data = barcode.data.decode("utf-8")
                barcode_type = barcode.type
                
                # Desenhando uma caixa ao redor do código de barras
                (x, y, w, h) = barcode.rect
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                # Desenhando o texto do código de barras e seu tipo
                text = f"{barcode_data} ({barcode_type})"
                cv2.putText(img, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 255, 0), 2)
                
                self.barcode_data = barcode_data
                self.barcode_type = barcode_type
                self.last_detection_time = current_time
                
                # Enviando dados para a sessão do Streamlit
                st.session_state.last_barcode = barcode_data
                st.session_state.barcode_detected = True
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# Funções CRUD para categorias
def get_categorias():
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM categorias ORDER BY nome", conn)
    conn.close()
    return df

def adicionar_categoria(nome, descricao=""):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO categorias (nome, descricao) VALUES (%s, %s) RETURNING id", (nome, descricao))
    cat_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return cat_id

def atualizar_categoria(cat_id, nome, descricao):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE categorias SET nome = %s, descricao = %s WHERE id = %s", (nome, descricao, cat_id))
    conn.commit()
    cur.close()
    conn.close()

def excluir_categoria(cat_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM categorias WHERE id = %s", (cat_id,))
        conn.commit()
        resultado = True
    except psycopg2.Error as e:
        conn.rollback()
        st.error(f"Erro ao excluir categoria: {e}")
        resultado = False
    cur.close()
    conn.close()
    return resultado

# Funções CRUD para produtos
def get_produtos():
    conn = get_db_connection()
    query = """
    SELECT p.*, c.nome as categoria_nome 
    FROM produtos p
    LEFT JOIN categorias c ON p.categoria_id = c.id
    ORDER BY p.nome
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def get_produto_by_id(produto_id):
    conn = get_db_connection()
    query = """
    SELECT p.*, c.nome as categoria_nome 
    FROM produtos p
    LEFT JOIN categorias c ON p.categoria_id = c.id
    WHERE p.id = %s
    """
    df = pd.read_sql(query, conn, params=[produto_id])
    conn.close()
    if len(df) > 0:
        return df.iloc[0]
    return None

def get_produto_by_barcode(barcode):
    conn = get_db_connection()
    query = """
    SELECT p.*, c.nome as categoria_nome 
    FROM produtos p
    LEFT JOIN categorias c ON p.categoria_id = c.id
    WHERE p.barcode = %s
    """
    df = pd.read_sql(query, conn, params=[barcode])
    conn.close()
    if len(df) > 0:
        return df.iloc[0]
    return None

def adicionar_produto(codigo, nome, descricao, preco, estoque, categoria_id, barcode=None, imagem_url=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO produtos (codigo, nome, descricao, preco, estoque, categoria_id, barcode, imagem_url) 
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    """, (codigo, nome, descricao, preco, estoque, categoria_id, barcode, imagem_url))
    produto_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return produto_id

def atualizar_produto(produto_id, codigo, nome, descricao, preco, estoque, categoria_id, barcode=None, imagem_url=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE produtos 
    SET codigo = %s, nome = %s, descricao = %s, preco = %s, estoque = %s, 
        categoria_id = %s, barcode = %s, imagem_url = %s, updated_at = CURRENT_TIMESTAMP
    WHERE id = %s
    """, (codigo, nome, descricao, preco, estoque, categoria_id, barcode, imagem_url, produto_id))
    conn.commit()
    cur.close()
    conn.close()

def excluir_produto(produto_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))
        conn.commit()
        resultado = True
    except psycopg2.Error as e:
        conn.rollback()
        st.error(f"Erro ao excluir produto: {e}")
        resultado = False
    cur.close()
    conn.close()
    return resultado

def atualizar_estoque_produto(produto_id, quantidade):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE produtos 
    SET estoque = estoque - %s, updated_at = CURRENT_TIMESTAMP
    WHERE id = %s
    """, (quantidade, produto_id))
    conn.commit()
    cur.close()
    conn.close()

# Funções CRUD para vendas
def registrar_venda(items, total, forma_pagamento, observacoes=""):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Gerar ID único para a venda
        venda_id = str(uuid.uuid4())
        
        # Inserir registro de venda
        cur.execute("""
        INSERT INTO vendas (venda_id, total, forma_pagamento, observacoes) 
        VALUES (%s, %s, %s, %s) RETURNING id
        """, (venda_id, total, forma_pagamento, observacoes))
        
        # Inserir itens da venda
        for item in items:
            produto_id = item['produto_id']
            quantidade = item['quantidade']
            preco_unitario = item['preco_unitario']
            subtotal = quantidade * preco_unitario
            
            cur.execute("""
            INSERT INTO venda_itens (venda_id, produto_id, quantidade, preco_unitario, subtotal) 
            VALUES (%s, %s, %s, %s, %s)
            """, (venda_id, produto_id, quantidade, preco_unitario, subtotal))
            
            # Atualizar estoque
            cur.execute("""
            UPDATE produtos SET estoque = estoque - %s WHERE id = %s
            """, (quantidade, produto_id))
        
        conn.commit()
        return venda_id
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao registrar venda: {str(e)}")
        return None
    finally:
        cur.close()
        conn.close()

def get_vendas(data_inicio=None, data_fim=None):
    conn = get_db_connection()
    query = "SELECT * FROM vendas WHERE 1=1"
    params = []
    
    if data_inicio:
        query += " AND data_venda >= %s"
        params.append(data_inicio)
    
    if data_fim:
        query += " AND data_venda <= %s"
        params.append(data_fim)
    
    query += " ORDER BY data_venda DESC"
    
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df

def get_venda_detalhes(venda_id):
    conn = get_db_connection()
    query = """
    SELECT vi.*, p.nome as produto_nome, p.codigo as produto_codigo
    FROM venda_itens vi
    JOIN produtos p ON vi.produto_id = p.id
    WHERE vi.venda_id = %s
    """
    df = pd.read_sql(query, conn, params=[venda_id])
    conn.close()
    return df

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
        st.title("🛒 ORION PDV")
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
        st.caption("© 2025 ORION PDV")
    
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

def mostrar_pdv():
    st.title("📋 Ponto de Venda")
    
    # Layout em duas colunas: esquerda para scanner e carrinho, direita para lista de produtos
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Scanner de código de barras
        st.subheader("Scanner de Código de Barras")
        
        # Iniciar WebRTC para captura de vídeo
        webrtc_ctx = webrtc_streamer(
            key="barcode-scanner",
            video_processor_factory=BarcodeVideoProcessor,
            media_stream_constraints={
                "video": True,
                "audio": False
            },
            async_processing=True,
        )
        
        # Campo para código de barras manual
        col_barcode, col_btn = st.columns([3, 1])
        with col_barcode:
            barcode_input = st.text_input("Código de Barras:", 
                                        value=st.session_state.last_barcode if st.session_state.barcode_detected else "")
        with col_btn:
            search_btn = st.button("Buscar", use_container_width=True)
        
        # Detectou código de barras ou clicou em buscar
        if (st.session_state.barcode_detected or search_btn) and barcode_input:
            produto = get_produto_by_barcode(barcode_input)
            
            if produto is not None:
                st.success(f"Produto encontrado: {produto['nome']}")
                
                # Adicionar ao carrinho
                if st.button("Adicionar ao Carrinho", key="add_to_cart"):
                    item = {
                        'produto_id': int(produto['id']),
                        'nome': produto['nome'],
                        'preco_unitario': float(produto['preco']),
                        'quantidade': 1,
                        'subtotal': float(produto['preco'])
                    }
                    st.session_state.cart.append(item)
                    st.success(f"Produto '{produto['nome']}' adicionado ao carrinho!")
                    st.session_state.barcode_detected = False
                    st.session_state.last_barcode = None
                    st.experimental_rerun()
            else:
                st.error(f"Produto com código de barras '{barcode_input}' não encontrado!")
                
            # Resetar detecção
            st.session_state.barcode_detected = False
        
        # Carrinho de compras
        st.subheader("Carrinho de Compras")
        
        if not st.session_state.cart:
            st.info("Seu carrinho está vazio.")
        else:
            # Tabela do carrinho
            cart_df = pd.DataFrame(st.session_state.cart)
            edited_df = st.data_editor(
                cart_df,
                column_config={
                    "produto_id": None,  # Ocultar coluna
                    "nome": "Produto",
                    "preco_unitario": st.column_config.NumberColumn(
                        "Preço Unit.", format="R$ %.2f"
                    ),
                    "quantidade": st.column_config.NumberColumn(
                        "Qtd", min_value=1, step=1
                    ),
                    "subtotal": st.column_config.NumberColumn(
                        "Subtotal", format="R$ %.2f", disabled=True
                    ),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="dynamic"
            )
            
            # Atualizar quantidades e subtotais
            updated_cart = []
            for i, row in edited_df.iterrows():
                item = row.to_dict()
                item['subtotal'] = item['quantidade'] * item['preco_unitario']
                updated_cart.append(item)
            
            st.session_state.cart = updated_cart
            
            # Botões para limpar carrinho
            if st.button("Limpar Carrinho", key="clear_cart", use_container_width=True):
                st.session_state.cart = []
                st.experimental_rerun()
            
            # Total
            total = sum(item['subtotal'] for item in st.session_state.cart)
            st.markdown(f"### Total: R$ {total:.2f}")
            
            # Finalizar compra
            st.subheader("Finalizar Compra")
            forma_pagamento = st.selectbox(
                "Forma de Pagamento",
                ["Dinheiro", "Cartão de Crédito", "Cartão de Débito", "PIX"]
            )
            
            observacoes = st.text_area("Observações", height=100)
            
            if st.button("Finalizar Venda", use_container_width=True):
                if st.session_state.cart:
                    venda_id = registrar_venda(
                        st.session_state.cart, 
                        total, 
                        forma_pagamento, 
                        observacoes
                    )
                    
                    if venda_id:
                        st.success(f"Venda registrada com sucesso! ID: {venda_id}")
                        st.session_state.cart = []
                        st.balloons()
                else:
                    st.error("Não é possível finalizar uma venda sem produtos.")
    
    with col2:
        # Lista de produtos
        st.subheader("Produtos Disponíveis")
        
        # Pesquisa
        pesquisa = st.text_input("Pesquisar produto:", key="search_pdv")
        
        # Obter produtos
        df_produtos = get_produtos()
        
        # Filtrar por pesquisa
        if pesquisa:
            df_produtos = df_produtos[
                df_produtos['nome'].str.contains(pesquisa, case=False) | 
                df_produtos['codigo'].str.contains(pesquisa, case=False)
            ]
        
        # Exibir produtos
        for i, row in df_produtos.iterrows():
            with st.container():
                col_img, col_info = st.columns([1, 3])
                
                with col_img:
                    if row['imagem_url']:
                        st.image(row['imagem_url'], width=50)
                    else:
                        st.markdown("📦")
                
                with col_info:
                    st.markdown(f"**{row['nome']}**")
                    st.markdown(f"Código: {row['codigo']} | R$ {float(row['preco']):.2f}")
                    st.markdown(f"Estoque: {int(row['estoque'])}")
                    
                    # Botão para adicionar ao carrinho
                    if st.button(f"Adicionar", key=f"add_pdv_{row['id']}"):
                        item = {
                            'produto_id': int(row['id']),
                            'nome': row['nome'],
                            'preco_unitario': float(row['preco']),
                            'quantidade': 1,
                            'subtotal': float(row['preco'])
                        }
                        st.session_state.cart.append(item)
                        st.success(f"Produto '{row['nome']}' adicionado ao carrinho!")
                        st.experimental_rerun()
                
                st.markdown("---")

def mostrar_produtos():
    st.title("📦 Gerenciamento de Produtos")
    
    # Tabs para listar e adicionar produtos
    tab1, tab2 = st.tabs(["Lista de Produtos", "Adicionar/Editar Produto"])
    
    with tab1:
        # Pesquisa
        pesquisa = st.text_input("Pesquisar produto:", key="search_produtos")
        
        # Obter produtos
        df_produtos = get_produtos()
        
        # Filtrar por pesquisa
        if pesquisa:
            df_produtos = df_produtos[
                df_produtos['nome'].str.contains(pesquisa, case=False) | 
                df_produtos['codigo'].str.contains(pesquisa, case=False) |
                df_produtos['barcode'].str.contains(pesquisa, case=False)
            ]
        
        # Exibir produtos em tabela
        st.dataframe(
            df_produtos,
            column_config={
                "id": st.column_config.NumberColumn("ID"),
                "codigo": "Código",
                "barcode": "Código de Barras",
                "nome": "Nome",
                "descricao": "Descrição",
                "preco": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
                "estoque": "Estoque",
                "categoria_nome": "Categoria",
                "imagem_url": None,  # Ocultar URL da imagem
                "created_at": None,  # Ocultar data de criação
                "updated_at": None,  # Ocultar data de atualização
                "categoria_id": None,  # Ocultar ID da categoria
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Ações para cada produto
        produto_id_para_acao = st.number_input("ID do Produto para Ação", min_value=1, step=1)
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Editar Produto", use_container_width=True):
                if produto_id_para_acao:
                    produto = get_produto_by_id(produto_id_para_acao)
                    if produto is not None:
                        st.session_state.produto_em_edicao = produto.to_dict()
                        st.session_state.modo_edicao = True
                        st.experimental_rerun()
                    else:
                        st.error(f"Produto com ID {produto_id_para_acao} não encontrado!")
        
        with col2:
            if st.button("Excluir Produto", use_container_width=True):
                if produto_id_para_acao:
                    if st.session_state.get('confirmar_exclusao') == produto_id_para_acao:
                        # Já confirmou a exclusão
                        if excluir_produto(produto_id_para_acao):
                            st.success(f"Produto com ID {produto_id_para_acao} excluído com sucesso!")
                            st.session_state.pop('confirmar_exclusao', None)
                            st.experimental_rerun()
                    else:
                        # Solicitar confirmação
                        st.session_state.confirmar_exclusao = produto_id_para_acao
                        st.warning(f"Clique novamente em 'Excluir Produto' para confirmar a exclusão do produto {produto_id_para_acao}")
    
    with tab2:
        # Obter lista de categorias para o select
        df_categorias = get_categorias()
        categorias_options = dict(zip(df_categorias['id'].tolist(), df_categorias['nome'].tolist()))
        
        # Se estiver em modo de edição, preencher os campos
        produto_em_edicao = st.session_state.get('produto_em_edicao', None)
        
        if produto_em_edicao:
            st.header("Editar Produto")
            produto_id = produto_em_edicao['id']
        else:
            st.header("Adicionar Novo Produto")
            produto_id = None
        
        # Formulário de produto
        with st.form(key="produto_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                codigo = st.text_input(
                    "Código do Produto*", 
                    value=produto_em_edicao['codigo'] if produto_em_edicao else ""
                )
                
                nome = st.text_input(
                    "Nome do Produto*", 
                    value=produto_em_edicao['nome'] if produto_em_edicao else ""
                )
                
                barcode = st.text_input(
                    "Código de Barras", 
                    value=produto_em_edicao['barcode'] if produto_em_edicao else ""
                )
                
                categoria_id = st.selectbox(
                    "Categoria", 
                    options=list(categorias_options.keys()),
                    format_func=lambda x: categorias_options.get(x),
                    index=list(categorias_options.keys()).index(produto_em_edicao['categoria_id']) 
                    if produto_em_edicao and produto_em_edicao['categoria_id'] in categorias_options 
                    else 0
                )
            
            with col2:
                preco = st.number_input(
                    "Preço*", 
                    min_value=0.01, 
                    step=0.01,
                    value=float(produto_em_edicao['preco']) if produto_em_edicao else 0.01
                )
                
                estoque = st.number_input(
                    "Estoque*", 
                    min_value=0, 
                    step=1,
                    value=int(produto_em_edicao['estoque']) if produto_em_edicao else 0
                )
                
                imagem_url = st.text_input(
                    "URL da Imagem", 
                    value=produto_em_edicao['imagem_url'] if produto_em_edicao and produto_em_edicao['imagem_url'] else ""
                )
            
            descricao = st.text_area(
                "Descrição", 
                value=produto_em_edicao['descricao'] if produto_em_edicao and produto_em_edicao['descricao'] else ""
            )
            
            submit_button = st.form_submit_button("Salvar Produto")
            
            if submit_button:
                # Validar campos obrigatórios
                if not codigo or not nome or not preco:
                    st.error("Os campos marcados com * são obrigatórios!")
                else:
                    if produto_id:  # Edição
                        atualizar_produto(
                            produto_id, codigo, nome, descricao, preco, 
                            estoque, categoria_id, barcode, imagem_url
                        )
                        st.success(f"Produto '{nome}' atualizado com sucesso!")
                        st.session_state.pop('produto_em_edicao', None)
                        st.session_state.modo_edicao = False
                    else:  # Adição
                        novo_id = adicionar_produto(
                            codigo, nome, descricao, preco, 
                            estoque, categoria_id, barcode, imagem_url
                        )
                        st.success(f"Produto '{nome}' adicionado com sucesso! ID: {novo_id}")
                    
                    time.sleep(1)
                    st.experimental_rerun()
        
        # Botão para cancelar edição
        if produto_em_edicao and st.button("Cancelar Edição", use_container_width=True):
            st.session_state.pop('produto_em_edicao', None)
            st.session_state.modo_edicao = False
            st.experimental_rerun()

def mostrar_categorias():
    st.title("🏷️ Gerenciamento de Categorias")
    
    # Tabs para listar e adicionar categorias
    tab1, tab2 = st.tabs(["Lista de Categorias", "Adicionar/Editar Categoria"])
    
    with tab1:
        # Obter categorias
        df_categorias = get_categorias()
        
        # Exibir categorias em tabela
        st.dataframe(
            df_categorias,
            column_config={
                "id": st.column_config.NumberColumn("ID"),
                "nome": "Nome",
                "descricao": "Descrição",
                "created_at": None,  # Ocultar data de criação
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Ações para cada categoria
        categoria_id_para_acao = st.number_input("ID da Categoria para Ação", min_value=1, step=1)
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Editar Categoria", use_container_width=True):
                if categoria_id_para_acao:
                    # Buscar categoria para edição
                    categoria = df_categorias[df_categorias['id'] == categoria_id_para_acao]
                    if not categoria.empty:
                        st.session_state.categoria_em_edicao = categoria.iloc[0].to_dict()
                        st.session_state.modo_edicao_categoria = True
                        st.experimental_rerun()
                    else:
                        st.error(f"Categoria com ID {categoria_id_para_acao} não encontrada!")
        
        with col2:
            if st.button("Excluir Categoria", use_container_width=True):
                if categoria_id_para_acao:
                    if st.session_state.get('confirmar_exclusao_categoria') == categoria_id_para_acao:
                        # Já confirmou a exclusão
                        if excluir_categoria(categoria_id_para_acao):
                            st.success(f"Categoria com ID {categoria_id_para_acao} excluída com sucesso!")
                            st.session_state.pop('confirmar_exclusao_categoria', None)
                            st.experimental_rerun()
                    else:
                        # Solicitar confirmação
                        st.session_state.confirmar_exclusao_categoria = categoria_id_para_acao
                        st.warning(f"Clique novamente em 'Excluir Categoria' para confirmar a exclusão da categoria {categoria_id_para_acao}")
    
    with tab2:
        # Se estiver em modo de edição, preencher os campos
        categoria_em_edicao = st.session_state.get('categoria_em_edicao', None)
        
        if categoria_em_edicao:
            st.header("Editar Categoria")
            categoria_id = categoria_em_edicao['id']
        else:
            st.header("Adicionar Nova Categoria")
            categoria_id = None
        
        # Formulário de categoria
        with st.form(key="categoria_form"):
            nome = st.text_input(
                "Nome da Categoria*", 
                value=categoria_em_edicao['nome'] if categoria_em_edicao else ""
            )
            
            descricao = st.text_area(
                "Descrição", 
                value=categoria_em_edicao['descricao'] if categoria_em_edicao and categoria_em_edicao['descricao'] else ""
            )
            
            submit_button = st.form_submit_button("Salvar Categoria")
            
            if submit_button:
                # Validar campos obrigatórios
                if not nome:
                    st.error("O nome da categoria é obrigatório!")
                else:
                    if categoria_id:  # Edição
                        atualizar_categoria(categoria_id, nome, descricao)
                        st.success(f"Categoria '{nome}' atualizada com sucesso!")
                        st.session_state.pop('categoria_em_edicao', None)
                        st.session_state.modo_edicao_categoria = False
                    else:  # Adição
                        novo_id = adicionar_categoria(nome, descricao)
                        st.success(f"Categoria '{nome}' adicionada com sucesso! ID: {novo_id}")
                    
                    time.sleep(1)
                    st.experimental_rerun()
        
        # Botão para cancelar edição
        if categoria_em_edicao and st.button("Cancelar Edição", use_container_width=True):
            st.session_state.pop('categoria_em_edicao', None)
            st.session_state.modo_edicao_categoria = False
            st.experimental_rerun()

def mostrar_relatorios():
    st.title("📊 Relatórios")
    
    # Tabs para diferentes relatórios
    tab1, tab2, tab3 = st.tabs(["Vendas", "Produtos", "Estoque"])
    
    with tab1:
        st.header("Relatório de Vendas")
        
        # Filtro de datas
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("Data Inicial", datetime.date.today() - datetime.timedelta(days=30))
        with col2:
            data_fim = st.date_input("Data Final", datetime.date.today())
        
        # Converter para datetime
        data_inicio_dt = datetime.datetime.combine(data_inicio, datetime.time.min)
        data_fim_dt = datetime.datetime.combine(data_fim, datetime.time.max)
        
        # Obter vendas filtradas
        df_vendas = get_vendas(data_inicio_dt, data_fim_dt)
        
        if df_vendas.empty:
            st.info("Nenhuma venda encontrada para o período selecionado.")
        else:
            # Resumo de vendas
            total_vendas = len(df_vendas)
            valor_total = df_vendas['total'].sum()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total de Vendas", total_vendas)
            with col2:
                st.metric("Valor Total", f"R$ {valor_total:.2f}")
            
            # Tabela de vendas
            st.subheader("Histórico de Vendas")
            df_vendas_formatado = df_vendas.copy()
            df_vendas_formatado['data_venda'] = pd.to_datetime(df_vendas_formatado['data_venda']).dt.strftime('%d/%m/%Y %H:%M')
            
            st.dataframe(
                df_vendas_formatado,
                column_config={
                    "id": None,  # Ocultar ID interno
                    "venda_id": "ID da Venda",
                    "data_venda": "Data/Hora",
                    "total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                    "forma_pagamento": "Forma de Pagamento",
                    "status": "Status",
                    "observacoes": "Observações"
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Gráfico de vendas por dia
            df_vendas['data'] = pd.to_datetime(df_vendas['data_venda']).dt.date
            vendas_por_dia = df_vendas.groupby('data')['total'].sum().reset_index()
            vendas_por_dia_chart = pd.DataFrame({
                'data': vendas_por_dia['data'].astype(str),
                'total': vendas_por_dia['total']
            })
            
            st.subheader("Vendas por Dia")
            st.bar_chart(vendas_por_dia_chart, x='data', y='total')
            
            # Gráfico de vendas por forma de pagamento
            vendas_por_pagamento = df_vendas.groupby('forma_pagamento')['total'].sum().reset_index()
            
            st.subheader("Vendas por Forma de Pagamento")
            st.bar_chart(vendas_por_pagamento, x='forma_pagamento', y='total')
            
            # Detalhes de venda
            st.subheader("Detalhes de Venda")
            venda_selecionada = st.selectbox(
                "Selecione uma venda para ver detalhes:",
                options=df_vendas['venda_id'].tolist(),
                format_func=lambda x: f"Venda {x} - {df_vendas[df_vendas['venda_id']==x]['data_venda'].iloc[0]}"
            )
            
            if venda_selecionada:
                detalhes_venda = get_venda_detalhes(venda_selecionada)
                
                st.dataframe(
                    detalhes_venda,
                    column_config={
                        "id": None,  # Ocultar ID interno
                        "venda_id": None,  # Ocultar ID da venda
                        "produto_id": None,  # Ocultar ID do produto
                        "produto_nome": "Produto",
                        "produto_codigo": "Código",
                        "quantidade": "Quantidade",
                        "preco_unitario": st.column_config.NumberColumn("Preço Unit.", format="R$ %.2f"),
                        "subtotal": st.column_config.NumberColumn("Subtotal", format="R$ %.2f")
                    },
                    use_container_width=True,
                    hide_index=True
                )
    
    with tab2:
        st.header("Relatório de Produtos")
        
        # Obter produtos
        df_produtos = get_produtos()
        
        if df_produtos.empty:
            st.info("Nenhum produto cadastrado.")
        else:
            # Resumo de produtos
            total_produtos = len(df_produtos)
            valor_estoque = (df_produtos['preco'] * df_produtos['estoque']).sum()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total de Produtos", total_produtos)
            with col2:
                st.metric("Valor em Estoque", f"R$ {valor_estoque:.2f}")
            
            # Gráfico de produtos por categoria
            produtos_por_categoria = df_produtos.groupby('categoria_nome').size().reset_index(name='count')
            
            st.subheader("Produtos por Categoria")
            st.bar_chart(produtos_por_categoria, x='categoria_nome', y='count')
            
            # Produtos mais caros
            st.subheader("Produtos mais caros")
            df_produtos_caros = df_produtos.sort_values('preco', ascending=False).head(10)
            
            st.dataframe(
                df_produtos_caros,
                column_config={
                    "id": None,  # Ocultar ID interno
                    "codigo": "Código",
                    "nome": "Nome",
                    "preco": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
                    "categoria_nome": "Categoria",
                    "barcode": None,  # Ocultar código de barras
                    "descricao": None,  # Ocultar descrição
                    "estoque": None,  # Ocultar estoque
                    "categoria_id": None,  # Ocultar ID da categoria
                    "imagem_url": None,  # Ocultar URL da imagem
                    "created_at": None,  # Ocultar data de criação
                    "updated_at": None  # Ocultar data de atualização
                },
                use_container_width=True,
                hide_index=True
            )
    
    with tab3:
        st.header("Relatório de Estoque")
        
        # Obter produtos
        df_produtos = get_produtos()
        
        if df_produtos.empty:
            st.info("Nenhum produto cadastrado.")
        else:
            # Resumo de estoque
            total_itens = df_produtos['estoque'].sum()
            
            st.metric("Total de Itens em Estoque", total_itens)
            
            # Produtos com estoque baixo
            st.subheader("Produtos com Estoque Baixo (menos de 10 unidades)")
            df_estoque_baixo = df_produtos[df_produtos['estoque'] < 10].sort_values('estoque')
            
            if df_estoque_baixo.empty:
                st.info("Nenhum produto com estoque baixo.")
            else:
                st.dataframe(
                    df_estoque_baixo,
                    column_config={
                        "id": None,  # Ocultar ID interno
                        "codigo": "Código",
                        "nome": "Nome",
                        "estoque": "Estoque",
                        "preco": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
                        "categoria_nome": "Categoria",
                        "barcode": None,  # Ocultar código de barras
                        "descricao": None,  # Ocultar descrição
                        "categoria_id": None,  # Ocultar ID da categoria
                        "imagem_url": None,  # Ocultar URL da imagem
                        "created_at": None,  # Ocultar data de criação
                        "updated_at": None  # Ocultar data de atualização
                    },
                    use_container_width=True,
                    hide_index=True
                )
            
            # Produtos com maior estoque
            st.subheader("Produtos com Maior Estoque")
            df_maior_estoque = df_produtos.sort_values('estoque', ascending=False).head(10)
            
            st.dataframe(
                df_maior_estoque,
                column_config={
                    "id": None,  # Ocultar ID interno
                    "codigo": "Código",
                    "nome": "Nome",
                    "estoque": "Estoque",
                    "preco": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
                    "categoria_nome": "Categoria",
                    "barcode": None,  # Ocultar código de barras
                    "descricao": None,  # Ocultar descrição
                    "categoria_id": None,  # Ocultar ID da categoria
                    "imagem_url": None,  # Ocultar URL da imagem
                    "created_at": None,  # Ocultar data de criação
                    "updated_at": None  # Ocultar data de atualização
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Gráfico de valor em estoque por categoria
            df_produtos['valor_estoque'] = df_produtos['preco'] * df_produtos['estoque']
            valor_por_categoria = df_produtos.groupby('categoria_nome')['valor_estoque'].sum().reset_index()
            
            st.subheader("Valor em Estoque por Categoria")
            st.bar_chart(valor_por_categoria, x='categoria_nome', y='valor_estoque')

if __name__ == "__main__":
    main()
