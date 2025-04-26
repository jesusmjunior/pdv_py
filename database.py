"""
Módulo de conexão e operações com o banco de dados PostgreSQL
"""

import psycopg2
import pandas as pd
from config import DB_CONFIG

def get_db_connection():
    """
    Estabelece conexão com o banco de dados PostgreSQL
    
    Returns:
        conn: Objeto de conexão com o banco de dados
    """
    conn = psycopg2.connect(
        host=DB_CONFIG["host"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        port=DB_CONFIG["port"],
        sslmode=DB_CONFIG["sslmode"]
    )
    return conn

def execute_query(query, params=None, fetch=False, fetch_all=True):
    """
    Executa uma query no banco de dados
    
    Args:
        query (str): Query SQL a ser executada
        params (tuple, optional): Parâmetros para a query. Defaults to None.
        fetch (bool, optional): Se deve retornar dados. Defaults to False.
        fetch_all (bool, optional): Se deve retornar todos os registros ou apenas um. Defaults to True.
    
    Returns:
        result: Resultado da query (registros, id ou None)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    result = None
    
    try:
        cur.execute(query, params)
        
        if fetch:
            if fetch_all:
                result = cur.fetchall()
            else:
                result = cur.fetchone()
        else:
            # Se a query contém RETURNING, pegar o resultado
            if "RETURNING" in query.upper():
                result = cur.fetchone()[0]
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()
    
    return result

def query_to_dataframe(query, params=None):
    """
    Executa uma query e retorna o resultado como DataFrame
    
    Args:
        query (str): Query SQL a ser executada
        params (tuple, optional): Parâmetros para a query. Defaults to None.
    
    Returns:
        pd.DataFrame: DataFrame com o resultado da query
    """
    conn = get_db_connection()
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df

def init_database():
    """
    Inicializa o banco de dados criando as tabelas necessárias
    """
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