# The documentation site (docs/ + mkdocs.yml, Material for MkDocs), built at image
# build time and served as static files. Build context is the repository root.
# Caddy puts it at DOCS_DOMAIN (docker/Caddyfile); it has no port of its own.
FROM python:3.14-slim AS build
# MkDocs 2.0 drops the plugin and theme system Material depends on: stay on 1.x.
RUN pip install --no-cache-dir "mkdocs>=1.6,<2" "mkdocs-material>=9.5,<10"
WORKDIR /src
COPY mkdocs.yml ./
COPY docs ./docs
# --strict: a broken link fails the build (and so the deploy), not the reader.
RUN mkdocs build --strict --site-dir /site

FROM nginx:1.27-alpine
COPY docker/docs-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /site /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
