import streamlit as st
import io
import os
import datetime
import time
import base64
import json

# Importações seguras com fallbacks para ambiente cloud
try:
    import psycopg2
    import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False
    st.error("Erro: Biblioteca psycopg2 não encontrada. Instale com: pip install psycopg2-binary")

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    
try:
    from PIL import Image
    import numpy as np
    HAS_IMAGE_SUPPORT = True
except ImportError:
    HAS_IMAGE_SUPPORT = False

# Importações compatíveis com Streamlit Cloud
try:
    import cv2
    from pyzbar.pyzbar import decode as pyzbar_decode
    HAS_BARCODE_SUPPORT = True
except:
    # Fallback para ambiente cloud
    HAS_BARCODE_SUPPORT = False
    
# Verificar se podemos usar plotly (funciona bem no Streamlit Cloud)
try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except:
    HAS_PLOTLY = False

# Configuração inicial
st.set_option('deprecation.showfileUploaderEncoding', False)

# Configuração da página
st.set_page_config(
    page_title="BarcodeScan PDV",
    page_icon="🛒",
    layout="wide"
)

# Configuração do banco de dados PostgreSQL
def get_db_connection():
    if not HAS_POSTGRES:
        st.error("Impossível conectar ao banco de dados: biblioteca psycopg2 não disponível")
        return None
        
    try:
        conn = psycopg2.connect(
            host="34.95.252.164",
            database="pdv",
            user="postgres",
            password="pdv@2025",
            port="5432",
            sslmode="require"
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        st.error(f"Erro de conexão com banco de dados: {str(e)}")
        return None

# Função para decodificar códigos de barras (compatível com Streamlit Cloud)
def decode_barcode(image):
    if not HAS_BARCODE_SUPPORT or not HAS_IMAGE_SUPPORT:
        st.info("📷 Leitura automática de código de barras indisponível na nuvem. Digite o código manualmente.")
        return None
    
    if image is not None:
        try:
            # Converter imagem para OpenCV
            if isinstance(image, Image.Image):
                image = np.array(image.convert('RGB'))
                
            # Converter para escala de cinza
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Decodificar os códigos de barras
            barcodes = pyzbar_decode(gray)
            
            if barcodes:
                return barcodes[0].data.decode('utf-8')
        except:
            # Silenciosamente falha em ambiente cloud
            pass
    
    return None

# Função para buscar produto por código de barras
def get_product_by_barcode(barcode):
    conn = get_db_connection()
    if conn is None:
        return None
        
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Busca produto pelo código de barras
        cursor.execute("""
            SELECT p.*, c.nome as categoria_nome 
            FROM produtos p 
            LEFT JOIN categorias c ON p.categoria_id = c.id 
            WHERE p.codigo_barras = %s OR p.codigo = %s 
            AND p.ativo = true
            LIMIT 1
        """, (barcode, barcode))
        
        product = cursor.fetchone()
        
        if product:
            # Atualiza timestamp de leitura
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
    if conn is None:
        return []
        
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

# Função para criar venda
def create_sale(items, customer_name, payment_method, payment_value=None):
    conn = get_db_connection()
    if conn is None:
        return False, "Erro de conexão com o banco de dados"
        
    cursor = conn.cursor()
    
    try:
        # Calcular valor total
        total = sum(item['preco_venda'] * item['quantidade'] for item in items)
        
        # Inserir venda
        cursor.execute("""
            INSERT INTO vendas 
            (cliente_nome, valor_total, forma_pagamento, status) 
            VALUES (%s, %s, %s, 'concluida') 
            RETURNING id
        """, (customer_name, total, payment_method))
        
        venda_id = cursor.fetchone()[0]
        
        # Inserir itens da venda e atualizar estoque
        for item in items:
            cursor.execute("""
                INSERT INTO venda_itens 
                (venda_id, produto_id, quantidade, preco_unitario) 
                VALUES (%s, %s, %s, %s)
            """, (venda_id, item['id'], item['quantidade'], item['preco_venda']))
            
            cursor.execute("""
                UPDATE produtos 
                SET estoque = estoque - %s 
                WHERE id = %s
            """, (item['quantidade'], item['id']))
        
        conn.commit()
        return True, venda_id
    
    except Exception as e:
        conn.rollback()
        return False, str(e)
    
    finally:
        cursor.close()
        conn.close()

# Função para cadastrar novo produto
def create_product(product_data):
    conn = get_db_connection()
    if conn is None:
        return False, "Erro de conexão com o banco de dados"
        
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Verificar se código já existe
        if product_data.get('codigo'):
            cursor.execute("SELECT id FROM produtos WHERE codigo = %s", (product_data['codigo'],))
            if cursor.fetchone():
                return False, "Código já está em uso"
        
        # Verificar se código de barras já existe
        if product_data.get('codigo_barras'):
            cursor.execute("SELECT id FROM produtos WHERE codigo_barras = %s", (product_data['codigo_barras'],))
            if cursor.fetchone():
                return False, "Código de barras já está em uso"
        
        # Inserir novo produto
        cursor.execute("""
            INSERT INTO produtos (
                codigo, codigo_barras, nome, descricao, preco_custo, preco_venda, 
                estoque, estoque_minimo, categoria_id, unidade, ativo, 
                criado_em, atualizado_em
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, 
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING *
        """, (
            product_data.get('codigo'),
            product_data.get('codigo_barras'),
            product_data['nome'],
            product_data.get('descricao'),
            product_data.get('preco_custo', 0),
            product_data['preco_venda'],
            product_data.get('estoque', 0),
            product_data.get('estoque_minimo', 5),
            product_data.get('categoria_id'),
            product_data.get('unidade', 'un')
        ))
        
        new_product = dict(cursor.fetchone())
        conn.commit()
        return True, new_product
    
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao criar produto: {str(e)}"
    
    finally:
        cursor.close()
        conn.close()

# Função para obter categorias
def get_categories():
    conn = get_db_connection()
    if conn is None:
        return []
        
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cursor.execute("SELECT id, nome FROM categorias WHERE ativo = true ORDER BY nome")
        return [dict(row) for row in cursor.fetchall()]
    
    finally:
        cursor.close()
        conn.close()

# Função para obter estatísticas para o dashboard
def get_dashboard_data():
    conn = get_db_connection()
    if conn is None:
        # Retornar dados vazios se não conseguir conectar
        return {
            'total_produtos': 0,
            'estoque_baixo': 0,
            'valor_estoque': 0,
            'vendas_recentes_qtd': 0,
            'vendas_recentes_valor': 0,
            'produtos_mais_vendidos': [],
            'vendas_por_dia': []
        }
        
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        data = {}
        
        # Total de produtos
        cursor.execute("SELECT COUNT(*) FROM produtos WHERE ativo = true")
        data['total_produtos'] = cursor.fetchone()[0]
        
        # Produtos com estoque baixo
        cursor.execute("SELECT COUNT(*) FROM produtos WHERE ativo = true AND estoque <= estoque_minimo")
        data['estoque_baixo'] = cursor.fetchone()[0]
        
        # Valor total em estoque
        cursor.execute("SELECT SUM(estoque * preco_venda) FROM produtos WHERE ativo = true")
        data['valor_estoque'] = cursor.fetchone()[0] or 0
        
        # Vendas recentes (últimos 7 dias)
        cursor.execute("""
            SELECT COUNT(*), SUM(valor_total) 
            FROM vendas 
            WHERE criado_em >= CURRENT_DATE - INTERVAL '7 days'
        """)
        vendas_recentes = cursor.fetchone()
        data['vendas_recentes_qtd'] = vendas_recentes[0] or 0
        data['vendas_recentes_valor'] = vendas_recentes[1] or 0
        
        # Produtos mais vendidos (top 5)
        cursor.execute("""
            SELECT p.nome, SUM(vi.quantidade) as total_vendido
            FROM venda_itens vi
            JOIN produtos p ON vi.produto_id = p.id
            JOIN vendas v ON vi.venda_id = v.id
            WHERE v.criado_em >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY p.nome
            ORDER BY total_vendido DESC
            LIMIT 5
        """)
        data['produtos_mais_vendidos'] = [dict(row) for row in cursor.fetchall()]
        
        # Vendas por dia (últimos 15 dias)
        cursor.execute("""
            SELECT DATE(criado_em) as data, COUNT(*) as qtd_vendas, SUM(valor_total) as valor_total
            FROM vendas
            WHERE criado_em >= CURRENT_DATE - INTERVAL '15 days'
            GROUP BY DATE(criado_em)
            ORDER BY data
        """)
        data['vendas_por_dia'] = [dict(row) for row in cursor.fetchall()]
        
        return data
    
    finally:
        cursor.close()
        conn.close()

# Função para gerar recibo em HTML
def generate_receipt_html(sale_id, items, customer_name, payment_method, total, payment_value=None):
    # Header com estilos CSS
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Recibo de Venda #{sale_id}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                line-height: 1.5;
            }}
            .receipt {{
                max-width: 800px;
                margin: 0 auto;
                border: 1px solid #ddd;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 20px;
                border-bottom: 2px solid #333;
                padding-bottom: 10px;
            }}
            .info {{
                margin-bottom: 20px;
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 5px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 10px;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            .total {{
                text-align: right;
                font-size: 18px;
                font-weight: bold;
                margin-top: 20px;
                border-top: 2px solid #333;
                padding-top: 10px;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                font-size: 12px;
                color: #777;
            }}
            .barcode {{
                text-align: center;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="receipt">
            <div class="header">
                <h1>BarcodeScan PDV</h1>
                <h2>Recibo de Venda #{sale_id}</h2>
                <p>Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
            </div>
            
            <div class="info">
                <div class="info-row">
                    <span><strong>Cliente:</strong></span>
                    <span>{customer_name or 'Cliente não identificado'}</span>
                </div>
                <div class="info-row">
                    <span><strong>Forma de Pagamento:</strong></span>
                    <span>{payment_method}</span>
                </div>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Código</th>
                        <th>Qtde</th>
                        <th>Preço Unit.</th>
                        <th>Subtotal</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    # Adicionar itens da venda
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
    
    # Adicionar total e informações de pagamento
    html += f"""
                </tbody>
            </table>
            
            <div class="total">
                <p>Total: R$ {total:.2f}</p>
    """
    
    if payment_method == "Dinheiro" and payment_value and payment_value > total:
        html += f"""
                <p>Valor Pago: R$ {payment_value:.2f}</p>
                <p>Troco: R$ {payment_value - total:.2f}</p>
        """
    
    # Adicionar rodapé
    html += f"""
            </div>
            
            <div class="footer">
                <p>Obrigado por sua compra!</p>
                <p>Este documento não tem valor fiscal.</p>
                <p>BarcodeScan PDV - Sistema de Gestão com Leitura de Código de Barras</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

# Função para download do recibo
def get_receipt_download_link(html_string, filename="recibo.html"):
    b64 = base64.b64encode(html_string.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="{filename}">Baixar Recibo</a>'
    return href

# Interface principal
def main():
    # Sidebar
    st.sidebar.title("BarcodeScan PDV")
    menu = st.sidebar.radio(
        "Menu", 
        ["Dashboard", "Escanear Produto", "Cadastrar Produto", "Produtos", "Vendas"]
    )
    
    # Dashboard
    if menu == "Dashboard":
        st.title("Dashboard")
        
        # Obter dados para o dashboard
        try:
            dashboard_data = get_dashboard_data()
            
            # Métricas principais
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total de Produtos", f"{dashboard_data['total_produtos']}")
            
            with col2:
                st.metric("Estoque Baixo", f"{dashboard_data['estoque_baixo']}")
            
            with col3:
                st.metric("Vendas (7 dias)", f"{dashboard_data['vendas_recentes_qtd']}")
            
            with col4:
                st.metric("Valor em Estoque", f"R$ {dashboard_data['valor_estoque']:.2f}")
            
            # Gráficos
            st.subheader("Análise de Vendas")
            
            if HAS_PLOTLY and 'pd' in globals():
                col1, col2 = st.columns(2)
                
                with col1:
                    # Gráfico de vendas por dia
                    if dashboard_data['vendas_por_dia']:
                        df_vendas = pd.DataFrame(dashboard_data['vendas_por_dia'])
                        df_vendas['data'] = pd.to_datetime(df_vendas['data'])
                        
                        fig = px.bar(
                            df_vendas, 
                            x='data', 
                            y='valor_total', 
                            title='Vendas Diárias (15 dias)',
                            labels={'data': 'Data', 'valor_total': 'Valor Total (R$)'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Sem dados de vendas para exibir.")
                
                with col2:
                    # Gráfico de produtos mais vendidos
                    if dashboard_data['produtos_mais_vendidos']:
                        df_produtos = pd.DataFrame(dashboard_data['produtos_mais_vendidos'])
                        
                        fig = px.pie(
                            df_produtos, 
                            names='nome', 
                            values='total_vendido', 
                            title='Produtos Mais Vendidos (30 dias)'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Sem dados de produtos vendidos para exibir.")
            else:
                # Exibir dados em formato tabular simples se não tiver plotly
                st.write("Vendas nos últimos 15 dias:")
                if dashboard_data['vendas_por_dia']:
                    st.write(dashboard_data['vendas_por_dia'])
                else:
                    st.info("Sem dados de vendas para exibir.")
                
                st.write("Produtos mais vendidos nos últimos 30 dias:")
                if dashboard_data['produtos_mais_vendidos']:
                    st.write(dashboard_data['produtos_mais_vendidos'])
                else:
                    st.info("Sem dados de produtos vendidos para exibir.")
            
            # Produtos com estoque baixo
            st.subheader("Produtos com Estoque Baixo")
            
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            cursor.execute("""
                SELECT p.nome, p.codigo, p.codigo_barras, p.estoque, p.estoque_minimo, c.nome as categoria
                FROM produtos p
                LEFT JOIN categorias c ON p.categoria_id = c.id
                WHERE p.ativo = true AND p.estoque <= p.estoque_minimo
                ORDER BY p.estoque ASC
                LIMIT 10
            """)
            
            estoque_baixo = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            
            if estoque_baixo:
                if 'pd' in globals():
                    df_estoque = pd.DataFrame(estoque_baixo)
                    st.dataframe(df_estoque, use_container_width=True)
                else:
                    # Exibir como tabela simples se não tiver pandas
                    for item in estoque_baixo:
                        st.write(f"{item['nome']} - Estoque: {item['estoque']} (Mínimo: {item['estoque_minimo']})")
            else:
                st.success("Não há produtos com estoque baixo!")
                
        except Exception as e:
            st.error(f"Erro ao carregar dashboard: {str(e)}")
    
    # Página de Escaneamento
    elif menu == "Escanear Produto":
        st.title("Escaneamento de Produto")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Entrada manual
            barcode_input = st.text_input("Código de Barras", 
                                        placeholder="Digite ou escaneie o código")
            
            # Ou upload de imagem
            uploaded_file = st.file_uploader("Ou envie uma imagem", 
                                            type=["jpg", "jpeg", "png"])
            
            # Ou usar a câmera (se suportado)
            if HAS_IMAGE_SUPPORT:
                camera_input = st.camera_input("Ou use a câmera")
            else:
                camera_input = None
                st.info("Captura de câmera não disponível neste ambiente")
            
            barcode = None
            
            # Processar código de barras
            if barcode_input:
                barcode = barcode_input
                st.success(f"Código inserido: {barcode}")
            
            elif uploaded_file and HAS_IMAGE_SUPPORT:
                try:
                    image = Image.open(uploaded_file)
                    barcode = decode_barcode(image)
                    
                    if barcode:
                        st.success(f"Código detectado: {barcode}")
                    else:
                        st.warning("Nenhum código detectado na imagem")
                except Exception as e:
                    st.error(f"Erro ao processar imagem: {str(e)}")
            
            elif camera_input and HAS_IMAGE_SUPPORT:
                try:
                    image = Image.open(camera_input)
                    barcode = decode_barcode(image)
                except:
                    st.error("Erro ao processar imagem da câmera")
                
                if barcode:
                    st.success(f"Código detectado: {barcode}")
                else:
                    st.warning("Nenhum código detectado")
        
        with col2:
            # Mostrar produto se encontrado
            if barcode:
                product = get_product_by_barcode(barcode)
                
                if product:
                    st.markdown("### Produto Encontrado")
                    st.markdown(f"**Nome:** {product['nome']}")
                    st.markdown(f"**Código:** {product.get('codigo', 'N/A')}")
                    st.markdown(f"**Código de Barras:** {product.get('codigo_barras', 'N/A')}")
                    st.markdown(f"**Preço:** R$ {product['preco_venda']:.2f}")
                    st.markdown(f"**Estoque:** {product.get('estoque', 0)} {product.get('unidade', 'un')}")
                    
                    if product.get('categoria_nome'):
                        st.markdown(f"**Categoria:** {product['categoria_nome']}")
                    
                    if product.get('descricao'):
                        st.markdown(f"**Descrição:** {product['descricao']}")
                    
                    # Adicionar à venda
                    if st.button("Adicionar à Venda"):
                        if 'cart' not in st.session_state:
                            st.session_state.cart = []
                        
                        # Verificar se já está no carrinho
                        for i, item in enumerate(st.session_state.cart):
                            if item['id'] == product['id']:
                                st.session_state.cart[i]['quantidade'] += 1
                                break
                        else:
                            st.session_state.cart.append({
                                'id': product['id'],
                                'nome': product['nome'],
                                'codigo_barras': product.get('codigo_barras', ''),
                                'preco_venda': product['preco_venda'],
                                'quantidade': 1
                            })
                        
                        st.success(f"Produto adicionado à venda!")
                        time.sleep(1)
                        st.experimental_rerun()
                else:
                    st.error("Produto não encontrado")
    
    # Página de Cadastro de Produto
    elif menu == "Cadastrar Produto":
        st.title("Cadastrar Novo Produto")
        
        # Formulário de cadastro
        with st.form("cadastro_produto"):
            # Layout em duas colunas
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome do Produto *", key="nome")
                codigo = st.text_input("Código (SKU)", key="codigo")
                codigo_barras = st.text_input("Código de Barras (EAN/UPC)", key="codigo_barras")
                
                # Verificar se tem categorias
                categorias = get_categories()
                if categorias:
                    categoria_id = st.selectbox(
                        "Categoria", 
                        options=[c["id"] for c in categorias],
                        format_func=lambda x: next((c["nome"] for c in categorias if c["id"] == x), ""),
                        key="categoria_id"
                    )
                else:
                    categoria_id = None
                    st.warning("Não há categorias cadastradas.")
                
                descricao = st.text_area("Descrição", key="descricao")
            
            with col2:
                preco_custo = st.number_input("Preço de Custo (R$)", 
                                           min_value=0.0, 
                                           step=0.01, 
                                           format="%.2f",
                                           key="preco_custo")
                
                preco_venda = st.number_input("Preço de Venda (R$) *", 
                                          min_value=0.01, 
                                          step=0.01, 
                                          format="%.2f",
                                          key="preco_venda")
                
                estoque = st.number_input("Estoque Inicial", 
                                      min_value=0, 
                                      step=1,
                                      key="estoque")
                
                estoque_minimo = st.number_input("Estoque Mínimo", 
                                             min_value=0, 
                                             value=5, 
                                             step=1,
                                             key="estoque_minimo")
                
                unidade = st.selectbox(
                    "Unidade", 
                    options=["un", "kg", "g", "l", "ml", "pct", "cx", "par"],
                    key="unidade"
                )
            
            # Uso de câmera para ler código de barras
            st.subheader("Ler código de barras com câmera")
            
            if HAS_IMAGE_SUPPORT and HAS_BARCODE_SUPPORT:
                use_camera = st.checkbox("Usar câmera para código de barras")
                
                if use_camera:
                    camera_input = st.camera_input("Capturar código de barras")
                    if camera_input:
                        try:
                            image = Image.open(camera_input)
                            barcode = decode_barcode(image)
                            
                            if barcode:
                                st.success(f"Código detectado: {barcode}")
                                # Preencher campo de código de barras
                                codigo_barras = barcode
                                st.session_state['codigo_barras'] = barcode
                            else:
                                st.warning("Nenhum código detectado na imagem. Tente novamente.")
                        except:
                            st.error("Erro ao processar imagem da câmera")
            else:
                st.info("Recurso de leitura de código de barras não disponível neste ambiente")
            
            # Botão de cadastro
            submit = st.form_submit_button("Cadastrar Produto")
            
            if submit:
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
                    
                    # Enviar para cadastro
                    success, result = create_product(produto_data)
                    
                    if success:
                        st.success("Produto cadastrado com sucesso!")
                        st.json(result)
                    else:
                        st.error(f"Erro ao cadastrar produto: {result}")
    
    # Página de Produtos
    elif menu == "Produtos":
        st.title("Catálogo de Produtos")
        
        # Filtro de busca
        search = st.text_input("Buscar produtos", placeholder="Nome, código ou código de barras")
        
        # Obter produtos
        products = get_all_products()
        
        # Aplicar filtro
        if search:
            search = search.lower()
            products = [p for p in products if 
                       search in p['nome'].lower() or 
                       (p.get('codigo') and search in str(p['codigo']).lower()) or
                       (p.get('codigo_barras') and search in str(p['codigo_barras']).lower())]
        
        # Mostrar produtos
        if not products:
            st.info("Nenhum produto encontrado.")
        else:
            # Criar tabela
            if 'pd' in globals():
                table_data = []
                for p in products:
                    table_data.append({
                        "ID": p['id'],
                        "Nome": p['nome'],
                        "Código": p.get('codigo', ''),
                        "Código de Barras": p.get('codigo_barras', ''),
                        "Preço": f"R$ {p['preco_venda']:.2f}",
                        "Estoque": p.get('estoque', 0),
                        "Categoria": p.get('categoria_nome', '')
                    })
                
                st.dataframe(table_data, use_container_width=True)
            else:
                # Alternativa simples sem pandas
                st.write("Produtos encontrados:")
                for p in products:
                    st.write(f"{p['id']} - {p['nome']} - R$ {p['preco_venda']:.2f} - Estoque: {p.get('estoque', 0)}")
            
            # Permite adicionar produto selecionado à venda
            product_id = st.selectbox("Selecionar produto para venda", 
                                     options=[p['id'] for p in products],
                                     format_func=lambda x: next((p['nome'] for p in products if p['id'] == x), ''))
            
            if st.button("Adicionar à Venda"):
                selected_product = next((p for p in products if p['id'] == product_id), None)
                
                if selected_product:
                    if 'cart' not in st.session_state:
                        st.session_state.cart = []
                    
                    # Verificar se já está no carrinho
                    for i, item in enumerate(st.session_state.cart):
                        if item['id'] == selected_product['id']:
                            st.session_state.cart[i]['quantidade'] += 1
                            break
                    else:
                        st.session_state.cart.append({
                            'id': selected_product['id'],
                            'nome': selected_product['nome'],
                            'codigo_barras': selected_product.get('codigo_barras', ''),
                            'preco_venda': selected_product['preco_venda'],
                            'quantidade': 1
                        })
                    
                    st.success(f"Produto adicionado à venda!")
                    time.sleep(1)
                    st.experimental_rerun()
    
    # Página de Vendas
    elif menu == "Vendas":
        st.title("Realizar Venda")
        
        # Inicializar carrinho se não existir
        if 'cart' not in st.session_state:
            st.session_state.cart = []
        
        # Exibir itens no carrinho
        if not st.session_state.cart:
            st.info("Carrinho vazio. Adicione produtos pelo escaneamento ou catálogo.")
        else:
            # Mostrar carrinho
            st.subheader("Produtos no Carrinho")
            
            if 'pd' in globals():
                # Versão com pandas e editor de dados avançado
                cart_data = []
                for i, item in enumerate(st.session_state.cart):
                    cart_data.append({
                        "Nome": item['nome'],
                        "Código": item.get('codigo_barras', ''),
                        "Preço Unit.": f"R$ {item['preco_venda']:.2f}",
                        "Qtde": item['quantidade'],
                        "Subtotal": f"R$ {item['preco_venda'] * item['quantidade']:.2f}",
                        "Remover": False
                    })
                
                edited_df = st.data_editor(
                    cart_data,
                    column_config={
                        "Qtde": st.column_config.NumberColumn(
                            "Qtde",
                            min_value=1,
                            step=1,
                        ),
                        "Remover": st.column_config.CheckboxColumn(
                            "Remover",
                            help="Marque para remover",
                            default=False,
                        ),
                    },
                    disabled=["Nome", "Código", "Preço Unit.", "Subtotal"],
                    hide_index=True,
                    use_container_width=True
                )
            else:
                # Versão simples sem pandas
                edited_df = []
                for i, item in enumerate(st.session_state.cart):
                    st.write(f"{item['nome']} - {item['quantidade']} x R$ {item['preco_venda']:.2f} = R$ {item['preco_venda'] * item['quantidade']:.2f}")
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        new_qtd = st.number_input(f"Quantidade de {item['nome']}", 
                                                 min_value=1, 
                                                 value=item['quantidade'], 
                                                 key=f"qtd_{i}")
                    with col2:
                        remove = st.checkbox(f"Remover {item['nome']}", key=f"rem_{i}")
                    
                    edited_df.append({
                        "Qtde": new_qtd,
                        "Remover": remove
                    })
            
            # Atualizar quantidades e remover itens
            for i, (row, item) in enumerate(zip(edited_df, st.session_state.cart)):
                if row["Remover"]:
                    st.session_state.cart[i] = None
                else:
                    st.session_state.cart[i]['quantidade'] = row["Qtde"]
            
            # Remover itens marcados para remoção
            st.session_state.cart = [item for item in st.session_state.cart if item is not None]
            
            # Calcular total
            total = sum(item['preco_venda'] * item['quantidade'] for item in st.session_state.cart)
            
            # Mostrar total
            st.markdown(f"### Total: R$ {total:.2f}")
            
            # Opções de pagamento
            col1, col2 = st.columns(2)
            
            with col1:
                payment_method = st.selectbox(
                    "Forma de Pagamento",
                    ["Dinheiro", "Cartão de Crédito", "Cartão de Débito", "PIX"]
                )
                
                payment_value = None
                if payment_method == "Dinheiro":
                    payment_value = st.number_input(
                        "Valor Recebido (R$)",
                        min_value=float(total),
                        value=float(total),
                        step=1.0
                    )
                    
                    if payment_value > total:
                        st.info(f"Troco: R$ {payment_value - total:.2f}")
            
            with col2:
                customer_name = st.text_input("Cliente (opcional)")
            
            # Finalizar venda
            if st.button("Finalizar Venda", type="primary"):
                success, result = create_sale(
                    st.session_state.cart,
                    customer_name,
                    payment_method,
                    payment_value
                )
                
                if success:
                    st.success("Venda realizada com sucesso!")
                    st.balloons()
                    
                    # Gerar recibo HTML
                    receipt_html = generate_receipt_html(
                        result,  # sale_id
                        st.session_state.cart,
                        customer_name,
                        payment_method,
                        total,
                        payment_value
                    )
                    
                    # Botão para download do recibo
                    st.markdown(
                        get_receipt_download_link(
                            receipt_html, 
                            f"recibo_venda_{result}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                        ),
                        unsafe_allow_html=True
                    )
                    
                    # Recibo visual
                    st.markdown("### Recibo da Venda")
                    st.markdown(f"**Data:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
                    st.markdown(f"**Cliente:** {customer_name or 'Cliente não identificado'}")
                    st.markdown(f"**Forma de Pagamento:** {payment_method}")
                    st.markdown(f"**Total:** R$ {total:.2f}")
                    
                    if payment_method == "Dinheiro" and payment_value > total:
                        st.markdown(f"**Valor Pago:** R$ {payment_value:.2f}")
                        st.markdown(f"**Troco:** R$ {payment_value - total:.2f}")
                    
                    # Limpar carrinho
                    st.session_state.cart = []
                else:
                    st.error(f"Erro ao finalizar venda: {result}")
            
            # Cancelar venda
            if st.button("Cancelar Venda"):
                st.session_state.cart = []
                st.experimental_rerun()

if __name__ == "__main__":
    main()
