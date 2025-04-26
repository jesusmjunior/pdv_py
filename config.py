"""
Configurações do sistema ORION PDV
"""

# Configuração do banco de dados PostgreSQL
DB_CONFIG = {
    "host": "34.95.252.164",
    "database": "pdv",
    "user": "postgres",
    "password": "pdv@2025",
    "port": 5432,
    "sslmode": "require"
}

# Configurações da aplicação
APP_CONFIG = {
    "title": "ORION PDV",
    "icon": "🛒",
    "layout": "wide",
    "sidebar_state": "expanded",
    "version": "1.0.0",
    "company": "ORION Systems",
    "year": "2025"
}

# Configurações de estoque
STOCK_CONFIG = {
    "low_stock_threshold": 10  # Limite para considerar estoque baixo
}

# Configurações de pagamento
PAYMENT_CONFIG = {
    "methods": ["Dinheiro", "Cartão de Crédito", "Cartão de Débito", "PIX"]
}

# Configurações do scanner de código de barras
BARCODE_CONFIG = {
    "detection_interval": 1.0  # Intervalo entre detecções em segundos
}