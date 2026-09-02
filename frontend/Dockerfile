# Imagem do frontend, em dois estágios.
#
# O primeiro compila; o segundo serve. O resultado carrega nginx e arquivos
# estáticos — nada de Node, `node_modules` ou código-fonte em produção.

FROM node:24-alpine AS compilacao
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---------------------------------------------------------------------------

FROM nginx:1.27-alpine AS servidor

COPY --from=compilacao /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /docker-entrypoint.d/40-configuracao.sh
RUN chmod +x /docker-entrypoint.d/40-configuracao.sh

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost/ >/dev/null || exit 1
