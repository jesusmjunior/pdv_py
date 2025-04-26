# Instruções para resolver os avisos no projeto PDV

## 1. Resolver conflito de lockfiles

Escolha um gerenciador de pacotes (npm OU yarn) e siga um destes passos:

### Se preferir usar npm:
```bash
# Remover yarn.lock
rm yarn.lock
# Atualizar package-lock.json
npm install
```

### Se preferir usar yarn:
```bash
# Remover package-lock.json
rm package-lock.json
# Atualizar yarn.lock
yarn
```

## 2. Atualizar dependências com avisos

O pacote bcrypt está usando várias dependências desatualizadas. Recomendo:

```bash
# Atualize para a versão mais recente do bcrypt
npm install bcrypt@latest

# Ou se estiver usando yarn
yarn add bcrypt@latest
```

## 3. Alternativa ao bcrypt

Se os problemas persistirem, considere usar o pacote bcryptjs que não possui dependências nativas:

```bash
# Remover bcrypt e instalar bcryptjs
npm remove bcrypt
npm install bcryptjs

# Ou com yarn
yarn remove bcrypt
yarn add bcryptjs
```

Depois, atualize os imports no código:
De: `const bcrypt = require('bcrypt');`
Para: `const bcrypt = require('bcryptjs');`

## 4. Outros pacotes com avisos

Para resolver avisos específicos:

```bash
# Atualizar rimraf
npm install rimraf@latest --save-dev

# Usar alternativa para inflight
# Não há ação direta necessária, pois é uma dependência indireta
```

## 5. Adicionar um .npmrc para ignorar mensagens de funding

Crie um arquivo `.npmrc` na raiz do projeto com:
```
fund=false
```

Isso vai suprimir as mensagens sobre pacotes solicitando financiamento.

---

Após fazer essas alterações, recomendo executar um novo deploy no Render para verificar se os avisos foram resolvidos.