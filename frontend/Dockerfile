ARG APP_BASE_PATH=/tradebridge
FROM node:22-alpine AS build
ARG APP_BASE_PATH

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# The existing API client treats an empty base URL as same-origin.
ENV VITE_API_BASE_URL=""
ENV APP_BASE_PATH=${APP_BASE_PATH}
RUN npm run build && printf '%s' "$APP_BASE_PATH" | sed 's:/*$::' > /app/app-base-path

FROM nginx:1.28-alpine AS runtime
ARG APP_BASE_PATH
ENV APP_BASE_PATH=${APP_BASE_PATH} \
    NGINX_ENVSUBST_FILTER=^APP_BASE_PATH$

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY nginx-proxy.conf /etc/nginx/tradebridge-proxy.conf
COPY nginx-routes.conf /etc/nginx/tradebridge-routes.conf
COPY docker-entrypoint.d/15-app-base-path.sh /docker-entrypoint.d/15-app-base-path.sh
RUN sed -i 's/\r$//' /docker-entrypoint.d/15-app-base-path.sh && chmod +x /docker-entrypoint.d/15-app-base-path.sh
COPY --from=build /app/app-base-path /etc/nginx/app-base-path
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080 8081
