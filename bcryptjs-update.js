/**
 * Script para atualizar as referências de bcrypt para bcryptjs no projeto
 * 
 * Este script modifica automaticamente todos os arquivos .js no projeto
 * para substituir as importações do bcrypt pelo bcryptjs, mantendo
 * a mesma API e funcionalidade.
 */

const fs = require('fs');
const path = require('path');

// Diretórios a serem verificados
const directories = [
  path.join(__dirname, 'api'),
  path.join(__dirname, 'scripts')
];

// Função para percorrer diretórios recursivamente
function walkDir(dir, callback) {
  fs.readdirSync(dir).forEach(f => {
    let dirPath = path.join(dir, f);
    let isDirectory = fs.statSync(dirPath).isDirectory();
    isDirectory ? walkDir(dirPath, callback) : callback(path.join(dir, f));
  });
}

// Função para atualizar os imports do bcrypt
function updateBcryptImports(filePath) {
  if (!filePath.endsWith('.js')) return;
  
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    
    // Verificar se o arquivo usa bcrypt
    if (content.includes('require(\'bcrypt\')') || 
        content.includes('require("bcrypt")') ||
        content.includes('from \'bcrypt\'') ||
        content.includes('from "bcrypt"')) {
      
      // Substituir as importações
      let updated = content
        .replace(/require\(['"]bcrypt['"]\)/g, 'require(\'bcryptjs\')')
        .replace(/from ['"]bcrypt['"]/g, 'from \'bcryptjs\'');
      
      // Escrever o arquivo atualizado
      fs.writeFileSync(filePath, updated, 'utf8');
      console.log(`Atualizado: ${filePath}`);
    }
  } catch (err) {
    console.error(`Erro ao processar ${filePath}:`, err);
  }
}

// Executar a atualização em todos os diretórios
console.log('Iniciando atualização de bcrypt para bcryptjs...');
directories.forEach(dir => {
  if (fs.existsSync(dir)) {
    walkDir(dir, updateBcryptImports);
  } else {
    console.log(`Diretório não encontrado: ${dir}`);
  }
});
console.log('Atualização concluída!');

/**
 * Instruções:
 * 
 * 1. Primeiro, instale o bcryptjs:
 *    - npm remove bcrypt
 *    - npm install bcryptjs
 * 
 * 2. Execute este script:
 *    - node bcryptjs-update.js
 * 
 * 3. Verifique se as funções continuam funcionando corretamente
 *    - A API do bcryptjs é compatível com bcrypt
 *    - Não são necessárias alterações adicionais no código
 */