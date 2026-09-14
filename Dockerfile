ARG NODE_IMAGE=mcr.microsoft.com/azurelinux/base/nodejs:24.20.0-1-azl3.0.20260909
ARG PYTHON_IMAGE=mcr.microsoft.com/azurelinux/base/python:3.12.14-1-azl3.0.20260909

FROM ${NODE_IMAGE} AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVE_FRONTEND=true \
    STATIC_DIR=/app/frontend-dist \
    PORT=10000
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN ln -sf /usr/bin/python3 /usr/bin/python
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /frontend/dist /app/frontend-dist
RUN mkdir -p /app/uploads && chmod +x /app/entrypoint.sh
EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '10000') + '/health', timeout=3)"
CMD ["/app/entrypoint.sh"]
