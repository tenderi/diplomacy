# The browser client.
#
# Stage 1 builds the React SPA with VITE_API_URL=/api, so every API call the
# page makes is same-origin under /api/. Stage 2 is nginx: it serves the
# static build and proxies /api/* to the API container on the compose network
# (DIPLOMACY_API_UPSTREAM, substituted into the template at container start). No CORS, no secrets, nothing here but static files and a
# reverse proxy.
FROM node:22-alpine@sha256:1314fb30ec37592d5845e5a160d522c0e680972aa534549940b8d73bde88481a AS build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
# --ignore-scripts: no dependency runs code at install time (vite and esbuild need none).
RUN npm ci --ignore-scripts
COPY frontend/ ./
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.28-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236
COPY docker/web-nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /build/dist /usr/share/nginx/html
# host:port, substituted into the template by the image's envsubst hook on start.
ENV DIPLOMACY_API_UPSTREAM=diplomacy_api:8000
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz >/dev/null || exit 1
