"""
Módulo contendo as classes de modelo do sistema PDV
"""

import uuid
import pandas as pd
from database import execute_query, query_to_dataframe

class Categoria:
    """Classe para operações com categorias de produtos"""
    
    @staticmethod
    def get_all():
        """
        Retorna todas as categorias
        
        Returns:
            pd.DataFrame: DataFrame com todas as categorias
        """
        return query_to_dataframe("SELECT * FROM categorias ORDER BY nome")
    
    @staticmethod
    def add(nome, descricao=""):
        """
        Adiciona uma nova categoria
        
        Args:
            nome (str): Nome da categoria
            descricao (str, optional): Descrição da categoria. Defaults to "".
            
        Returns:
            int: ID da categoria criada
        """
        query = "INSERT INTO categorias (nome, descricao) VALUES (%s, %s) RETURNING id"
        params = (nome, descricao)
        return execute_query(query, params)
    
    @staticmethod
    def update(cat_id, nome, descricao):
        """
        Atualiza uma categoria existente
        
        Args:
            cat_id (int): ID da categoria
            nome (str): Novo nome
            descricao (str): Nova descrição
        """
        query = "UPDATE categorias SET nome = %s, descricao = %s WHERE id = %s"
        params = (nome, descricao, cat_id)
        execute_query(query, params)
    
    @staticmethod
    def delete(cat_id):
        """
        Exclui uma categoria
        
        Args:
            cat_id (int): ID da categoria
            
        Returns:
            bool: True se excluído com sucesso, False caso contrário
        """
        try:
            query = "DELETE FROM categorias WHERE id = %s"
            execute_query(query, (cat_id,))
            return True
        except Exception:
            return False


class Produto:
    """Classe para operações com produtos"""
    
    @staticmethod
    def get_all():
        """
        Retorna todos os produtos
        
        Returns:
            pd.DataFrame: DataFrame com todos os produtos e suas categorias
        """
        query = """
        SELECT p.*, c.nome as categoria_nome 
        FROM produtos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        ORDER BY p.nome
        """
        return query_to_dataframe(query)
    
    @staticmethod
    def get_by_id(produto_id):
        """
        Retorna um produto pelo ID
        
        Args:
            produto_id (int): ID do produto
            
        Returns:
            pd.Series: Produto encontrado ou None
        """
        query = """
        SELECT p.*, c.nome as categoria_nome 
        FROM produtos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.id = %s
        """
        df = query_to_dataframe(query, [produto_id])
        return df.iloc[0] if not df.empty else None
    
    @staticmethod
    def get_by_barcode(barcode):
        """
        Retorna um produto pelo código de barras
        
        Args:
            barcode (str): Código de barras
            
        Returns:
            pd.Series: Produto encontrado ou None
        """
        query = """
        SELECT p.*, c.nome as categoria_nome 
        FROM produtos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.barcode = %s
        """
        df = query_to_dataframe(query, [barcode])
        return df.iloc[0] if not df.empty else None
    
    @staticmethod
    def add(codigo, nome, descricao, preco, estoque, categoria_id, barcode=None, imagem_url=None):
        """
        Adiciona um novo produto
        
        Args:
            codigo (str): Código do produto
            nome (str): Nome do produto
            descricao (str): Descrição do produto
            preco (float): Preço do produto
            estoque (int): Quantidade em estoque
            categoria_id (int): ID da categoria
            barcode (str, optional): Código de barras. Defaults to None.
            imagem_url (str, optional): URL da imagem. Defaults to None.
            
        Returns:
            int: ID do produto criado
        """
        query = """
        INSERT INTO produtos (codigo, nome, descricao, preco, estoque, categoria_id, barcode, imagem_url) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """
        params = (codigo, nome, descricao, preco, estoque, categoria_id, barcode, imagem_url)
        return execute_query(query, params)
    
    @staticmethod
    def update(produto_id, codigo, nome, descricao, preco, estoque, categoria_id, barcode=None, imagem_url=None):
        """
        Atualiza um produto existente
        
        Args:
            produto_id (int): ID do produto
            codigo (str): Código do produto
            nome (str): Nome do produto
            descricao (str): Descrição do produto
            preco (float): Preço do produto
            estoque (int): Quantidade em estoque
            categoria_id (int): ID da categoria
            barcode (str, optional): Código de barras. Defaults to None.
            imagem_url (str, optional): URL da imagem. Defaults to None.
        """
        query = """
        UPDATE produtos 
        SET codigo = %s, nome = %s, descricao = %s, preco = %s, estoque = %s, 
            categoria_id = %s, barcode = %s, imagem_url = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        params = (codigo, nome, descricao, preco, estoque, categoria_id, barcode, imagem_url, produto_id)
        execute_query(query, params)
    
    @staticmethod
    def delete(produto_id):
        """
        Exclui um produto
        
        Args:
            produto_id (int): ID do produto
            
        Returns:
            bool: True se excluído com sucesso, False caso contrário
        """
        try:
            query = "DELETE FROM produtos WHERE id = %s"
            execute_query(query, (produto_id,))
            return True
        except Exception:
            return False
    
    @staticmethod
    def update_stock(produto_id, quantidade):
        """
        Atualiza o estoque de um produto
        
        Args:
            produto_id (int): ID do produto
            quantidade (int): Quantidade a ser reduzida do estoque
        """
        query = """
        UPDATE produtos 
        SET estoque = estoque - %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        params = (quantidade, produto_id)
        execute_query(query, params)


class Venda:
    """Classe para operações com vendas"""
    
    @staticmethod
    def registrar(items, total, forma_pagamento, observacoes=""):
        """
        Registra uma nova venda
        
        Args:
            items (list): Lista de itens da venda
            total (float): Valor total da venda
            forma_pagamento (str): Forma de pagamento
            observacoes (str, optional): Observações. Defaults to "".
            
        Returns:
            str: ID da venda criada ou None em caso de erro
        """
        conn = None
        cur = None
        try:
            from database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            
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
            if conn:
                conn.rollback()
            return None
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    @staticmethod
    def get_all(data_inicio=None, data_fim=None):
        """
        Retorna todas as vendas
        
        Args:
            data_inicio (datetime, optional): Data inicial para filtro. Defaults to None.
            data_fim (datetime, optional): Data final para filtro. Defaults to None.
            
        Returns:
            pd.DataFrame: DataFrame com todas as vendas
        """
        query = "SELECT * FROM vendas WHERE 1=1"
        params = []
        
        if data_inicio:
            query += " AND data_venda >= %s"
            params.append(data_inicio)
        
        if data_fim:
            query += " AND data_venda <= %s"
            params.append(data_fim)
        
        query += " ORDER BY data_venda DESC"
        
        return query_to_dataframe(query, params)
    
    @staticmethod
    def get_detalhes(venda_id):
        """
        Retorna os detalhes de uma venda
        
        Args:
            venda_id (str): ID da venda
            
        Returns:
            pd.DataFrame: DataFrame com os itens da venda
        """
        query = """
        SELECT vi.*, p.nome as produto_nome, p.codigo as produto_codigo
        FROM venda_itens vi
        JOIN produtos p ON vi.produto_id = p.id
        WHERE vi.venda_id = %s
        """
        return query_to_dataframe(query, [venda_id])