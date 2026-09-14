ARG PYTHON_IMAGE=mcr.microsoft.com/azurelinux/base/python:3.12.14-1-azl3.0.20260909
FROM ${PYTHON_IMAGE}
WORKDIR /app
COPY requirements.txt .
RUN ln -sf /usr/bin/python3 /usr/bin/python
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r requirements.txt
COPY . .
RUN mkdir -p /app/uploads
RUN chmod +x /app/entrypoint.sh
CMD ["/app/entrypoint.sh"]
