# Instruções para Atualização do PDV-2028

Prezado usuário,

Preparamos uma versão atualizada do seu sistema PDV para corrigir os problemas de deploy no Render. Esta atualização resolve os avisos relacionados ao bcrypt e ao uso misto de npm e yarn.

## Arquivos Atualizados

O arquivo compactado `pdv-v2.tar.gz` contém a versão atualizada do projeto com as seguintes modificações:

1. **package.json**: Atualizado para usar bcryptjs em vez de bcrypt
2. **api/controllers/authController.js**: Modificado para usar bcryptjs
3. **scripts/setup-db.js**: Modificado para usar bcryptjs
4. **.npmrc**: Novo arquivo para configuração do npm
5. **render.yaml**: Otimizado para evitar conflitos entre npm e yarn
6. **.gitignore**: Adicionado para excluir arquivos desnecessários
7. **README.md**: Atualizado com instruções para a versão 2.0

## Como Aplicar a Atualização

### Opção 1: Atualizar o Repositório Existente

1. Faça backup do seu repositório atual:
   ```bash
   cp -r /caminho/para/seu/repositorio /caminho/para/seu/repositorio.bak
   ```

2. Extraia os arquivos da versão 2:
   ```bash
   tar -xzvf pdv-v2.tar.gz -C /caminho/temporario/
   ```

3. Copie os arquivos atualizados para seu repositório:
   ```bash
   cp -r /caminho/temporario/pdv-v2/* /caminho/para/seu/repositorio/
   ```

4. Envie as alterações para o GitHub:
   ```bash
   cd /caminho/para/seu/repositorio
   git add .
   git commit -m "Atualização para versão 2.0 com bcryptjs e correções de deploy"
   git push
   ```

### Opção 2: Criar um Novo Repositório no GitHub

1. Crie um novo repositório no GitHub (por exemplo, pdv-2028-v2)

2. Extraia e prepare os arquivos:
   ```bash
   tar -xzvf pdv-v2.tar.gz
   cd pdv-v2
   rm -rf .git  # Remover histórico git existente
   git init
   git add .
   git commit -m "Versão 2.0 - Atualizada com bcryptjs"
   ```

3. Adicione o novo repositório como remote e envie:
   ```bash
   git remote add origin https://github.com/seu-usuario/pdv-2028-v2.git
   git push -u origin main
   ```

4. Configure o deploy no Render apontando para o novo repositório

## Configuração no Render

1. Acesse o dashboard do Render
2. Edite seu serviço existente ou crie um novo
3. Na seção "Build & Deploy":
   - Configure o Build Command para: `rm -f yarn.lock && npm ci`
   - Verifique se o Start Command está como: `npm start`
4. Certifique-se de que as variáveis de ambiente estão configuradas corretamente

## Principais Alterações Técnicas

1. **Migração para bcryptjs**:
   - Substituímos o pacote nativo bcrypt pelo bcryptjs puro em JavaScript
   - A API é compatível, então não há necessidade de alterar a lógica do código

2. **Resolução de Conflitos npm/yarn**:
   - Configurado para usar apenas npm, eliminando conflitos com o yarn
   - Adicionado .npmrc para suprimir mensagens de funding

3. **Otimização do Build**:
   - Configuração no render.yaml para remover yarn.lock e usar npm ci
   - Isso garante uma instalação limpa e reproduzível

## Verificação da Instalação

Após aplicar a atualização e fazer o deploy, verifique:

1. Ausência de mensagens de erro relacionadas ao bcrypt no log do deploy
2. Ausência de avisos sobre conflitos entre npm e yarn
3. Correto funcionamento da autenticação (login) e cadastro de usuários

Se encontrar algum problema, consulte o README atualizado ou entre em contato para suporte.

---

Obrigado por usar nosso sistema PDV!

Data da atualização: 26/04/2025