#!/bin/sh
# Escreve a configuração de tempo de execução antes de o nginx subir.
#
# O Vite embute `import.meta.env` na compilação, então o endereço da API ficaria
# congelado na imagem. Reescrever `config.js` aqui faz o mesmo artefato servir
# qualquer ambiente — e é isso que torna "a imagem testada é a imagem
# publicada" verdadeiro.
set -eu

API_URL="${API_URL:-http://localhost:8000}"
DESTINO=/usr/share/nginx/html/config.js

cat > "$DESTINO" <<EOF
window.__BANCO_CONFIG__ = { apiUrl: "${API_URL}" };
EOF

echo "configuração aplicada: apiUrl=${API_URL}"
