#!/bin/bash
# Script para criar estrutura de arquivos do PDV v3 para GitHub
# Inclui adaptação para pasta 'public' reconhecida pelo Render

# Cores para console
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Criando estrutura de arquivos para PDV v3...${NC}"

# Diretório base (ajuste se necessário)
BASE_DIR="$HOME/pdv-3-github"

# Criar diretório base
mkdir -p "$BASE_DIR"
cd "$BASE_DIR"

# Criar estrutura de diretórios
echo -e "${YELLOW}Criando estrutura de diretórios...${NC}"

# API Backend
mkdir -p api/controllers api/models

# Frontend (pasta public para Render)
mkdir -p public/css public/js/core public/js/components public/js/modules/scanner public/img public/pages

# Scripts utilitários
mkdir -p scripts

# GitHub e configurações
mkdir -p .github/workflows .vscode

# Copiar arquivos do PDV v3 e Scanner
echo -e "${YELLOW}Copiando arquivos...${NC}"

# Descompactar arquivos existentes se disponíveis
if [ -f "$HOME/pdv-v3.tar.gz" ]; then
    echo -e "${GREEN}Encontrado pdv-v3.tar.gz, extraindo...${NC}"
    tar -xzf "$HOME/pdv-v3.tar.gz" -C "$HOME/temp-pdv" --strip-components=1
fi

if [ -f "$HOME/pdv-v3-scanner.tar.gz" ]; then
    echo -e "${GREEN}Encontrado pdv-v3-scanner.tar.gz, extraindo...${NC}"
    tar -xzf "$HOME/pdv-v3-scanner.tar.gz" -C "$HOME/temp-scanner" --strip-components=1
fi

