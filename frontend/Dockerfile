# Imagen de producción del frontend: construcción en etapas y salida autónoma de Next.js.
FROM node:20-alpine AS dependencias
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS construccion
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=dependencias /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public && npm run build

FROM node:20-alpine AS ejecucion
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S sigs && adduser -S sigs -G sigs
COPY --from=construccion --chown=sigs:sigs /app/.next/standalone ./
COPY --from=construccion --chown=sigs:sigs /app/.next/static ./.next/static
COPY --from=construccion --chown=sigs:sigs /app/public ./public
USER sigs
EXPOSE 3000
CMD ["node", "server.js"]
