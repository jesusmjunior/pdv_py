"""
Módulo contendo as views (interfaces) do sistema PDV
"""

import time
import datetime
import pandas as pd
import streamlit as st
from streamlit_webrtc import webrtc_streamer

from models import Categoria, Produto, Venda
from barcode_scanner import BarcodeVideoProcessor
from config import PAYMENT_CONFIG, STOCK_CONFIG

def mostrar_pdv():
    """Interface principal do PDV (Ponto de Venda)"""
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
            produto = Produto.get_by_barcode(barcode_input)
            
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
                PAYMENT_CONFIG["methods"]
            )
            
            observacoes = st.text_area("Observações", height=100)
            
            if st.button("Finalizar Venda", use_container_width=True):
                if st.session_state.cart:
                    venda_id = Venda.registrar(
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
                        st.error("Erro ao registrar venda. Verifique o estoque dos produtos.")
                else:
                    st.error("Não é possível finalizar uma venda sem produtos.")
    
    with col2:
        # Lista de produtos
        st.subheader("Produtos Disponíveis")
        
        # Pesquisa
        pesquisa = st.text_input("Pesquisar produto:", key="search_pdv")
        
        # Obter produtos
        df_produtos = Produto.get_all()
        
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
    """Interface de gerenciamento de produtos"""
    st.title("📦 Gerenciamento de Produtos")
    
    # Tabs para listar e adicionar produtos
    tab1, tab2 = st.tabs(["Lista de Produtos", "Adicionar/Editar Produto"])
    
    with tab1:
        # Pesquisa
        pesquisa = st.text_input("Pesquisar produto:", key="search_produtos")
        
        # Obter produtos
        df_produtos = Produto.get_all()
        
        # Filtrar por pesquisa
        if pesquisa:
            df_produtos = df_produtos[
                df_produtos['nome'].str.contains(pesquisa, case=False) | 
                df_produtos['codigo'].str.contains(pesquisa, case=False) |
                (df_produtos['barcode'].str.contains(pesquisa, case=False) if 'barcode' in df_produtos else False)
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
                    produto = Produto.get_by_id(produto_id_para_acao)
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
                        if Produto.delete(produto_id_para_acao):
                            st.success(f"Produto com ID {produto_id_para_acao} excluído com sucesso!")
                            st.session_state.pop('confirmar_exclusao', None)
                            st.experimental_rerun()
                        else:
                            st.error(f"Erro ao excluir produto. Verifique se não há vendas associadas.")
                    else:
                        # Solicitar confirmação
                        st.session_state.confirmar_exclusao = produto_id_para_acao
                        st.warning(f"Clique novamente em 'Excluir Produto' para confirmar a exclusão do produto {produto_id_para_acao}")
    
    with tab2:
        # Obter lista de categorias para o select
        df_categorias = Categoria.get_all()
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
                        Produto.update(
                            produto_id, codigo, nome, descricao, preco, 
                            estoque, categoria_id, barcode, imagem_url
                        )
                        st.success(f"Produto '{nome}' atualizado com sucesso!")
                        st.session_state.pop('produto_em_edicao', None)
                        st.session_state.modo_edicao = False
                    else:  # Adição
                        novo_id = Produto.add(
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
    """Interface de gerenciamento de categorias"""
    st.title("🏷️ Gerenciamento de Categorias")
    
    # Tabs para listar e adicionar categorias
    tab1, tab2 = st.tabs(["Lista de Categorias", "Adicionar/Editar Categoria"])
    
    with tab1:
        # Obter categorias
        df_categorias = Categoria.get_all()
        
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
                        if Categoria.delete(categoria_id_para_acao):
                            st.success(f"Categoria com ID {categoria_id_para_acao} excluída com sucesso!")
                            st.session_state.pop('confirmar_exclusao_categoria', None)
                            st.experimental_rerun()
                        else:
                            st.error(f"Erro ao excluir categoria. Verifique se não há produtos associados.")
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
                        Categoria.update(categoria_id, nome, descricao)
                        st.success(f"Categoria '{nome}' atualizada com sucesso!")
                        st.session_state.pop('categoria_em_edicao', None)
                        st.session_state.modo_edicao_categoria = False
                    else:  # Adição
                        novo_id = Categoria.add(nome, descricao)
                        st.success(f"Categoria '{nome}' adicionada com sucesso! ID: {novo_id}")
                    
                    time.sleep(1)
                    st.experimental_rerun()
        
        # Botão para cancelar edição
        if categoria_em_edicao and st.button("Cancelar Edição", use_container_width=True):
            st.session_state.pop('categoria_em_edicao', None)
            st.session_state.modo_edicao_categoria = False
            st.experimental_rerun()

def mostrar_relatorios():
    """Interface de relatórios do sistema"""
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
        df_vendas = Venda.get_all(data_inicio_dt, data_fim_dt)
        
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
                detalhes_venda = Venda.get_detalhes(venda_selecionada)
                
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
        df_produtos = Produto.get_all()
        
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
        df_produtos = Produto.get_all()
        
        if df_produtos.empty:
            st.info("Nenhum produto cadastrado.")
        else:
            # Resumo de estoque
            total_itens = df_produtos['estoque'].sum()
            
            st.metric("Total de Itens em Estoque", total_itens)
            
            # Produtos com estoque baixo
            low_stock_threshold = STOCK_CONFIG["low_stock_threshold"]
            st.subheader(f"Produtos com Estoque Baixo (menos de {low_stock_threshold} unidades)")
            df_estoque_baixo = df_produtos[df_produtos['estoque'] < low_stock_threshold].sort_values('estoque')
            
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