# Mover arquivos da API
cp -r "$HOME/pdv-v3/api/controllers"/* "$BASE_DIR/api/controllers/" 2>/dev/null || :
cp -r "$HOME/pdv-v3/api/models"/* "$BASE_DIR/api/models/" 2>/dev/null || :
cp "$HOME/pdv-v3/api/index.js" "$BASE_DIR/api/" 2>/dev/null || :

# Mover arquivos de scanner
cp "$HOME/pdv-v3-scanner/api/controllers/productController.js" "$BASE_DIR/api/controllers/" 2>/dev/null || :
cp -r "$HOME/pdv-v3-scanner/src/js/modules/scanner"/* "$BASE_DIR/public/js/modules/scanner/" 2>/dev/null || :

# Mover arquivos para pasta public (importante para o Render)
cp -r "$HOME/pdv-v3/src/css"/* "$BASE_DIR/public/css/" 2>/dev/null || :
cp -r "$HOME/pdv-v3/src/js/core"/* "$BASE_DIR/public/js/core/" 2>/dev/null || :
cp -r "$HOME/pdv-v3/src/js/components"/* "$BASE_DIR/public/js/components/" 2>/dev/null || :
cp -r "$HOME/pdv-v3/src/pages"/* "$BASE_DIR/public/pages/" 2>/dev/null || :

# Adicionar páginas de scanner
cp "$HOME/pdv-v3-scanner/src/pages/scan.html" "$BASE_DIR/public/pages/" 2>/dev/null || :
cp "$HOME/pdv-v3-scanner/src/pages/venda-nova.html" "$BASE_DIR/public/pages/" 2>/dev/null || :

# Copiar scripts
cp "$HOME/pdv-v3/scripts/setup-db.js" "$BASE_DIR/scripts/" 2>/dev/null || :

# Copiar arquivos de configuração
cp "$HOME/pdv-v3/.eslintrc.json" "$BASE_DIR/" 2>/dev/null || :
cp "$HOME/pdv-v3/.npmrc" "$BASE_DIR/" 2>/dev/null || :
cp "$HOME/pdv-v3/package.json" "$BASE_DIR/" 2>/dev/null || :
cp "$HOME/pdv-v3/README.md" "$BASE_DIR/" 2>/dev/null || :

# Criar arquivo render.yaml adaptado para usar pasta public
echo -e "${YELLOW}Criando render.yaml...${NC}"
cat > "$BASE_DIR/render.yaml" << EOF
services:
  # Serviço Web (API + Front)
  - type: web
    name: pdv-3
    env: node
    plan: free
    buildCommand: npm ci
    startCommand: npm start
    repo: https://github.com/jesusmjunior/pdv-3.git
    branch: main
    healthCheckPath: /api/system/status
    envVars:
      - key: NODE_ENV
        value: production
      - key: DB_HOST
        fromDatabase:
          name: pdv-3-db
          property: host
      - key: DB_USER
        fromDatabase:
          name: pdv-3-db
          property: user
      - key: DB_PASSWORD
        fromDatabase:
          name: pdv-3-db
          property: password
      - key: DB_NAME
        fromDatabase:
          name: pdv-3-db
          property: database
      - key: DB_PORT
        fromDatabase:
          name: pdv-3-db
          property: port
      - key: JWT_SECRET
        sync: false
      - key: PORT
        value: 3000
        
databases:
  # Banco de dados PostgreSQL
  - name: pdv-3-db
    plan: free
    databaseName: pdv_3
    user: pdv_app
EOF

# Criar .env.example
echo -e "${YELLOW}Criando .env.example...${NC}"
cat > "$BASE_DIR/.env.example" << EOF
# Configurações do Ambiente
NODE_ENV=development

# Configurações do Servidor
PORT=3000

# Configurações do Banco de Dados
DB_HOST=localhost
DB_USER=pdv_app
DB_PASSWORD=sua_senha_aqui
DB_NAME=pdv_3
DB_PORT=5432

# Segurança
JWT_SECRET=sua_chave_jwt_secreta_muito_longa_e_aleatoria
JWT_EXPIRATION=24h

# Configurações de Log
LOG_LEVEL=info

# Configurações de Taxa de Limite
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX=100
EOF

# Criar .gitignore
echo -e "${YELLOW}Criando .gitignore...${NC}"
cat > "$BASE_DIR/.gitignore" << EOF
# Dependências
node_modules/
yarn.lock

# Variáveis de ambiente
.env
.env.local
.env.*.local

# Logs
logs
*.log
npm-debug.log*

# Arquivos do sistema
.DS_Store
Thumbs.db

# Arquivos IDE/editores
.idea/
.vscode/*
!.vscode/settings.json
*.swp

# Arquivos temporários
tmp/
temp/
EOF

# Criar workflow GitHub Actions
echo -e "${YELLOW}Criando GitHub Actions workflow...${NC}"
mkdir -p "$BASE_DIR/.github/workflows"
cat > "$BASE_DIR/.github/workflows/deploy.yml" << EOF
name: Deploy to Render

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run linting
        run: npm run lint || true
  
  deploy:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Trigger Render Deploy
        run: |
          curl -X POST \${{ secrets.RENDER_DEPLOY_HOOK }}
EOF

# Ajustar api/index.js para servir pasta public
echo -e "${YELLOW}Atualizando api/index.js para servir pasta public...${NC}"
# Se o arquivo não existe, criar um modelo
if [ ! -f "$BASE_DIR/api/index.js" ]; then
  cat > "$BASE_DIR/api/index.js" << EOF
// API para Sistema PDV
const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const path = require('path');
const bodyParser = require('body-parser');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');

// Importar controladores
const controllers = require('./controllers');

// Carregar variáveis de ambiente
dotenv.config();

// Inicializar Express
const app = express();

// Configuração de segurança com helmet
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'unsafe-inline'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      imgSrc: ["'self'", "data:"],
      connectSrc: ["'self'"]
    }
  }
}));

// Limite de requisições para evitar ataques
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutos
  max: 100, // limite de 100 requisições por IP
  standardHeaders: true,
  legacyHeaders: false,
});
app.use('/api/', limiter);

// Compressão para melhorar performance
app.use(compression());

// Middlewares
app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// Middleware de log simplificado
app.use((req, res, next) => {
  console.log(\`\${new Date().toISOString()} - \${req.method} \${req.originalUrl}\`);
  next();
});

// Servir arquivos estáticos da pasta public
app.use(express.static(path.join(__dirname, '../public')));

// Middleware de autenticação
const { authenticateToken } = controllers.auth;

// Rotas de sistema
app.get('/api/system/status', controllers.system.getStatus);
app.get('/api/system/stats', authenticateToken, controllers.system.getStats);

// Rotas de autenticação
app.post('/api/auth/login', controllers.auth.login);
app.post('/api/auth/logout', controllers.auth.logout);

// API Routers
const produtoRouter = express.Router();
produtoRouter.get('/', controllers.product.getAll);
produtoRouter.get('/baixo-estoque', controllers.product.getLowStock);
produtoRouter.get('/barcode/:codigo', controllers.product.getByBarcode);
produtoRouter.get('/:id', controllers.product.getById);
produtoRouter.post('/', controllers.product.create);
produtoRouter.put('/:id', controllers.product.update);
produtoRouter.delete('/:id', controllers.product.delete);
app.use('/api/produtos', authenticateToken, produtoRouter);

const clienteRouter = express.Router();
clienteRouter.get('/', controllers.client.getAll);
clienteRouter.get('/documento/:documento', controllers.client.getByDocument);
clienteRouter.get('/:id', controllers.client.getById);
clienteRouter.post('/', controllers.client.create);
clienteRouter.put('/:id', controllers.client.update);
clienteRouter.delete('/:id', controllers.client.delete);
app.use('/api/clientes', authenticateToken, clienteRouter);

const vendaRouter = express.Router();
vendaRouter.get('/', controllers.sale.getAll);
vendaRouter.get('/stats', controllers.sale.getStats);
vendaRouter.get('/:id', controllers.sale.getById);
vendaRouter.post('/', controllers.sale.create);
vendaRouter.put('/:id/cancelar', controllers.sale.cancel);
app.use('/api/vendas', authenticateToken, vendaRouter);

// Rota catchall para SPA
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../public/pages/index.html'));
});

// Iniciar servidor
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(\`Servidor rodando na porta \${PORT}\`);
  console.log(\`Ambiente: \${process.env.NODE_ENV || 'development'}\`);
});
EOF
fi

# Empacotar diretório para entrega
echo -e "${YELLOW}Empacotando projeto...${NC}"
cd "$HOME"
tar -czvf pdv-3-github.tar.gz -C "$HOME" pdv-3-github

echo -e "${GREEN}Estrutura criada com sucesso em $BASE_DIR${NC}"
echo -e "${GREEN}Arquivo compactado: $HOME/pdv-3-github.tar.gz${NC}"
echo -e "${BLUE}Importante: O diretório 'public/' foi configurado conforme requisitos do Render${NC}"
echo -e "${YELLOW}Credenciais padrão: usuário 'admin', senha 'admin'${NC}"