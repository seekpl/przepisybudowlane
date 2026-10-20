# Kontekst budowania: katalog główny repozytorium (generator tokenów czyta design/tokens.json).
FROM node:22-alpine AS deps
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app/frontend
# Przekierowania /api/v1 → backend są zapisywane w trakcie budowania, więc adres backendu podajemy już tu.
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=$BACKEND_URL \
    NEXT_OUTPUT=standalone \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/frontend/node_modules ./node_modules
COPY design /app/design
COPY frontend/ ./
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
COPY --from=build /app/frontend/.next/standalone ./
COPY --from=build /app/frontend/.next/static ./.next/static
COPY --from=build /app/frontend/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
