ARG NODE_IMAGE=mcr.microsoft.com/azurelinux/base/nodejs:24.20.0-1-azl3.0.20260909
ARG NGINX_IMAGE=mcr.microsoft.com/azurelinux/base/nginx:1.28.3-8-azl3.0.20260909

FROM ${NODE_IMAGE} AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM ${NGINX_IMAGE}
COPY nginx.conf /etc/nginx/nginx.conf.default
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD curl --fail --silent http://127.0.0.1/healthz > /dev/null || exit 1
