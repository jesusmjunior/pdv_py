# Arquitetura PDV v3 - Estrutura completa

## Estrutura de Arquivos para GitHub

```
pdv-3/
├── api/                     # Backend API Node.js/Express
│   ├── controllers/         # Controladores REST
│   │   ├── authController.js
│   │   ├── clientController.js
│   │   ├── productController.js
│   │   ├── saleController.js
│   │   ├── systemController.js
│   │   └── index.js
│   ├── models/              # Modelos e conexão com PostgreSQL
│   │   └── database.js      # Configuração do Pool PostgreSQL
│   └── index.js             # Configuração Express com segurança
├── public/                  # ⚠️ Diretório reconhecido pelo Render
│   ├── css/                 # Estilos CSS
│   │   └── styles.css
│   ├── js/                  # JavaScript client-side
│   │   ├── components/      # Componentes reutilizáveis
│   │   ├── core/            # Funções core
│   │   │   ├── app.js
│   │   │   ├── auth.js
│   │   │   ├── database.js  # Cliente JavaScript para DB
│   │   │   └── utils.js
│   │   └── modules/         # Módulos específicos
│   │       └── scanner/     # Scanner de código de barras
│   │           └── barcode-scanner.js
│   ├── img/                 # Imagens
│   └── pages/               # Páginas HTML
│       ├── index.html       # Redirecionamento para login
│       ├── login.html
│       ├── dashboard.html
│       ├── produtos.html
│       ├── clientes.html
│       ├── vendas.html
│       ├── venda-nova.html
│       └── scan.html        # Página de scanner
├── scripts/                 # Scripts utilitários
│   └── setup-db.js          # Inicialização do banco de dados
├── .github/                 # Configurações do GitHub
│   └── workflows/           # GitHub Actions para CI/CD
│       └── deploy.yml
├── .vscode/                 # Configurações VS Code
│   └── settings.json
├── .env.example             # Template de variáveis de ambiente  
├── .eslintrc.json           # Configuração ESLint
├── .gitignore               # Arquivos ignorados pelo Git
├── .npmrc                   # Configuração npm
├── package.json             # Dependências e scripts
├── README.md                # Documentação
└── render.yaml              # Configuração do Render
```

## Configuração PostgreSQL

### 1. Estrutura do Banco

```sql
-- Tabela de Usuários
CREATE TABLE IF NOT EXISTS usuarios (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  nome VARCHAR(100) NOT NULL,
  email VARCHAR(100) UNIQUE,
  role VARCHAR(20) NOT NULL DEFAULT 'user',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de Produtos
CREATE TABLE IF NOT EXISTS produtos (
  id SERIAL PRIMARY KEY,
  codigo VARCHAR(50),
  codigo_barras VARCHAR(50) NOT NULL UNIQUE,  -- Chave primária para scanner
  nome VARCHAR(100) NOT NULL,
  categoria_id INTEGER REFERENCES categorias(id),
  descricao TEXT,
  preco_custo DECIMAL(10,2),
  preco_venda DECIMAL(10,2) NOT NULL,
  estoque INTEGER DEFAULT 0,
  estoque_minimo INTEGER DEFAULT 5,
  unidade VARCHAR(10) DEFAULT 'un',
  ultima_leitura TIMESTAMP,  -- Para rastrear uso do scanner
  imagem TEXT,
  ativo BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índice otimizado para busca de código de barras
CREATE INDEX IF NOT EXISTS idx_produtos_codigo_barras ON produtos(codigo_barras);
```

### 2. Conexão com Banco (api/models/database.js)

```javascript
const { Pool } = require('pg');
const pool = new Pool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  port: process.env.DB_PORT,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
});

module.exports = pool;
```

## Configuração do Render

### render.yaml

```yaml
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
```

## Entrega estática pelo Express (api/index.js)

```javascript
// Servir arquivos estáticos da pasta public
app.use(express.static(path.join(__dirname, '../public')));

// Rota catchall para SPA
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../public/pages/index.html'));
});
```

## Credenciais Padrão

- **Usuário:** admin
- **Senha:** admin 

## Instruções para Implementação

1. **Clone do repositório**:
   ```bash
   git clone https://github.com/jesusmjunior/pdv-3.git
   cd pdv-3
   ```

2. **Instalação de dependências**:
   ```bash
   npm ci
   ```

3. **Configuração do .env**:
   ```
   DB_HOST=localhost
   DB_USER=pdv_app
   DB_PASSWORD=sua_senha
   DB_NAME=pdv_3
   DB_PORT=5432
   JWT_SECRET=sua_chave_secreta
   PORT=3000
   ```

4. **Inicialização do banco**:
   ```bash
   npm run setup-db
   ```

5. **Execução local**:
   ```bash
   npm run dev
   ```

## Considerações importantes para o Render

1. **Diretório `public/`**: O Render reconhece automaticamente esta pasta para servir arquivos estáticos.

2. **Redirecionamento para páginas HTML**: Importante garantir que as rotas sejam tratadas corretamente.

3. **PostgreSQL**: O Render provisiona automaticamente o PostgreSQL conforme configurado no render.yaml.

4. **Variáveis de ambiente**: São configuradas no render.yaml e acessíveis via process.env.

5. **Deployment**: O Render usa o buildCommand e startCommand conforme definidos no render.yaml.