# CONTROL LAYER — the browser client. Runs on the VPS.
#
# Stage 1 builds the React SPA with VITE_API_URL=/api, so every API call the
# page makes is same-origin under /api/. Stage 2 is nginx: it serves the
# static build and proxies /api/* across the WireGuard tunnel to the API on
# the home server (DIPLOMACY_API_UPSTREAM, substituted into the template at
# container start). No CORS, no secrets, nothing here but static files and a
# reverse proxy.
FROM node:22-alpine AS build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY docker/web-nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /build/dist /usr/share/nginx/html
# host:port, substituted into the template by the image's envsubst hook on start.
ENV DIPLOMACY_API_UPSTREAM=10.8.0.2:8000
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz >/dev/null || exit 1
