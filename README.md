# BarcodeScan PDV

Sistema de Ponto de Venda com Leitura de Código de Barras integrado ao PostgreSQL na nuvem.

## Funcionalidades

- **Dashboard**: Visualização rápida de métricas importantes do negócio
- **Leitura de Código de Barras**: Identificação rápida de produtos via câmera ou entrada manual
- **Gerenciamento de Produtos**: Cadastro e listagem de produtos
- **Vendas**: Processamento completo de vendas com recibo HTML

## Requisitos Mínimos

- Python 3.7+
- Streamlit
- psycopg2-binary

```bash
pip install streamlit psycopg2-binary
```

## Dependências Opcionais

Para funcionalidades avançadas como leitura de código de barras e gráficos:

```bash
pip install pandas pillow opencv-python-headless pyzbar plotly
```

## Executando Localmente

```bash
streamlit run app.py
```

## Implantação no Streamlit Cloud

1. Faça fork deste repositório no GitHub
2. Conecte ao Streamlit Cloud
3. Implante a partir do seu repositório

## Configuração do Banco de Dados

O sistema está configurado para conectar com PostgreSQL hospedado no Google Cloud. Os detalhes de conexão estão no arquivo app.py.

## Recursos

- Escaneamento de produtos por código de barras
- Dashboard interativo com métricas importantes
- Cadastro e gerenciamento de produtos
- Sistema de vendas com carrinho
- Recibos HTML para download

## Notas

Este sistema foi projetado para ser altamente resistente a problemas de dependências em ambientes de nuvem, funcionando mesmo quando algumas bibliotecas não estão disponíveis.