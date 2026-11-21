# The documentation site (docs/ + mkdocs.yml, Material for MkDocs), built at image
# build time and served as static files. Build context is the repository root.
# Caddy puts it at DOCS_DOMAIN (docker/Caddyfile); it has no port of its own.
FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS build
# MkDocs 2.0 drops the plugin and theme system Material depends on: stay on 1.x.
COPY docker/docs-requirements.txt /tmp/
RUN pip install --no-cache-dir --no-deps --require-hashes -r /tmp/docs-requirements.txt
WORKDIR /src
COPY mkdocs.yml ./
COPY docs ./docs
# --strict: a broken link fails the build (and so the deploy), not the reader.
RUN mkdocs build --strict --site-dir /site

FROM nginx:1.28-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236
COPY docker/docs-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /site /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
